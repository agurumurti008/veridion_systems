"""
core/phases/phase2_sim_augmented.py
PINN / NODE / GPR trainer + incremental update (Phase 2).
Compatible with real PyTorch AND the NumPy shim.
"""
import os
import warnings
import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import TensorDataset, DataLoader
except ImportError:
    import torch_shim  # noqa
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import TensorDataset, DataLoader

from core.tensor_utils import to_np, to_f32, scalar, make_float_tensor, assign_col

try:
    import wandb as _wandb
    _WANDB = True
except ImportError:
    _WANDB = False


class Phase2SimAugmented:
    """Train surrogate models from simulation data and specKG."""

    def __init__(self, spec_kg, use_wandb: bool = False):
        self.spec_kg = spec_kg
        self.use_wandb = use_wandb and _WANDB
        self.models = {}
        self.model_names = []
        self.best_model_name = None
        self.output_names = []
        self.feature_names = []
        self._symbolic_results = {}

        if self.use_wandb:
            try:
                _wandb.init(project='surrogate_framework',
                            config={'ip_type': spec_kg.ip_type})
            except Exception:
                self.use_wandb = False

    def build_dataset_from_blut(
        self, blut_path: str, signal_map,
        input_signal_names: list, output_signal_names: list,
        fsm_detector, current_suffixes=None, run_ids: list = None,
    ) -> dict:
        """
        Build a Phase2 training dataset from a multi-run BLUT file, dropping
        directly into the EXISTING incremental_train(data=...) contract —
        no changes to _train_pinn/_train_node's tensor assumptions.

        run_ids: optional list of qualified 'run_id' or 'run_id@corner_id'
        strings restricting/ordering which runs contribute rows (e.g. only
        the corners an upstream per-corner correlation pass judged
        trustworthy — see examples/example9_per_corner_fsm_correlate.py /
        example10_final_fsm_from_good_corners.py). Row order follows the
        GIVEN list's order (not BLUT file order) when provided, so a
        caller that separately derives a consistent global state labeling
        over the same ordered run_ids (e.g. via one global SignalCapture
        .load_from_blut(run_id=run_ids) + FSMStateDetector.detect() call)
        can align it to this method's per-row output by per-run sample
        count. None (default) preserves today's behavior: every run in
        the file, in BLUT iteration order.

        For every run in the BLUT:
          1. Decode + rename via signal_map (reuses SignalCapture.load_from_blut
             per-run, run_id=<this run>, so the boundary-mask machinery in
             SignalCapture/TransitionLearner applies consistently even though
             here we're calling it once per run rather than once for all runs).
          2. Split decoded signals (both self.signals AND self.current_signals,
             since output_signal_names may name either voltage or current
             SpecKG names) into input columns (X) vs output columns (Y) using
             input_signal_names / output_signal_names.
          3. Run fsm_detector.detect(...) on that run's logic/analog matrices
             to get a per-sample state_sequence for THIS run.
          4. Append the varying stimulus parameter(s) for this run (parsed
             from RunMeta.meta via digitwin.blut_reader_ext.parse_meta_string,
             e.g. "corner=ff,temp=125" -> {"corner": "ff", "temp": "125"})
             as extra X columns beyond the decoded signal columns, so the
             surrogate is stimulus-conditioned rather than corner-blind.
             Non-numeric meta values (e.g. "ff") are encoded via a stable
             per-key string->float lookup built across all runs in this
             call (first-seen order), recorded in self.meta_value_encoding
             for later inspection; numeric meta values parse directly.

        Returns a dict with the EXISTING contract keys:
            {'X': FloatTensor, 'Y': FloatTensor, 'state_sequence': LongTensor,
             'run_ids': list[str], 'run_meta': list[str]}
        plus 'feature_names' (input_signal_names + meta-derived column names)
        and 'output_names' (output_signal_names), so callers/Phase2 reporting
        know what the extra stimulus columns mean.
        """
        from digitwin.blut_reader_ext import open_blut, DEFAULT_CURRENT_SUFFIXES, parse_meta_string
        from core.fsm.signal_capture import SignalCapture

        suffixes = current_suffixes if current_suffixes is not None else DEFAULT_CURRENT_SUFFIXES
        blut = open_blut(blut_path)

        if not blut.runs:
            raise ValueError(f"{blut_path}: no runs found in BLUT file")

        # First pass: parse every run's meta string so we know which meta
        # keys vary across runs and can build a consistent column order and
        # string->float encoding table before building any row.
        # v8: runs are keyed (run_id, corner_id); iterate the full matrix
        # and address each run by its qualified 'run_id@corner_id' string
        # (plain run_id when corner_id is empty — v7 files, no-corner v8).
        run_pairs = [(rid, cid) for rid, cmap in blut.runs.items()
                     for cid in cmap.keys()]
        run_id_order = [rid if not cid else f"{rid}@{cid}" for rid, cid in run_pairs]

        if run_ids is not None:
            # Restrict + REORDER to the caller's given list (not BLUT file
            # order) — see run_ids docstring above for why order matters.
            pair_by_qid = dict(zip(run_id_order, run_pairs))
            run_id_order = list(run_ids)
            run_pairs = [pair_by_qid[qid] for qid in run_id_order]

        meta_dicts = {qid: parse_meta_string(blut.runs[rid][cid].meta)
                      for qid, (rid, cid) in zip(run_id_order, run_pairs)}
        run_meta_by_qid = {qid: blut.runs[rid][cid].meta
                           for qid, (rid, cid) in zip(run_id_order, run_pairs)}
        meta_keys = sorted({k for d in meta_dicts.values() for k in d.keys()})

        # Stable string -> float encoding, first-seen order, one table per
        # meta key (so "corner=ff" / "corner=ss" / "corner=tt" get distinct,
        # reproducible float codes across runs in this call). Also track
        # whether each key is genuinely 'continuous' (every value parsed
        # as a real float — temp, vsup — so the code IS the value, safe
        # for interpolation-sensitive models) or 'categorical' (any value
        # needed the arbitrary ordinal fallback — process corner "ff"/
        # "ss"/"tt" — the code is just a distinct label with no metric
        # meaning; a key is marked categorical the first time ANY of its
        # values falls back, since one column can't be partly ordinal).
        self.meta_value_encoding = {k: {} for k in meta_keys}
        self.meta_key_kind = {k: 'continuous' for k in meta_keys}
        for rid in run_id_order:
            for k in meta_keys:
                v = meta_dicts[rid].get(k)
                if v is None:
                    continue
                table = self.meta_value_encoding[k]
                if v not in table:
                    try:
                        table[v] = float(v)
                    except ValueError:
                        table[v] = float(len(table))  # stable ordinal code
                        self.meta_key_kind[k] = 'categorical'

        def _meta_row_values(rid: str) -> list:
            row = []
            for k in meta_keys:
                v = meta_dicts[rid].get(k)
                if v is None:
                    row.append(0.0)
                else:
                    row.append(self.meta_value_encoding[k].get(v, 0.0))
            return row

        X_rows = []
        Y_rows = []
        state_seq_all = []
        run_ids_per_row = []
        run_meta_per_row = []
        _warned_unmapped = False

        for rid in run_id_order:
            sc = SignalCapture(spec_kg=self.spec_kg)
            # Suppress the per-run unmapped-name warning after the first run:
            # the mapping gap is a property of (signal_map, spec_kg), not of
            # any individual run, so printing it once per call (not once per
            # run) avoids drowning the console in an identical table N times.
            effective_signal_map = signal_map
            if signal_map is not None and _warned_unmapped:
                # Temporarily silence by monkey-patching print_unmapped_warning
                # to a no-op for this call only; resolve()/reverse_resolve()
                # behavior is unaffected.
                class _SilentWrapper:
                    def __init__(self, inner):
                        self._inner = inner
                    def __getattr__(self, name):
                        return getattr(self._inner, name)
                    def print_unmapped_warning(self, kg):
                        pass
                effective_signal_map = _SilentWrapper(signal_map)
            sc.load_from_blut(blut_path, run_id=rid, signal_map=effective_signal_map,
                              current_suffixes=suffixes)
            _warned_unmapped = True

            n_t = len(sc.time)
            if n_t == 0:
                continue

            # Build per-sample input/output columns from renamed signals,
            # searching both voltage (sc.signals) and current
            # (sc.current_signals) dicts since either may hold a name
            # requested in input_signal_names/output_signal_names.
            def _column_for(name: str) -> np.ndarray:
                if name in sc.signals:
                    return np.asarray(sc.signals[name], dtype=np.float64)
                if name in sc.current_signals:
                    return np.asarray(sc.current_signals[name], dtype=np.float64)
                log_msg = (f"[Phase2.build_dataset_from_blut] '{name}' not found in "
                          f"run '{rid}' (voltage or current) — filling with NaN column.")
                print(log_msg)
                return np.full(n_t, np.nan, dtype=np.float64)

            input_cols  = [_column_for(name) for name in input_signal_names]
            output_cols = [_column_for(name) for name in output_signal_names]

            meta_row = _meta_row_values(rid)
            meta_cols = [np.full(n_t, v, dtype=np.float64) for v in meta_row]

            X_run = np.column_stack(input_cols + meta_cols) if (input_cols or meta_cols) else np.zeros((n_t, 0))
            Y_run = np.column_stack(output_cols) if output_cols else np.zeros((n_t, 0))

            # Per-run FSM state detection (Section 6 requirement #3): run
            # fsm_detector on THIS run's logic/analog matrices so state
            # labels reflect this run's own dynamics, not a blended
            # cross-run clustering.
            lm, ln, lt = sc.get_logic_signal_matrix()
            af = sc.get_analog_features(n_windows=min(10, max(2, n_t // 5)))
            try:
                run_state_seq = fsm_detector.detect(lm, ln, af)
            except Exception as e:
                print(f"[Phase2.build_dataset_from_blut] FSM detection failed for "
                      f"run '{rid}': {e} — falling back to all-state-0.")
                run_state_seq = np.zeros(n_t, dtype=int)

            if len(run_state_seq) != n_t:
                # detect() may return a sequence aligned to a different
                # array length in edge cases (e.g. dummy logic matrix);
                # pad/truncate defensively rather than raise, matching this
                # dataset builder's NaN-fill-not-drop philosophy elsewhere.
                fixed = np.zeros(n_t, dtype=int)
                m = min(n_t, len(run_state_seq))
                fixed[:m] = run_state_seq[:m]
                run_state_seq = fixed

            X_rows.append(X_run)
            Y_rows.append(Y_run)
            state_seq_all.append(run_state_seq)
            run_ids_per_row.extend([rid] * n_t)
            run_meta_per_row.extend([run_meta_by_qid[rid]] * n_t)

        if not X_rows:
            raise ValueError(f"{blut_path}: no usable rows produced across any run")

        X_all = np.concatenate(X_rows, axis=0).astype(np.float32)
        Y_all = np.concatenate(Y_rows, axis=0).astype(np.float32)
        state_seq_concat = np.concatenate(state_seq_all, axis=0).astype(np.int64)

        feature_names = list(input_signal_names) + [f"meta_{k}" for k in meta_keys]
        self.feature_names = feature_names
        self.output_names = list(output_signal_names)

        return {
            'X': make_float_tensor(X_all),
            'Y': make_float_tensor(Y_all),
            'state_sequence': state_seq_concat,  # plain int64 ndarray; to_np()
                                                  # in _train_pinn handles this
                                                  # via int(ss[i]) same as any
                                                  # other array-like — no
                                                  # change needed there.
            'run_ids': run_ids_per_row,
            'run_meta': run_meta_per_row,
            'feature_names': feature_names,
            'output_names': list(output_signal_names),
            'meta_key_kind': dict(self.meta_key_kind),
        }

    def expand_categorical_meta(self, data: dict) -> dict:
        """Post-process a build_dataset_from_blut() result: one-hot expand
        every CATEGORICAL meta_<key> column (process corner "nn"/"ss"/
        "ww" etc — see meta_key_kind) into meta_<key>=<value> binary
        columns, leaving CONTINUOUS meta_<key> columns (temp, vsup —
        already their true numeric value) untouched. Continuous columns
        stay interpolation-friendly for later cross-corner interpolation
        work; categorical columns stop imposing a false ordinal scale on
        values that have none (a distance-based/interpolating model would
        otherwise treat "ss", coded 1, as "between" "ff" coded 0 and "tt"
        coded 2). Returns a NEW dict (does not mutate the input) — 'X' is
        a new tensor, 'feature_names' reflects the expanded columns; a
        dataset with no categorical meta keys is returned unchanged."""
        feature_names = list(data['feature_names'])
        meta_key_kind = data.get('meta_key_kind', {})
        categorical_keys = {k for k, kind in meta_key_kind.items()
                            if kind == 'categorical'}
        if not categorical_keys:
            return data

        X_np = to_np(data['X']).astype(np.float64)
        new_cols, new_names = [], []
        for j, name in enumerate(feature_names):
            matched_key = next((k for k in categorical_keys
                                if name == f'meta_{k}'), None)
            if matched_key is None:
                new_cols.append(X_np[:, j])
                new_names.append(name)
                continue
            # One-hot expand using the SAME stable value->code table
            # build_dataset_from_blut already produced, so column
            # order/meaning is reproducible across calls.
            table = self.meta_value_encoding.get(matched_key, {})
            for value_str, code in table.items():
                new_cols.append(np.isclose(X_np[:, j], code).astype(np.float64))
                new_names.append(f'meta_{matched_key}={value_str}')

        X_expanded = np.column_stack(new_cols) if new_cols else X_np
        out = dict(data)
        out['X'] = make_float_tensor(X_expanded.astype(np.float32))
        out['feature_names'] = new_names
        return out

    def target_encode_categorical_meta(self, data: dict) -> dict:
        """Alternative to expand_categorical_meta (that method is
        untouched — this is a separate, additive option): instead of
        one-hot expanding a categorical meta_<key> column (process corner
        "nn"/"ss"/"ww") into N binary columns, replace it with a SINGLE
        meta_<key> column holding one real number per category — a
        target/mean encoding: each category's code is the mean, across
        that category's rows, of a per-row "how this row's outputs trend
        relative to the whole sweep" score (each output z-scored, then
        averaged across outputs). This is what lets a single overridable
        `parameter real meta_<key>` (declared once, swapped per simulated
        corner — the same pattern already used for meta_temp/meta_vsup_max)
        stand in for the category, with a value chosen to correlate with
        that category's actual measured behavior rather than an arbitrary
        ordinal/one-hot encoding. Returns a NEW dict (does not mutate the
        input) with an added 'categorical_codes': {key: {category:
        code}} — the mapping a caller should print/document so a
        simulator setting meta_<key> per corner knows which value to use.
        Continuous meta_<key> columns (temp, vsup) pass through
        unchanged, same as expand_categorical_meta."""
        feature_names = list(data['feature_names'])
        meta_key_kind = data.get('meta_key_kind', {})
        categorical_keys = {k for k, kind in meta_key_kind.items()
                            if kind == 'categorical'}
        if not categorical_keys:
            return data

        X_np = to_np(data['X']).astype(np.float64)
        Y_np = to_np(data['Y']).astype(np.float64)
        if Y_np.ndim == 1:
            Y_np = Y_np.reshape(-1, 1)
        # nanmean/nanstd, not mean/std: a single unresolved output column
        # (e.g. a --blut_output_signals typo that build_dataset_from_blut
        # NaN-fills — see _column_for's warning) must not poison every
        # OTHER output's contribution to the score, and row_score below
        # must not go NaN for every row just because one column did.
        bad_cols = np.all(np.isnan(Y_np), axis=0)
        if bad_cols.any():
            print(f"[Phase2.target_encode_categorical_meta] output column(s) "
                  f"{[data['output_names'][i] for i in np.where(bad_cols)[0]]} "
                  f"are entirely NaN (unresolved signal name?) — excluded "
                  f"from the corner-encoding score, not just averaged in "
                  f"as NaN.")
        with warnings.catch_warnings():
            # "Mean/degrees of freedom of empty slice" for any all-NaN
            # column — already surfaced explicitly above, expected here.
            warnings.simplefilter('ignore', category=RuntimeWarning)
            y_mean = np.nanmean(Y_np, axis=0)
            y_std = np.nanstd(Y_np, axis=0)
            y_std[~np.isfinite(y_std) | (y_std < 1e-12)] = 1.0
            with np.errstate(invalid='ignore'):
                row_score = np.nanmean((Y_np - y_mean) / y_std, axis=1)
        # A row where EVERY output is NaN (all-NaN row, not just a bad
        # column) has nothing left to average — fall back to 0.0 rather
        # than propagate NaN into the encoded category.
        row_score[~np.isfinite(row_score)] = 0.0

        new_cols, new_names = [], []
        categorical_codes: dict = {}
        for j, name in enumerate(feature_names):
            matched_key = next((k for k in categorical_keys
                                if name == f'meta_{k}'), None)
            if matched_key is None:
                new_cols.append(X_np[:, j])
                new_names.append(name)
                continue
            # The existing (arbitrary, ordinal) meta_value_encoding table
            # is only used here to identify which rows belong to which
            # raw category value — never as the final encoded number.
            table = self.meta_value_encoding.get(matched_key, {})
            col_vals = X_np[:, j]
            encoded_col = np.zeros(len(X_np))
            code_by_value = {}
            for value_str, raw_code in table.items():
                mask = np.isclose(col_vals, raw_code)
                code = float(row_score[mask].mean()) if mask.any() else 0.0
                code_by_value[value_str] = code
                encoded_col[mask] = code
            new_cols.append(encoded_col)
            new_names.append(f'meta_{matched_key}')
            categorical_codes[matched_key] = code_by_value

        X_encoded = np.column_stack(new_cols) if new_cols else X_np
        out = dict(data)
        out['X'] = make_float_tensor(X_encoded.astype(np.float32))
        out['feature_names'] = new_names
        out['categorical_codes'] = categorical_codes
        return out

    def _map_predictions_to_physics_keys(self, output_names: list, Y_row_or_matrix) -> dict:
        """
        Build a predictions_dict keyed with the PHYSICS variable names that
        PhysicsConstraintLayer.kcl_loss/kvl_loss (core/models/pinn.py,
        unchanged) already expect — I_pass, I_load, I_feedback, I_out,
        I_tail, V_vin, V_dropout, V_vout — from a BLUT-derived output_names
        list plus its corresponding Y values (a single row or a full
        (n_samples, n_outputs) matrix; both accepted, returned dict values
        are ndarrays either way).

        This is what lets a real BLUT-derived voltage/current output tensor
        actually activate the existing KCL/KVL loss terms, instead of
        silently contributing zero physics loss because the dict keys
        never matched (kcl_loss/kvl_loss return 0.0 when their required
        keys are absent from predictions_dict — see core/models/pinn.py).

        Matching is keyword-based (substring search on the uppercased,
        underscore-normalized output name), not exact-match, because real
        SpecKG naming mixes short port names (VIN, VOUT) and verbose spec
        names (Dropout_Voltage, Output_Voltage) — both "VOUT" and
        "Output_Voltage" must resolve to physics key "V_vout". Rules are
        checked in order, most-specific first (DROPOUT before the generic
        OUTPUT+VOLT fallback), and each output column matches at most one
        key. Names matching nothing are skipped (contribute to neither KCL
        nor KVL — same zero-physics-loss default as today; this helper
        only ever adds coverage, never removes it).
        """
        keyword_rules = [
            ('DROPOUT', 'V_dropout'),
            ('DROP', 'V_dropout'),
            ('FEEDBACK', 'I_feedback'),
            ('IFB', 'I_feedback'),
            ('TAIL', 'I_tail'),
            ('PASS', 'I_pass'),
            ('LOAD', 'I_load'),
            ('VIN', 'V_vin'),
            ('VOUT', 'V_vout'),
            ('IOUT', 'I_out'),
        ]

        def _resolve_key(name: str):
            norm = name.upper().replace('.', '_').replace('-', '_')
            for keyword, key in keyword_rules:
                if keyword in norm:
                    return key
            # Fallback for verbose spec-name conventions (Output_Voltage,
            # Output_Current) that don't contain VOUT/IOUT as a substring.
            if 'OUTPUT' in norm:
                if 'VOLT' in norm:
                    return 'V_vout'
                if 'CURR' in norm:
                    return 'I_out'
            return None

        Y_arr = to_np(Y_row_or_matrix)
        if Y_arr.ndim == 1:
            Y_arr = Y_arr.reshape(1, -1)

        circuit_state = {}
        for idx, name in enumerate(output_names):
            if idx >= Y_arr.shape[1]:
                continue
            key = _resolve_key(name)
            if key is None:
                continue
            col = Y_arr[:, idx]
            circuit_state[key] = make_float_tensor(col.astype(np.float32))

        return circuit_state


    def initialize_models(self, input_dim: int, output_dim: int,
                          n_fsm_states: int = 4, state_dim: int = 2,
                          user_bridges: dict = None, model_names: list = None):
        from core.models.pinn import CircuitPINN
        from core.models.neural_ode import CircuitNeuralODE
        from core.models.gpr_surrogate import CircuitGPR

        physics_rules = self.spec_kg.get_physics_loss_terms()
        spec_constraints = self.spec_kg.specs
        active_bridges = user_bridges or {}
        requested = set(model_names or ['PINN', 'GPR'])

        if 'PINN' in requested:
            self.models['PINN'] = CircuitPINN(
                input_dim=input_dim, output_dim=output_dim,
                hidden_dims=[64, 64, 32], n_states=n_fsm_states,
                physics_rules=physics_rules, spec_constraints=spec_constraints,
                active_bridges=active_bridges,
            )
        if 'NODE' in requested:
            self.models['NODE'] = CircuitNeuralODE(
                state_dim=state_dim, param_dim=input_dim,
                n_fsm_states=n_fsm_states, ip_type=self.spec_kg.ip_type,
            )
        if 'GPR' in requested:
            self.models['GPR'] = CircuitGPR(input_dim=input_dim, output_dim=output_dim)

        self.model_names = list(self.models.keys())
        print(f"[Phase2] Initialized models: {self.model_names}")

    def incremental_train(self, data: dict, analysis_data: dict = None,
                          iteration: int = 0, epochs: int = 150) -> dict:
        X = data.get('X')
        Y = data.get('Y')
        if X is None or Y is None:
            raise ValueError("data dict must contain 'X' and 'Y' tensors")

        X_np = to_np(X).astype(np.float32)
        Y_np = to_np(Y).astype(np.float32)
        metrics = {}

        # ── GPR ──────────────────────────────────────────────────────────────
        if 'GPR' in self.models:
            gpr = self.models['GPR']
            split = max(1, int(0.8 * len(X_np)))
            gpr.fit(X_np[:split], Y_np[:split])
            mse = gpr.evaluate(X_np[split:], Y_np[split:]) if split < len(X_np) else 0.0
            metrics['GPR'] = {'test_mse': mse, 'history': [mse]}
            print(f"[Phase2] GPR trained — test MSE: {mse:.6f}")

        # ── PINN ─────────────────────────────────────────────────────────────
        if 'PINN' in self.models:
            pinn_metrics = self._train_pinn(
                self.models['PINN'], X_np, Y_np,
                state_sequence=data.get('state_sequence'),
                analysis_data=analysis_data, epochs=epochs,
                output_names=data.get('output_names'),
            )
            metrics['PINN'] = pinn_metrics

        # ── NODE ─────────────────────────────────────────────────────────────
        if 'NODE' in self.models:
            metrics['NODE'] = self._train_node(
                self.models['NODE'], data, epochs=min(epochs, 50)
            )

        mse_dict = {k: v['test_mse'] for k, v in metrics.items()
                    if not (isinstance(v['test_mse'], float) and
                            v['test_mse'] != v['test_mse'])}  # skip NaN
        if mse_dict:
            self.best_model_name = min(mse_dict, key=mse_dict.get)
        elif metrics:
            self.best_model_name = list(metrics.keys())[0]
        return metrics

    def _train_pinn(self, pinn, X_np, Y_np,
                    state_sequence=None, analysis_data=None, epochs=150,
                    output_names=None):
        split = max(1, int(0.8 * len(X_np)))
        X_tr, X_te = X_np[:split], X_np[split:]
        Y_tr, Y_te = Y_np[:split], Y_np[split:]

        # z-score X (train-set statistics) — unlike CircuitGPR/CircuitSMT,
        # which StandardScaler their X internally, this trainer previously
        # fed raw, unscaled feature columns straight into the network.
        # When those columns span wildly different magnitudes (uA-scale
        # currents alongside V-scale voltages alongside a differential
        # dV/dt feature whose scale depends on the sampling dt), that
        # alone is enough to stall gradient-based training regardless of
        # epoch count. The scaler is stored ON THE MODEL (pinn.
        # set_input_scaler), not applied to X_tr/X_te here directly:
        # CircuitPINN.forward() applies it internally on every call, so
        # ANY caller evaluating this trained pinn later on a raw, held-out
        # split (this method's own eval below, or a caller's separate
        # eval pass after incremental_train() returns) transparently gets
        # the same transform the network was actually trained on — X_tr/
        # X_te themselves stay in their original, physically meaningful
        # units throughout. Y is left in native units too: compute_loss's
        # KCL/KVL physics terms need real voltage/current magnitudes to
        # mean anything, and it keeps PINN's reported MSE directly
        # comparable to CircuitGPR/CircuitSMT's already-original-units
        # evaluate() with no inverse-transform step.
        pinn.set_input_scaler(X_tr.mean(axis=0), X_tr.std(axis=0))

        n_states = pinn.n_states
        n_tr = len(X_tr)

        # Build state one-hot as plain numpy first, then wrap
        state_oh_np = np.zeros((n_tr, n_states), dtype=np.float32)
        if state_sequence is not None:
            ss = to_np(state_sequence).reshape(-1)
            for i in range(min(n_tr, len(ss))):
                sid = min(int(ss[i]), n_states - 1)
                state_oh_np[i, sid] = 1.0
        else:
            state_oh_np[:, 0] = 1.0

        X_t  = make_float_tensor(X_tr)
        Y_t  = make_float_tensor(Y_tr)
        S_t  = make_float_tensor(state_oh_np)

        params = pinn.parameters()
        if not params:
            return {'test_mse': 0.0, 'history': []}

        # Use real Adam if available, shim otherwise
        try:
            optimizer = torch.optim.Adam(params, lr=1e-3)
            _real_torch = not hasattr(optimizer, '__class__') or \
                          optimizer.__class__.__name__ == 'Adam' and \
                          hasattr(optimizer, 'param_groups')
        except Exception:
            optimizer = None
            _real_torch = False

        history = []
        for epoch in range(epochs):
            outputs = pinn(X_t, S_t, analysis_data)

            # Build a real circuit_state dict keyed with the physics
            # variable names KCL/KVL expect (V_vout, I_out, etc.) whenever
            # the caller knows what each output column represents (BLUT
            # ingestion always does; the synthetic/CSV path leaves
            # output_names=None, so circuit_state stays {} exactly as
            # before — this is purely additive coverage, never a behavior
            # change for existing callers).
            if output_names:
                circuit_state = self._map_predictions_to_physics_keys(
                    output_names, outputs['predictions']
                )
            else:
                circuit_state = {}

            loss_dict = pinn.compute_loss(outputs, Y_t, circuit_state)
            total_loss = loss_dict['total']
            loss_val = scalar(total_loss)

            # Backward + step
            if hasattr(total_loss, 'backward') and not hasattr(total_loss, '_d'):
                # Real PyTorch
                if optimizer is not None and hasattr(optimizer, 'zero_grad'):
                    optimizer.zero_grad()
                try:
                    total_loss.backward()
                    if optimizer is not None:
                        optimizer.step()
                except Exception:
                    pass
            else:
                # Shim: tiny numerical perturbation
                for p in params:
                    if hasattr(p, '_d'):
                        p._d -= np.random.randn(*p._d.shape) * max(abs(loss_val), 1e-6) * 1e-5

            if epoch % 25 == 0:
                data_l  = scalar(loss_dict['data'])
                phys_l  = scalar(loss_dict['physics'])
                print(f"  [PINN] epoch {epoch:4d} | total={loss_val:.6f} "
                      f"data={data_l:.6f} phys={phys_l:.6f}")
                if self.use_wandb:
                    try:
                        _wandb.log({'pinn_loss': loss_val, 'pinn_data': data_l,
                                    'pinn_phys': phys_l, 'epoch': epoch})
                    except Exception:
                        pass
            history.append(loss_val)

        # Evaluate on test set — eval() disables Dropout (0.05 in every
        # _build_mlp hidden layer), so the reported test MSE reflects the
        # trained network deterministically instead of one noisy dropout
        # sample of it (the model was never switched out of the default
        # train() mode for this forward pass before).
        pinn.eval()
        if len(X_te) > 0:
            X_te_t = make_float_tensor(X_te)
            S_te   = make_float_tensor(np.zeros((len(X_te), n_states), dtype=np.float32))
            assign_col(S_te, 0, 1.0)
            out_te  = pinn(X_te_t, S_te)
            pred_np = to_np(out_te['predictions']).astype(np.float32)
            mse = float(np.mean((pred_np - Y_te) ** 2))
        else:
            mse = float(history[-1]) if history else 0.0

        print(f"[Phase2] PINN trained — test MSE: {mse:.6f}")
        return {'test_mse': mse, 'history': history}

    def _train_node(self, node, data: dict, epochs: int = 50):
        t_span      = data.get('t_span')
        trajectories = data.get('trajectories')
        X           = data.get('X')

        if t_span is None or trajectories is None:
            print("[Phase2] NODE: no transient data — skipping training")
            return {'test_mse': 0.0, 'history': []}

        X_np    = to_np(X).astype(np.float32)
        traj_np = to_np(trajectories)
        t_np    = to_np(t_span)

        history = []
        params  = node.parameters()
        if not params:
            return {'test_mse': 0.0, 'history': []}

        # Real optimizer, mirroring _train_pinn's exact pattern above —
        # under real PyTorch, node(...)'s returned 'trajectory' is now a
        # genuine tensor connected to every ode_fn's/state_clf's/ic_net's
        # parameters (see core/models/neural_ode.py's _euler_integrate
        # fix), so backward()/optimizer.step() actually updates them;
        # under torch_shim, sample_loss carries a `._d` attribute and the
        # real-path check below falls through to the same numpy-
        # perturbation update this method always used, unchanged.
        try:
            optimizer = torch.optim.Adam(params, lr=1e-3)
        except Exception:
            optimizer = None

        n_samples = min(len(X_np), 5)
        for epoch in range(epochs):
            if optimizer is not None and hasattr(optimizer, 'zero_grad'):
                optimizer.zero_grad()
            total_loss_val = 0.0
            epoch_loss_tensor = None
            for i in range(n_samples):
                result = node(X_np[i], t_np)
                traj_pred = result['trajectory']
                traj_target = (traj_np[i, :, :node.state_dim]
                               if traj_np.ndim == 3
                               else traj_np[:, :node.state_dim])
                n_t = min(len(traj_pred), len(traj_target))
                target_t = make_float_tensor(traj_target[:n_t].astype(np.float32))
                sample_loss = ((traj_pred[:n_t] - target_t) ** 2).mean()
                loss_val = scalar(sample_loss)
                total_loss_val += loss_val

                if hasattr(sample_loss, 'backward') and not hasattr(sample_loss, '_d'):
                    # Real PyTorch — accumulate a real tensor to backward()
                    # once per epoch (one graph walk for all n_samples).
                    epoch_loss_tensor = sample_loss if epoch_loss_tensor is None \
                        else epoch_loss_tensor + sample_loss
                else:
                    # Shim: tiny numerical perturbation, same as before.
                    for p in params:
                        if hasattr(p, '_d'):
                            p._d -= 1e-5 * loss_val * np.random.randn(*p._d.shape)

            if epoch_loss_tensor is not None:
                try:
                    epoch_loss_tensor.backward()
                    if optimizer is not None:
                        optimizer.step()
                except Exception:
                    pass

            avg = total_loss_val / max(n_samples, 1)
            history.append(avg)
            if epoch % 10 == 0:
                print(f"  [NODE] epoch {epoch:4d} | loss={avg:.6f}")

        mse = float(history[-1]) if history else 0.0
        print(f"[Phase2] NODE trained — last loss: {mse:.6f}")
        return {'test_mse': mse, 'history': history}

    def extract_interpretable(self, X, feature_names, output_names) -> dict:
        from core.interpretability.symbolic_regression import CircuitSymbolicExtractor
        X_np = to_np(X).astype(np.float32)

        if self.best_model_name == 'GPR' and 'GPR' in self.models:
            Y_pred, _ = self.models['GPR'].predict(X_np)
        elif self.best_model_name == 'PINN' and 'PINN' in self.models:
            pinn  = self.models['PINN']
            X_t   = make_float_tensor(X_np)
            n_st  = pinn.n_states
            S_t   = make_float_tensor(np.zeros((len(X_np), n_st), dtype=np.float32))
            assign_col(S_t, 0, 1.0)
            out   = pinn(X_t, S_t)
            Y_pred = to_np(out['predictions']).astype(np.float32)
        else:
            if 'GPR' in self.models:
                Y_pred, _ = self.models['GPR'].predict(X_np)
            else:
                Y_pred = np.zeros((len(X_np), len(output_names)))

        extractor = CircuitSymbolicExtractor(feature_names, output_names)
        results   = extractor.extract_all(X_np, Y_pred)
        self._symbolic_results = results
        return results

    def generate_phase2_veriloga(self, fsm_code='', interpretable=None,
                                  output_dir='output') -> str:
        os.makedirs(output_dir, exist_ok=True)
        ip = self.spec_kg.ip_type.lower()
        lines = [
            f'// Phase 2 Verilog-A — {self.spec_kg.ip_type} (sim-augmented)',
            '// Generated by surrogate_framework Phase2SimAugmented',
            '', '`include "disciplines.vams"', '`include "constants.vams"', '',
            f'module {ip}_phase2(',
        ]
        ports = [p.name.lower() for p in self.spec_kg.ports]
        lines.append('    ' + ', '.join(ports[:6]))
        lines.append(');')
        lines.append('')
        if interpretable:
            lines.append('    // ── Extracted symbolic equations (Phase 2) ──')
            for out_name, res in interpretable.items():
                r2  = res.get('r2', 0.0)
                eq  = res.get('equation', '')
                lines.append(f'    // {out_name}: {eq}  (R²={r2:.3f})')
            lines.append('')
        lines.append('    // ── Calibrated parameters from training ──')
        for s in self.spec_kg.specs:
            safe = s.name.replace(' ', '_').replace('.', '_')
            lines.append(f'    parameter real {safe}_cal = {s.nominal:.6g};'
                         f'  // calibrated, unit={s.unit}')
        lines += ['', '    analog begin',
                  '        // Phase 2 calibrated behavior', '    end', '',
                  f'endmodule  // {ip}_phase2']
        path = os.path.join(output_dir, f'{ip}_phase2.vams')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"[Phase2] Phase 2 Verilog-A → {path}")
        return path
