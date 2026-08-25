"""
core/fitting/objectives.py — loss builders from SpecKG + waveforms.

Residual builders shared by the staged fitter:
- DC residuals over (vin, iload, mode) -> vout/iq samples
- transient waveform residuals (weighted point-wise + feature terms)
- transient feature extraction (undershoot, settling, ringing)
- spec compliance table against SpecKG SpecConstraints

Weighting comes from SpecKG: each SpecConstraint carries a
`transient_weight` field (recon note: this is the spec's loss-weight
knob — there is no field literally named loss_weight).
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np


def spec_weights(spec_kg) -> Dict[str, float]:
    """SpecConstraint.name -> transient_weight (default 0.5)."""
    if spec_kg is None:
        return {}
    return {s.name: float(getattr(s, 'transient_weight', 0.5))
            for s in getattr(spec_kg, 'specs', [])}


# ─── DC ──────────────────────────────────────────────────────────────────────

def dc_residuals(template, params: Dict[str, float],
                 dc_points: List[dict]) -> np.ndarray:
    """Residual vector over DC sample points.

    Each point: {'vin', 'iload', optional 'mode', 'vout' (measured),
    optional 'iq' (measured)}. vout residuals are absolute volts; iq
    residuals are log-ratio (decades) so a 20 uA target and a 200 mA
    rail don't fight over scale."""
    res = []
    for pt in dc_points:
        op = template.dc_solve(params, pt['vin'], pt['iload'],
                               mode=pt.get('mode'))
        res.append(op['vout'] - pt['vout'])
        if 'iq' in pt and pt['iq'] > 0:
            model_iq = max(op['iq'], 1e-12)
            res.append(0.5 * np.log10(model_iq / pt['iq']))
    return np.asarray(res, dtype=float)


# ─── Transient features ──────────────────────────────────────────────────────

def transient_features(t: np.ndarray, vout: np.ndarray,
                       t_event: float, v_target: Optional[float] = None,
                       settle_band: float = 0.01) -> Dict[str, float]:
    """Undershoot / overshoot / settling time / ringing metric for a
    step event at t_event. v_target defaults to the pre-event mean."""
    t = np.asarray(t, dtype=float)
    vout = np.asarray(vout, dtype=float)
    pre = vout[(t < t_event) & (t > t_event - (t_event - t[0]) * 0.5)]
    if v_target is None:
        v_target = float(pre.mean()) if len(pre) else float(vout[0])
    post_mask = t >= t_event
    tp, vp = t[post_mask], vout[post_mask]
    if len(vp) < 3:
        return {'undershoot': 0.0, 'overshoot': 0.0, 'settling_time': 0.0,
                'ringing': 0.0, 'v_target': v_target}
    undershoot = float(max(0.0, v_target - vp.min()))
    overshoot = float(max(0.0, vp.max() - v_target))
    band = settle_band * abs(v_target)
    outside = np.where(np.abs(vp - v_target) > band)[0]
    settling = float(tp[outside[-1]] - t_event) if len(outside) else 0.0
    # ringing: number of band crossings after the first re-entry
    dev = vp - v_target
    crossings = int(np.sum(np.diff(np.sign(dev)) != 0))
    return {'undershoot': undershoot, 'overshoot': overshoot,
            'settling_time': settling, 'ringing': float(crossings),
            'v_target': v_target}


def transient_residual(template, params: Dict[str, float], tr: dict,
                       weights: Optional[Dict[str, float]] = None,
                       feature_weight: float = 5.0) -> np.ndarray:
    """Weighted residual for one transient record:
    {'t', 'inputs': {vin, iload, en, hp...}, 'vout_ref',
     optional 'ivin_ref', optional 't_event', optional 'mode'}.

    Point-wise vout residual (normalized to the reference span) plus,
    when t_event is given, feature residuals (undershoot/settling deltas)
    scaled by SpecKG weights."""
    weights = weights or {}
    t = np.asarray(tr['t'], dtype=float)
    ref = np.asarray(tr['vout_ref'], dtype=float)
    sim = template.simulate(params, t, tr['inputs'], mode=tr.get('mode'))
    span = max(float(ref.max() - ref.min()), 1e-3)
    res = [(sim['vout'] - ref) / span]

    if 'ivin_ref' in tr:
        iref = np.asarray(tr['ivin_ref'], dtype=float)
        ispan = max(float(iref.max() - iref.min()), 1e-6)
        res.append(0.5 * (sim['i_vin'] - iref) / ispan)

    if 't_event' in tr:
        w_sett = weights.get('Settling_Time', 0.8)
        w_tran = weights.get('Load_Transient_Peak',
                             weights.get('Load_Transient', 0.8))
        f_ref = transient_features(t, ref, tr['t_event'])
        f_sim = transient_features(t, sim['vout'], tr['t_event'])
        res.append(np.array([
            feature_weight * w_tran *
            (f_sim['undershoot'] - f_ref['undershoot']) / span,
            feature_weight * w_sett *
            (f_sim['settling_time'] - f_ref['settling_time'])
            / max(t[-1] - tr['t_event'], 1e-9),
        ]))
    return np.concatenate(res)


# ─── Spec compliance ─────────────────────────────────────────────────────────

def spec_compliance_table(template, params: Dict[str, float], spec_kg,
                          vin_nom: float = 5.0, iload_nom: float = 0.05,
                          iload_max: float = 0.2) -> List[dict]:
    """Evaluate the fitted template against every SpecConstraint the
    template can express. Rows: {spec, model_value, min, max, nominal,
    unit, passes, evaluated} — specs with no template view are returned
    with evaluated=False rather than silently dropped."""
    rows = []
    if spec_kg is None:
        return rows
    op = template.dc_solve(params, vin_nom, iload_nom)
    ss = template.small_signal(params, op)
    f = ss['freqs']

    def psrr_at(freq_hz):
        return float(ss['psrr_db'][np.argmin(np.abs(f - freq_hz))])

    # dropout: smallest (vin - vout_nom) keeping vout within 2% at iload_max
    dropout = None
    for vin in np.arange(1.25, 2.2, 0.01):
        o = template.dc_solve(params, vin, iload_max, mode={'uvlo_ok': 1})
        if o['vout'] >= 0.98 * op['vout']:
            dropout = vin - o['vout']
            break

    for s in spec_kg.specs:
        name = s.name
        val = None
        if name in ('Output_Voltage',):
            val = op['vout']
        elif 'Dropout' in name:
            val = dropout
        elif 'Quiescent' in name:
            val = op['iq']
        elif 'PSRR' in name:
            freq = s.frequency if s.frequency > 0 else 1e3
            val = psrr_at(freq)
        elif 'Settling' in name:
            t = np.linspace(0, 40e-6, 1200)
            il = np.where(t < 10e-6, max(0.01, iload_nom / 5), iload_max)
            w = template.simulate(params, t, {'vin': vin_nom, 'iload': il})
            val = transient_features(t, w['vout'], 10e-6)['settling_time']
        elif 'Phase_Margin' in name:
            T = ss['loop_gain']
            idx = np.where(np.abs(T) < 1.0)[0]
            val = float(180 + np.angle(T[idx[0]], deg=True)) if len(idx) else None
        if val is None:
            rows.append({'spec': name, 'model_value': None, 'min': s.min_val,
                         'max': s.max_val, 'nominal': s.nominal,
                         'unit': s.unit, 'passes': None, 'evaluated': False})
        else:
            rows.append({'spec': name, 'model_value': float(val),
                         'min': s.min_val, 'max': s.max_val,
                         'nominal': s.nominal, 'unit': s.unit,
                         'passes': bool(s.min_val <= val <= s.max_val),
                         'evaluated': True})
    return rows
