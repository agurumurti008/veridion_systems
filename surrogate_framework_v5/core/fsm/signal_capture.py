"""
core/fsm/signal_capture.py
Waveform loader + signal classifier for FSM auto-derivation.
"""
import logging
import numpy as np
import os
try:
    import pandas as pd
except ImportError:
    pd = None

log = logging.getLogger("surrogate_framework.signal_capture")


class SignalCapture:
    """Load, classify and export waveform data for FSM derivation."""

    def __init__(self, spec_kg=None):
        self.spec_kg = spec_kg
        self.signals: dict = {}   # name -> np.ndarray  (voltage/logic signals)
        self.current_signals: dict = {}  # name -> np.ndarray  (BLUT $flow-derived current signals)
        self.time: np.ndarray = None
        self.digital_signals: list = []
        self.analog_signals: list = []
        self.constant_signals: list = []  # rails/grounds — carry no FSM state information
        self.run_boundaries: list = []   # index into concatenated time axis where each run starts
        self.run_ids: list = []          # parallel to run_boundaries: run_id starting at that index
        self.run_corners: list = []      # parallel to run_boundaries: corner_id ("" if none)
        self.run_meta: list = []         # parallel to run_boundaries: RunMeta.meta string for that run

    def load_from_csv(self, filepath: str, time_col: str = 'time'):
        if pd is None:
            import csv
            with open(filepath, encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            if not rows:
                return
            cols = list(rows[0].keys())
            data = {c: np.array([float(r[c]) for r in rows]) for c in cols}
        else:
            df = pd.read_csv(filepath)
            data = {c: df[c].values for c in df.columns}

        if time_col in data:
            self.time = data.pop(time_col)
        else:
            n = len(next(iter(data.values())))
            self.time = np.linspace(0, 1e-4, n)

        self.signals = {k: v.astype(float) for k, v in data.items()}
        self._classify_signals()

    def load_synthetic(self, n_points: int = 1000, t_end: float = 100e-6,
                       ip_type: str = 'LDO'):
        self.time = np.linspace(0, t_end, n_points)
        t = self.time
        ip_type = ip_type.upper()

        if ip_type == 'LDO':
            # Startup exponential ramp (analog)
            tau = t_end * 0.15
            self.signals['VOUT'] = 1.8 * (1 - np.exp(-t / tau)) + 0.01 * np.random.randn(n_points) * 0.001
            # Load current sigmoid step (analog)
            t_step = t_end * 0.5
            self.signals['ILOAD'] = 0.1 + 0.4 / (1 + np.exp(-100000 * (t - t_step)))
            # Digital EN: 0 for first 5%, then 1
            en = np.zeros(n_points)
            en[int(0.05 * n_points):] = 1.0
            self.signals['EN'] = en
            # POK: goes high after startup (25% mark)
            pok = np.zeros(n_points)
            pok[int(0.25 * n_points):] = 1.0
            self.signals['POK'] = pok
            # FAULT: stays low
            self.signals['FAULT'] = np.zeros(n_points)

        elif ip_type == 'OTA':
            freq = 1e6
            self.signals['VDIFF'] = 0.1 * np.sin(2 * np.pi * freq * t)
            # Slew-limited output
            sr = 50e6  # V/s
            vout = np.zeros(n_points)
            for i in range(1, n_points):
                dt = t[i] - t[i - 1]
                target = self.signals['VDIFF'][i]
                delta = target - vout[i - 1]
                max_delta = sr * dt
                vout[i] = vout[i - 1] + np.clip(delta, -max_delta, max_delta)
            self.signals['VOUT'] = vout
            en = np.zeros(n_points)
            en[int(0.1 * n_points):] = 1.0
            self.signals['EN'] = en

        elif ip_type == 'DCDC':
            fsw = 2e6
            d = 0.36
            # SW node
            sw_period = 1.0 / fsw
            sw = np.zeros(n_points)
            for i, ti in enumerate(t):
                phase = (ti % sw_period) / sw_period
                sw[i] = 12.0 if phase < d else 0.0
            self.signals['VSW'] = sw
            # Inductor current with ripple
            il_avg = 0.5
            il_ripple = 0.1
            il = il_avg + il_ripple * np.sin(2 * np.pi * fsw * t)
            self.signals['IL'] = il
            # Output voltage (filtered)
            self.signals['VOUT'] = 1.8 + 0.02 * np.sin(2 * np.pi * fsw * t) + 0.005 * np.random.randn(n_points)
            en = np.zeros(n_points)
            en[int(0.05 * n_points):] = 1.0
            self.signals['EN'] = en
            pg = np.zeros(n_points)
            pg[int(0.2 * n_points):] = 1.0
            self.signals['PG'] = pg
        else:
            # Generic
            self.signals['SIG_A'] = np.sin(2 * np.pi * 1e4 * t)
            en = np.zeros(n_points)
            en[int(0.1 * n_points):] = 1.0
            self.signals['EN'] = en

        self._classify_signals()

    def load_from_blut(self, blut_path: str, run_id=None,
                       signal_map=None, current_suffixes=None):
        """Load signals from a digiTwin BLUT (v7) file for FSM derivation.

        run_id may be: None (load ALL runs in the file), a single qualified
        'run_id' or 'run_id@corner_id' string (load just that one run), or
        a list/tuple of such qualified strings (load exactly that SUBSET,
        e.g. only the (run_id, corner_id) pairs an upstream per-corner
        correlation pass judged trustworthy — see
        examples/example10_final_fsm_from_good_corners.py). All three
        forms concatenate into one FSM-derivation dataset, recording
        self.run_boundaries (index into the concatenated time axis where
        each run starts), self.run_ids, and self.run_meta so callers
        (TransitionLearner, get_analog_features) can avoid treating the
        artificial seam between two concatenated runs as a real transition
        or a real windowed statistic.

        Voltage columns populate self.signals exactly as the synthetic/CSV
        paths do today (so _is_bimodal / get_logic_signal_matrix /
        get_analog_features work unmodified downstream). Current columns
        (BLUT signals whose name matches a current_suffixes entry, default
        ["$flow"]) populate self.current_signals instead.

        If signal_map is given, decoded BLUT base names are renamed to
        their speckg_name before populating self.signals/self.current_signals,
        using kind-aware reverse_resolve so voltage and current pairs on the
        same BLUT base name land under the correct speckg_name. Names with
        no mapping fall back to their raw BLUT base name, and (once, the
        first time this happens for this call) a warning table is printed
        via SignalMap.unmapped_speckg_names / auto_suggest so mapping gaps
        are visible rather than silently applied.
        """
        from digitwin.blut_reader_ext import (
            open_blut, load_all_runs, load_run_matrix, get_run,
            DEFAULT_CURRENT_SUFFIXES,
        )

        suffixes = current_suffixes if current_suffixes is not None else DEFAULT_CURRENT_SUFFIXES
        blut = open_blut(blut_path)

        def _resolve_one(qualified_id: str):
            # v8: runs are keyed (run_id, corner_id). Accept a plain
            # run_id (resolved when unambiguous) or 'run_id@corner_id'.
            rid, _, cid = qualified_id.partition('@')
            run = get_run(blut, rid, cid if cid else None)
            return load_run_matrix(blut_path, run, None, suffixes)

        if run_id is None:
            run_dicts = load_all_runs(blut_path, None, suffixes)
        elif isinstance(run_id, (list, tuple)):
            run_dicts = [_resolve_one(qid) for qid in run_id]
        else:
            run_dicts = [_resolve_one(run_id)]

        if not run_dicts:
            raise ValueError(f"{blut_path}: no runs found (or resolved) to load")

        # Print the unmapped-name warning once per call, before renaming,
        # so the user sees exactly what mapping gap exists for this file.
        if signal_map is not None and self.spec_kg is not None:
            signal_map.print_unmapped_warning(self.spec_kg)
        elif signal_map is None:
            log.warning(
                "%s: no signal_map provided — falling back to raw BLUT signal "
                "names. Downstream FSM/Phase2 code will only see SpecKG-native "
                "names if you pass a SignalMap.",
                blut_path,
            )

        # Concatenate across runs, tracking boundaries.
        all_time = []
        # renamed_name -> {run_idx: per-run array}, run_idx-keyed (not just
        # appended in run order) so a signal missing from some runs but not
        # others — the normal case on a real heterogeneous multi-corner
        # file, where n_signals varies run to run — still gets NaN-filled
        # at the CORRECT run position rather than only at the trailing
        # runs (see _concat_aligned).
        all_voltage: dict = {}
        all_current: dict = {}
        self.run_boundaries = []
        self.run_ids = []
        self.run_corners = []
        self.run_meta = []

        cursor = 0
        for run_idx, rd in enumerate(run_dicts):
            self.run_boundaries.append(cursor)
            self.run_ids.append(rd["run_id"])
            self.run_corners.append(rd.get("corner_id", ""))
            self.run_meta.append(rd["meta"])

            n_t = len(rd["time"])
            all_time.append(rd["time"])
            cursor += n_t

            for j, raw_name in enumerate(rd["voltage_names"]):
                renamed = raw_name
                if signal_map is not None:
                    mapped = signal_map.reverse_resolve(raw_name, run_id=rd["run_id"], kind="voltage")
                    if mapped is not None:
                        renamed = mapped
                all_voltage.setdefault(renamed, {})[run_idx] = rd["voltage_matrix"][:, j]

            for j, raw_name in enumerate(rd["current_names"]):
                renamed = raw_name
                if signal_map is not None:
                    mapped = signal_map.reverse_resolve(raw_name, run_id=rd["run_id"], kind="current")
                    if mapped is not None:
                        renamed = mapped
                all_current.setdefault(renamed, {})[run_idx] = rd["current_matrix"][:, j]

        self.time = np.concatenate(all_time)
        total_n = len(self.time)

        # Any signal missing from a given run contributes a NaN-filled
        # segment of that run's length, so concatenated column lengths stay
        # aligned to self.time regardless of which runs actually had it.
        self.signals = {name: self._concat_aligned(by_run, run_dicts)
                        for name, by_run in all_voltage.items()}
        self.current_signals = {name: self._concat_aligned(by_run, run_dicts)
                                for name, by_run in all_current.items()}

        self._classify_signals()

    def _concat_aligned(self, by_run: dict, run_dicts: list) -> np.ndarray:
        """Concatenate a signal's per-run segments onto the full
        concatenated time axis, keyed by actual run index (not run
        declaration order among only the runs that had this signal) —
        NaN-fills any run that didn't have this signal at all, at that
        run's own position, so the result always matches self.time's
        length regardless of which specific runs (not necessarily a
        trailing/contiguous subset) had the signal."""
        result = []
        for run_idx, rd in enumerate(run_dicts):
            if run_idx in by_run:
                result.append(by_run[run_idx])
            else:
                result.append(np.full(len(rd["time"]), np.nan))
        return np.concatenate(result)

    def get_boundary_mask(self) -> np.ndarray:
        """Bool array, True at index i if sample i+1 is the start of a new
        run (an artificial concatenation seam). Length matches self.time
        (last element is always False since there's no i+1 past the end).
        Returns an all-False array if this SignalCapture was not loaded
        from a multi-run source (run_boundaries empty or single-run)."""
        n = len(self.time) if self.time is not None else 0
        mask = np.zeros(n, dtype=bool)
        if not self.run_boundaries:
            return mask
        for start_idx in self.run_boundaries[1:]:  # skip the first run's own start (index 0)
            if 0 < start_idx <= n:
                mask[start_idx - 1] = True
        return mask

    def get_current_features(self, n_windows: int = 10):
        """Mirrors get_analog_features but for self.current_signals (BLUT
        $flow-derived current signals). Phase 2 needs both voltage and
        current windowed features for joint voltage+current modelling."""
        if not self.current_signals:
            return None

        n = len(self.time)
        boundary_mask = self.get_boundary_mask()
        window_size = n // n_windows
        rows = []
        for w in range(n_windows):
            start = w * window_size
            end = min(start + window_size, n)
            # Clip window to the nearest preceding run boundary so a
            # window's mean/std/slope never blends two independent runs'
            # statistics (Section 5 requirement).
            if self.run_boundaries:
                for b in self.run_boundaries:
                    if start < b <= end:
                        end = b
                        break
            if end <= start:
                continue
            row = {'window': w, 't_start': self.time[start], 't_end': self.time[end - 1]}
            for name in self.current_signals:
                vals = self.current_signals[name][start:end]
                valid = vals[~np.isnan(vals)]
                if valid.size == 0:
                    row[f'{name}_mean'] = 0.0
                    row[f'{name}_std'] = 0.0
                    row[f'{name}_slope'] = 0.0
                    continue
                row[f'{name}_mean'] = float(valid.mean())
                row[f'{name}_std'] = float(valid.std())
                x = np.arange(len(valid), dtype=float)
                if len(x) > 1:
                    coeffs = np.polyfit(x, valid, 1)
                    row[f'{name}_slope'] = float(coeffs[0])
                else:
                    row[f'{name}_slope'] = 0.0
            rows.append(row)

        if pd is not None:
            return pd.DataFrame(rows)
        return rows

    def _is_constant(self, values: np.ndarray) -> bool:
        """True for signals pinned to a single level for the whole capture
        (ground/substrate/fixed rails such as AVSS, PBKG, gnd!). They carry
        no FSM state information and must not enter the logic matrix."""
        vals = np.asarray(values, dtype=float)
        valid = vals[~np.isnan(vals)]
        if valid.size == 0:
            return True
        return float(valid.max() - valid.min()) < 1e-6

    def _mid_rail_dwell(self, values: np.ndarray):
        """Per-run, time-weighted fraction of dwell in the mid-rail band
        (15%..85% of the signal's global span).

        Sample-count fractions are misleading for SPICE data: adaptive
        timesteps oversample edges/ramps, so a clean digital control that
        switches once per run can look 40% "mid-rail" by sample count while
        spending <1% of simulated time there. Weighting by dt and evaluating
        per run (a control held at a different level in each test case is
        still digital) fixes both failure modes.

        Returns (mean_mid, max_mid) across runs."""
        vals = np.asarray(values, dtype=float)
        n = len(vals)
        v_valid = vals[~np.isnan(vals)]
        v_min, v_max = float(v_valid.min()), float(v_valid.max())
        span = v_max - v_min
        if span <= 0:
            return 0.0, 0.0

        starts = list(self.run_boundaries) if self.run_boundaries else [0]
        edges = starts + [n]
        mids = []
        for k in range(len(starts)):
            s, e = edges[k], edges[k + 1]
            seg = vals[s:e]
            t_seg = self.time[s:e]
            ok = ~np.isnan(seg)
            if ok.sum() < 2:
                continue
            seg, t_seg = seg[ok], t_seg[ok]
            dt = np.diff(t_seg, append=t_seg[-1])
            dt = np.clip(dt, 0.0, None)
            total = dt.sum()
            if total <= 0:
                # degenerate/constant time axis — fall back to sample count
                dt = np.ones(len(seg))
                total = float(len(seg))
            norm = (seg - v_min) / span
            in_mid = (norm > 0.15) & (norm < 0.85)
            mids.append(float(dt[in_mid].sum() / total))

        if not mids:
            return 0.0, 0.0
        return float(np.mean(mids)), float(np.max(mids))

    def _is_bimodal(self, values: np.ndarray) -> bool:
        """Digital classifier — rail-to-rail switching signals are digital;
        ramps/sigmoids/regulated nodes are analog. Uses time-weighted,
        run-aware mid-rail dwell (see _mid_rail_dwell)."""
        vals = np.asarray(values, dtype=float)
        if self._is_constant(vals):
            # Constant at a single level: two-level degenerate case
            return True
        mean_mid, max_mid = self._mid_rail_dwell(vals)
        return mean_mid < 0.05 and max_mid < 0.50

    def _speckg_domain(self, name: str):
        """Domain ('digital'/'analog'/...) of the SpecKG port matching this
        (signal-map-renamed) signal name, or None if no port matches."""
        if self.spec_kg is None:
            return None
        for p in getattr(self.spec_kg, 'ports', []):
            if p.name == name:
                return p.domain
        return None

    def _classify_signals(self):
        self.digital_signals = []
        self.analog_signals = []
        self.constant_signals = []
        for name, vals in self.signals.items():
            if self._is_constant(vals):
                # Grounds/fixed rails (AVSS, PBKG, gnd!, ...) — no state info
                self.constant_signals.append(name)
                continue
            # SpecKG port domain, when known, overrides the waveform
            # heuristic (a signal_map-mapped port is ground truth).
            domain = self._speckg_domain(name)
            if domain == 'digital':
                self.digital_signals.append(name)
            elif domain == 'analog':
                self.analog_signals.append(name)
            elif self._is_bimodal(vals):
                self.digital_signals.append(name)
                if self.spec_kg is not None:
                    log.info("[capture] %s: no SpecKG port match — "
                             "waveform-classified as digital", name)
            else:
                self.analog_signals.append(name)
                if self.spec_kg is not None:
                    log.info("[capture] %s: no SpecKG port match — "
                             "waveform-classified as analog", name)

    def _fsm_port_names(self, which: str):
        """SpecKG FSM port names by causality role: 'input' (may drive
        states/guards) or 'output' (signature-only indicators). Falls back
        to the undirected list for SpecKG objects predating direction
        support."""
        if self.spec_kg is None:
            return []
        try:
            if which == 'output':
                return [p.name for p in self.spec_kg.get_fsm_output_ports()]
            return [p.name for p in self.spec_kg.get_fsm_input_ports()]
        except AttributeError:
            if which == 'output':
                return []
            try:
                return [p.name for p in self.spec_kg.get_fsm_relevant_ports()]
            except Exception:
                return []

    def _binarize_matrix(self, names):
        matrix = np.zeros((len(self.time), len(names)))
        for j, name in enumerate(names):
            vals = self.signals[name]
            valid = vals[~np.isnan(vals)]
            v_min, v_max = valid.min(), valid.max()
            if v_max - v_min < 1e-9:
                matrix[:, j] = float(valid[0] > 0.5)
            else:
                threshold = (v_min + v_max) / 2
                matrix[:, j] = (np.nan_to_num(vals, nan=v_min) > threshold).astype(float)
        return matrix, names, self.time

    def get_logic_signal_matrix(self):
        """Returns (matrix, names, time) — binary matrix of digital signals.

        When a SpecKG is attached and its FSM INPUT port names (enable/
        control/select signals, via signal_map renaming; direction from
        port_direction) are present among the captured digital signals, the
        matrix is restricted to those ports. This keeps the FSM state space
        spanned by the signals the spec says can CAUSE states — output/
        status indicator pins never enter this matrix (they are observed as
        per-state output signatures instead; see get_output_signal_matrix).
        Signals with no matching port fall back to waveform classification,
        used only when no spec input port is present at all."""
        names = list(self.digital_signals)
        if self.spec_kg is not None and names:
            input_names = self._fsm_port_names('input')
            output_names = set(self._fsm_port_names('output'))
            restricted = [n for n in names if n in input_names]
            if restricted:
                names = restricted
            else:
                # Waveform fallback (no spec input port captured) — still
                # never let a declared output indicator become a state bit.
                names = [n for n in names if n not in output_names]
                if names:
                    log.info("[capture] no SpecKG FSM input port among "
                             "digital signals — waveform-classified set "
                             "%s used as state signals", names)

        if not names:
            return np.zeros((len(self.time), 1)), ['_dummy'], self.time
        return self._binarize_matrix(names)

    def get_output_signal_matrix(self):
        """Returns (matrix, names, time) — binarized digital OUTPUT-
        direction FSM ports (status/ready/fault indicators). These signals
        are the DUT's observable effects: they are summarized per detected
        state as output signatures and consistency-checked, never used as
        state variables or guard features. Constant-classified outputs are
        included (an indicator stuck at one rail is itself a signature)."""
        n = len(self.time) if self.time is not None else 0
        out_ports = self._fsm_port_names('output')
        names = [nm for nm in self.digital_signals if nm in out_ports]
        names += [nm for nm in self.constant_signals
                  if nm in out_ports and nm not in names]
        if not names:
            return np.zeros((n, 0)), [], self.time
        return self._binarize_matrix(names)

    def get_analog_features(self, n_windows: int = 10):
        """Returns DataFrame of mean/std/slope per analog signal per time window.

        If this SignalCapture was loaded from a multi-run BLUT source
        (self.run_boundaries non-empty), windows are clipped to the nearest
        preceding run boundary so a window's mean/std/slope never blends
        two independent runs' statistics."""
        if not self.analog_signals:
            return None

        n = len(self.time)
        window_size = n // n_windows
        rows = []
        for w in range(n_windows):
            start = w * window_size
            end = min(start + window_size, n)
            if self.run_boundaries:
                for b in self.run_boundaries:
                    if start < b <= end:
                        end = b
                        break
            if end <= start:
                continue
            row = {'window': w, 't_start': self.time[start], 't_end': self.time[end - 1]}
            for name in self.analog_signals:
                vals = self.signals[name][start:end]
                valid = vals[~np.isnan(vals)] if np.issubdtype(vals.dtype, np.floating) else vals
                if valid.size == 0:
                    row[f'{name}_mean'] = 0.0
                    row[f'{name}_std'] = 0.0
                    row[f'{name}_slope'] = 0.0
                    continue
                row[f'{name}_mean'] = float(valid.mean())
                row[f'{name}_std'] = float(valid.std())
                # slope via linear regression
                x = np.arange(len(valid), dtype=float)
                if len(x) > 1:
                    coeffs = np.polyfit(x, valid, 1)
                    row[f'{name}_slope'] = float(coeffs[0])
                else:
                    row[f'{name}_slope'] = 0.0
            rows.append(row)

        if pd is not None:
            return pd.DataFrame(rows)
        # Fallback: return list of dicts
        return rows

    def export_to_csv(self, filepath: str):
        data = {'time': self.time}
        data.update(self.signals)
        if pd is not None:
            df = pd.DataFrame(data)
            df.to_csv(filepath, index=False)
        else:
            import csv
            cols = list(data.keys())
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=cols)
                writer.writeheader()
                for i in range(len(self.time)):
                    writer.writerow({c: data[c][i] for c in cols})
        print(f"[SignalCapture] Exported to {filepath}")
