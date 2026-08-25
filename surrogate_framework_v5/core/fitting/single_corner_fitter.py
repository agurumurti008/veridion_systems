"""
core/fitting/single_corner_fitter.py — staged system identification.

SingleCornerFitter.fit() runs the Section-4 pipeline on one PVT corner:

  Stage DC        : fit_stage=='dc' params against DC sweep points
                    (trust-region least_squares, bounds, log-space where
                    flagged).
  Stage LINEAR    : fit_stage=='linear' params against AC data when
                    present (Vector Fitting extracts empirical poles;
                    objective matches PSRR/Zout magnitude + dominant
                    poles), else against small-signal step ring-down via
                    ERA (recorded in the report as the transient-derived
                    path).
  Stage TRANSIENT : fit_stage=='transient' (plus refinement of earlier
                    stages) with differential_evolution seeded from
                    stages 1–2, then least_squares polish; objective is
                    the weighted time-domain residual with SpecKG
                    weights; simulation-in-the-loop via template.simulate.
  Identifiability : numerical Jacobian at the optimum; parameters with
                    normalized sensitivity below threshold or living in
                    rank-deficient directions are frozen to manifest
                    defaults and listed (fitted noise is a defect).

Optional NN residual (off by default): a small per-mode residual net on
the ODE RHS following the repo's NODE residual pattern, capped at <=10%
of the RHS magnitude. The POC bars are met by the physical template
first; the residual is an opt-in refinement layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np
from scipy.optimize import least_squares, differential_evolution

from .objectives import (
    dc_residuals, transient_residual, spec_weights, spec_compliance_table,
)
from .vector_fitting import vector_fit, era


@dataclass
class FitResult:
    params: Dict[str, float]
    per_stage_residuals: Dict[str, float]
    frozen_params: List[str]
    spec_compliance: List[dict]
    corner: str = ''
    notes: List[str] = field(default_factory=list)
    identifiability: Dict[str, float] = field(default_factory=dict)
    residual_net: Optional[object] = None


class SingleCornerFitter:
    def __init__(self, template, spec_kg=None,
                 de_maxiter: int = 12, de_popsize: int = 8,
                 sensitivity_threshold: float = 1e-3,
                 enable_nn_residual: bool = False, seed: int = 42):
        self.template = template
        self.spec_kg = spec_kg
        self.de_maxiter = de_maxiter
        self.de_popsize = de_popsize
        self.sensitivity_threshold = sensitivity_threshold
        self.enable_nn_residual = enable_nn_residual
        self.seed = seed

    # ─── Internals ──────────────────────────────────────────────────────────

    def _solve_stage(self, names: List[str], params: Dict[str, float],
                     residual_fn: Callable[[Dict[str, float]], np.ndarray]):
        """Bounded trust-region LS over `names` in fit space (log where
        flagged), all other params held at their current values."""
        man = self.template.manifest()
        x0_nat = man.to_vector(params, names)
        lo_f, hi_f = man.fit_space_bounds(names)
        x0_f = np.clip(man.to_fit_space(x0_nat, names), lo_f, hi_f)

        def fun(x_f):
            trial = dict(params)
            trial.update(man.from_vector(man.from_fit_space(x_f, names), names))
            try:
                return residual_fn(trial)
            except Exception:
                return np.full(1, 1e3)

        sol = least_squares(fun, x0_f, bounds=(lo_f, hi_f),
                            method='trf', max_nfev=60 * len(names))
        fitted = man.from_vector(man.from_fit_space(sol.x, names), names)
        out = dict(params)
        out.update(fitted)
        return out, float(np.sqrt(np.mean(sol.fun ** 2)))

    # ─── Stages ─────────────────────────────────────────────────────────────

    def _stage_dc(self, params, data, notes, exclude=frozenset()):
        names = [n for n in self.template.manifest().names_for_stage('dc')
                 if n not in exclude]
        dc_pts = data.get('dc', [])
        if not dc_pts or not names:
            notes.append('Stage DC skipped: no DC data provided.'
                         if not dc_pts else
                         'Stage DC re-polish skipped: all params frozen.')
            return params, float('nan')
        return self._solve_stage(
            names, params, lambda p: dc_residuals(self.template, p, dc_pts))

    def _stage_linear(self, params, data, notes, exclude=frozenset()):
        names = [n for n in self.template.manifest().names_for_stage('linear')
                 if n not in exclude]
        if not names:
            notes.append('Stage LINEAR re-polish skipped: all params frozen.')
            return params, float('nan')
        ac = data.get('ac')
        if ac is not None:
            freqs = np.asarray(ac['freqs'], dtype=float)
            # Empirical poles via Vector Fitting on the complex PSRR path
            # response (magnitude-only data is lifted to minimum-phase-ish
            # complex form by fitting |H| with zero phase — adequate for
            # pole extraction; noted).
            meas_psrr_db = np.asarray(ac['psrr_db'], dtype=float)
            H_meas = 10 ** (-meas_psrr_db / 20.0)
            try:
                vf = vector_fit(freqs, H_meas.astype(complex), n_poles=4)
                notes.append(
                    'Stage LINEAR: VF empirical poles (Hz): '
                    + ', '.join(f'{p/2/np.pi:.3g}' for p in vf.poles))
            except Exception as e:
                notes.append(f'Stage LINEAR: VF failed ({e}); '
                             'falling back to direct magnitude match.')

            zout_meas = np.asarray(ac['zout'], dtype=float) if 'zout' in ac else None
            op_pt = ac.get('op', {'vin': 5.0, 'iload': 0.05})

            def resid(p):
                op = self.template.dc_solve(p, op_pt['vin'], op_pt['iload'])
                ss = self.template.small_signal(p, op, freqs=freqs)
                r = [(ss['psrr_db'] - meas_psrr_db) / 20.0]
                if zout_meas is not None:
                    r.append(np.log10(np.maximum(ss['zout'], 1e-9))
                             - np.log10(np.maximum(zout_meas, 1e-9)))
                return np.concatenate(r)

            return self._solve_stage(names, params, resid)

        # No AC data: transient-derived linear stage (ERA on step ring-down)
        trs = data.get('transient', [])
        step_tr = next((tr for tr in trs if 't_event' in tr), None)
        if step_tr is None:
            notes.append('Stage LINEAR skipped: no AC data and no step '
                         'transient with t_event.')
            return params, float('nan')

        notes.append('Stage LINEAR: derived from small-signal step '
                     'ring-down via ERA (no AC data available).')
        t = np.asarray(step_tr['t'], dtype=float)
        ref = np.asarray(step_tr['vout_ref'], dtype=float)
        post = t >= step_tr['t_event']
        y = ref[post] - ref[post][-1]
        dt = float(np.mean(np.diff(t[post])))
        try:
            meas_poles, era_info = era(np.diff(y) / dt, dt, order=3)
            meas_poles = meas_poles[np.argsort(np.abs(meas_poles))]
            notes.append('Stage LINEAR: ERA ring-down poles (Hz): '
                         + ', '.join(f'{p/2/np.pi:.3g}' for p in meas_poles))
        except Exception as e:
            meas_poles = None
            notes.append(f'Stage LINEAR: ERA failed ({e}); matching the '
                         'ring-down waveform directly.')

        def resid(p):
            r = [transient_residual(self.template, p, step_tr,
                                    spec_weights(self.spec_kg))]
            if meas_poles is not None and len(meas_poles) >= 2:
                op = self.template.dc_solve(
                    p, step_tr['inputs'].get('vin', 5.0)
                    if np.isscalar(step_tr['inputs'].get('vin', 5.0)) else 5.0,
                    float(np.max(step_tr['inputs']['iload'])))
                ss = self.template.small_signal(p, op)
                mp = np.sort(np.abs(ss['poles']))[:2]
                tp = np.sort(np.abs(meas_poles))[:2]
                r.append(0.5 * (np.log10(np.maximum(mp, 1.0))
                                - np.log10(np.maximum(tp, 1.0))))
            return np.concatenate(r)

        return self._solve_stage(names, params, resid)

    def _stage_transient(self, params, data, notes, exclude=frozenset(),
                         local_only: bool = False):
        trs = data.get('transient', [])
        if not trs:
            notes.append('Stage TRANSIENT skipped: no transient data.')
            return params, float('nan')
        man = self.template.manifest()
        names = [n for n in man.names_for_stage('transient')
                 if n not in exclude]
        if not names:
            notes.append('Stage TRANSIENT re-polish skipped: all params frozen.')
            return params, float('nan')
        w = spec_weights(self.spec_kg)

        def full_resid(p):
            return np.concatenate(
                [transient_residual(self.template, p, tr, w) for tr in trs])

        if local_only:
            return self._solve_stage(names, params, full_resid)

        def scalar_obj(x_f):
            trial = dict(params)
            trial.update(man.from_vector(man.from_fit_space(x_f, names), names))
            try:
                r = full_resid(trial)
                return float(np.sqrt(np.mean(r ** 2)))
            except Exception:
                return 1e3

        lo_f, hi_f = man.fit_space_bounds(names)
        x_seed = np.clip(man.to_fit_space(man.to_vector(params, names), names),
                         lo_f, hi_f)
        # Global (bounded, seeded) then local polish
        de = differential_evolution(
            scalar_obj, bounds=list(zip(lo_f, hi_f)),
            maxiter=self.de_maxiter, popsize=self.de_popsize,
            init='sobol', x0=x_seed, seed=self.seed, tol=1e-6,
            polish=False, updating='deferred')
        seeded = dict(params)
        seeded.update(man.from_vector(man.from_fit_space(de.x, names), names))
        return self._solve_stage(names, seeded, full_resid)

    # ─── Identifiability gate ────────────────────────────────────────────────

    def _identifiability(self, params, data, notes):
        """Numerical Jacobian of the full residual stack w.r.t. every
        non-fixed parameter (fit space). Frozen = normalized column
        sensitivity below threshold OR dominant component of a
        rank-deficient SVD direction. Frozen params return to manifest
        defaults."""
        man = self.template.manifest()
        names = [n for n in man.names if man.spec(n).fit_stage != 'fixed']
        w = spec_weights(self.spec_kg)

        def full_resid(p):
            parts = []
            if data.get('dc'):
                parts.append(dc_residuals(self.template, p, data['dc']))
            for tr in data.get('transient', []):
                parts.append(transient_residual(self.template, p, tr, w))
            if not parts:
                return np.zeros(1)
            return np.concatenate(parts)

        x0 = man.to_fit_space(man.to_vector(params, names), names)
        r0 = full_resid(params)
        J = np.zeros((len(r0), len(names)))
        for j, n in enumerate(names):
            h = 1e-4 * max(1.0, abs(x0[j]))
            xp = x0.copy(); xp[j] += h
            xm = x0.copy(); xm[j] -= h
            pp = dict(params); pp.update(
                man.from_vector(man.from_fit_space(xp, names), names))
            pm = dict(params); pm.update(
                man.from_vector(man.from_fit_space(xm, names), names))
            J[:, j] = (full_resid(pp) - full_resid(pm)) / (2 * h)

        col_sens = np.linalg.norm(J, axis=0)
        max_sens = float(col_sens.max()) if col_sens.max() > 0 else 1.0
        norm_sens = col_sens / max_sens
        frozen = {n for n, s in zip(names, norm_sens)
                  if s < self.sensitivity_threshold}

        # Rank check: near-null-space directions freeze their dominant param
        _, S, Vt = np.linalg.svd(J, full_matrices=False)
        if S[0] > 0:
            for k in range(len(S)):
                if S[k] < 1e-4 * S[0]:
                    dom = names[int(np.argmax(np.abs(Vt[k])))]
                    frozen.add(dom)

        out = dict(params)
        for n in sorted(frozen):
            out[n] = man.spec(n).default
        if frozen:
            notes.append('Identifiability gate froze to defaults: '
                         + ', '.join(sorted(frozen)))
        sens_map = {n: float(s) for n, s in zip(names, norm_sens)}
        return out, sorted(frozen), sens_map

    # ─── Optional NN residual (repo NODE pattern, shim-compatible) ──────────

    def _train_nn_residual(self, params, data, notes):
        from core.numpy_mlp import NumpyMLP, torch_is_real

        trs = [tr for tr in data.get('transient', []) if 'vout_ref' in tr]
        if not trs:
            notes.append('NN residual requested but no transient data; skipped.')
            return None
        # Targets: one-step derivative mismatch between reference vout and
        # the fitted template, expressed on the v_co state; inputs are
        # [v_co, v_g, v_c, vin] normalized. Hard cap: <=10% of the RHS
        # magnitude, enforced on the targets before training.
        feats, targs, caps = [], [], []
        for tr in trs:
            t = np.asarray(tr['t'], dtype=float)
            sim = self.template.simulate(params, t, tr['inputs'],
                                         mode=tr.get('mode'))
            ref = np.asarray(tr['vout_ref'], dtype=float)
            d_ref = np.gradient(ref, t)
            d_sim = np.gradient(sim['vout'], t)
            rhs_mag = np.abs(d_sim) + 1e-3
            feats.append(np.stack([sim['v_co'], sim['vg'], sim['vc'],
                                   sim['vin']], axis=1))
            targs.append(d_ref - d_sim)
            caps.append(0.10 * rhs_mag)
        X = np.concatenate(feats)
        Y = np.concatenate(targs)
        CAP = np.concatenate(caps)
        Y = np.clip(Y, -CAP, CAP)
        x_mu, x_sd = X.mean(0), X.std(0) + 1e-9
        y_sd = float(np.abs(Y).max()) + 1e-12
        Xn = (X - x_mu) / x_sd
        Yn = (Y[:, None] / y_sd)

        if torch_is_real():
            import torch
            import torch.nn as nn
            torch.manual_seed(self.seed)
            net = nn.Sequential(nn.Linear(4, 16), nn.Tanh(), nn.Linear(16, 1))
            opt = torch.optim.Adam(net.parameters(), lr=1e-3)
            Xt = torch.tensor(Xn.astype(np.float32))
            Yt = torch.tensor(Yn.astype(np.float32))
            loss = None
            for _ in range(300):
                opt.zero_grad()
                loss = ((net(Xt) - Yt) ** 2).mean()
                loss.backward()
                opt.step()
            mse = float(loss.detach().cpu().numpy())
            model = ('torch', net)
        else:
            # torch_shim has no autograd (backward is a no-op) — train the
            # analytic-gradient NumPy MLP instead so the residual really fits.
            net = NumpyMLP(4, 16, 1, seed=self.seed)
            mse = net.fit(Xn, Yn, epochs=300, lr=5e-3)
            model = ('numpy', net)
        notes.append(f'NN residual trained (final mse={mse:.3e}, cap 10% '
                     f'RHS, applied to dv_co/dt only, backend={model[0]}).')
        return {'model': model, 'x_mu': x_mu, 'x_sd': x_sd, 'y_sd': y_sd}

    # ─── Pipeline ───────────────────────────────────────────────────────────

    def fit(self, data: dict, corner: str = '') -> FitResult:
        """data: {'dc': [points], 'ac': {...} (optional),
                  'transient': [records]} — see objectives.py for shapes."""
        notes: List[str] = []
        params = self.template.default_params()

        params, r_dc = self._stage_dc(params, data, notes)
        params, r_lin = self._stage_linear(params, data, notes)
        params, r_tr = self._stage_transient(params, data, notes)
        params, frozen, sens = self._identifiability(params, data, notes)

        # Freeze-then-repolish (real bug found during the build: freezing a
        # parameter back to its manifest default WITHOUT re-fitting leaves
        # its identifiable partners holding a compensation for the old
        # railed value — e.g. a railed V_ref compensated by Rf1 turns into
        # a plain vout error once V_ref snaps back). Re-run every stage
        # locally with the frozen set pinned.
        if frozen:
            excl = frozenset(frozen)
            params, r_dc2 = self._stage_dc(params, data, notes, exclude=excl)
            params, r_lin2 = self._stage_linear(params, data, notes,
                                                exclude=excl)
            params, r_tr2 = self._stage_transient(params, data, notes,
                                                  exclude=excl,
                                                  local_only=True)
            r_dc = r_dc2 if np.isfinite(r_dc2) else r_dc
            r_lin = r_lin2 if np.isfinite(r_lin2) else r_lin
            r_tr = r_tr2 if np.isfinite(r_tr2) else r_tr
            notes.append('Re-polished identifiable params with frozen set '
                         'pinned.')

        residual_net = None
        if self.enable_nn_residual:
            residual_net = self._train_nn_residual(params, data, notes)

        compliance = spec_compliance_table(self.template, params, self.spec_kg)
        return FitResult(
            params=params,
            per_stage_residuals={'dc': r_dc, 'linear': r_lin,
                                 'transient': r_tr},
            frozen_params=frozen,
            spec_compliance=compliance,
            corner=corner,
            notes=notes,
            identifiability=sens,
            residual_net=residual_net,
        )
