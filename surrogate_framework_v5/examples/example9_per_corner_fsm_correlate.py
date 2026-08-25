#!/usr/bin/env python3
"""
examples/example9_per_corner_fsm_correlate.py — independent FSM generation
per (run_id, corner_id) in a multi-corner BLUT file, plus a cross-corner
correlation/outlier report to flag which corners' results look anomalous
(likely truncated/incomplete simulation data, or a real FSM/DUT failure)
rather than treating the whole file as one blended dataset.

Reuses Phase2SimAugmented.build_dataset_from_blut's per-run loop skeleton
(open_blut -> iterate (run_id, corner_id) pairs -> fresh SignalCapture per
run) rather than new BLUT-iteration code. Detection is independent per
corner (not one global detection sliced by run boundary) so a corner's own
local incompleteness surfaces instead of being blended into a shared
global state space.

Naming convention this script does NOT assume (BLUT files vary):
  - run_id is the TEST CASE / scenario name (e.g. "TC_004_LDO_MuxSwitch_
    HPMToggle_EnLDO_Cycling") — many corner_ids share one run_id.
  - corner_id carries the actual PVT/supply point, in whatever free-form
    convention the regression generator used (e.g.
    "proc_nn_temp_125_vsup_maxproc_5.5") — NOT guaranteed standardized
    across BLUT files.
  - RunMeta.meta is a comma-separated "key=value[,key=value...]" string
    that may carry the SAME dimensions as corner_id (redundantly), a
    DIFFERENT/richer set (more sweep variables than just process/temp/
    vsup), or — on at least one real fixture seen in this codebase's
    history — a stale, near-constant value that doesn't track the actual
    corner at all. This script trusts neither source blindly: it parses
    both, merges them (meta wins on key collisions, since it's
    structured key=value and generalizes to however many sweep variables
    a regression uses — see resolve_corner_dims), and separately detects
    the "meta is suspiciously constant across an entire run_id's corners"
    smell so a bad meta field doesn't silently corrupt correlation.
  - A permanent fix belongs in BLUT generation (standardizing on
    corner_id + meta agreeing, both carrying every sweep variable). This
    script is the defensive/diagnostic layer until then.

Outlier philosophy: a corner is flagged relative to its SIBLING corners
under the same run_id (test case), not against a global reference or an
arbitrary row. Different test cases legitimately exercise different
stimulus/state-space complexity, so comparing across test cases (or
against whichever corner happened to be processed first) both over- and
under-flags. See group_outliers().

Run:  uv run examples/example9_per_corner_fsm_correlate.py \\
          [--blut_path PATH] [--spec_json PATH] [--signal_map_json PATH] \\
          [--fsm_strategy hybrid] [--fsm_tree_depth 4] \\
          [--ip_type LDO] [--output_dir output]
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import torch  # noqa: F401
except ImportError:
    import torch_shim  # noqa: F401

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = os.path.join(ROOT, 'configs')

MIN_GROUP_FOR_MAJORITY = 3   # below this, "majority" isn't statistically meaningful
MAJORITY_FRACTION = 0.5      # mode must exceed this fraction of the group to count


def _sanitize(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]', '_', name)


def parse_corner_id_heuristic(corner_id: str) -> dict:
    """Best-effort key/value extraction from a free-form corner_id, e.g.
    'proc_nn_temp_125_vsup_maxproc_5.5' -> {'proc': 'nn', 'temp': '125',
    'vsup_maxproc': '5.5'}. NOT guaranteed correct for every naming
    convention (the caller is told this in the module docstring) — a
    token is treated as a VALUE if it contains a digit or is a short
    (<=2 char) pure-alpha code (covers 2-letter process corners like nn/
    ss/ww/tt/ff); consecutive non-value tokens accumulate into that
    value's key. Advisory/reporting use only — never load-bearing for the
    outlier algorithm itself, which compares corners by measured
    behavior (n_states, validation results, signal counts), not by how
    well this parser understood their names."""
    if not corner_id:
        return {}
    tokens = [t for t in corner_id.split('_') if t]
    result = {}
    key_parts = []
    for tok in tokens:
        looks_like_value = bool(re.search(r'\d', tok)) or (tok.isalpha() and len(tok) <= 2)
        if looks_like_value:
            key = '_'.join(key_parts) if key_parts else f'field_{len(result)}'
            result[key] = tok
            key_parts = []
        else:
            key_parts.append(tok)
    return result


def resolve_corner_dims(meta_raw: str, corner_id: str):
    """Merge meta-derived and corner_id-derived dimension dicts (meta wins
    on key collisions — it's structured key=value and already generalizes
    to however many sweep variables a regression uses, via the existing
    parse_meta_string; corner_id parsing is the best-effort fallback/
    supplement). Returns (merged_dict, source_label, meta_dict, cid_dict)."""
    from digitwin.blut_reader_ext import parse_meta_string
    meta_dict = parse_meta_string(meta_raw)
    cid_dict = parse_corner_id_heuristic(corner_id)
    merged = {**cid_dict, **meta_dict}
    if meta_dict and cid_dict:
        source = 'meta+corner_id'
    elif meta_dict:
        source = 'meta'
    elif cid_dict:
        source = 'corner_id'
    else:
        source = 'none'
    return merged, source, meta_dict, cid_dict


def iqr_low_outliers(values: list) -> set:
    """Indices whose value is below Q1 - 1.5*IQR (classic low-side IQR
    rule) — simple, defensible, no exotic statistics for what is
    diagnostic tooling, not a research pipeline. Needs >=4 points to be
    meaningful; returns empty otherwise."""
    arr = np.asarray(values, dtype=float)
    if len(arr) < 4:
        return set()
    q1, q3 = np.percentile(arr, [25, 75])
    iqr = q3 - q1
    low = q1 - 1.5 * iqr
    return {i for i, v in enumerate(arr) if v < low}


def _mode(values: list):
    """(mode_value, count, fraction) — ties broken by first-seen order."""
    if not values:
        return None, 0, 0.0
    counts = collections.Counter(values)
    mode_value, count = counts.most_common(1)[0]
    return mode_value, count, count / len(values)


def group_outliers(rows: list) -> None:
    """Mutates each row in-place with 'outlier'/'outlier_reasons', judged
    RELATIVE TO SIBLING CORNERS UNDER THE SAME run_id — not a global
    reference or an arbitrary row. A minority pattern within a run_id's
    corner set is flagged only when the group is large enough
    (MIN_GROUP_FOR_MAJORITY) and there IS a clear majority
    (MAJORITY_FRACTION) to deviate from; otherwise the field is left
    unflagged (ambiguous group — don't over-flag)."""
    by_run_id = collections.defaultdict(list)
    for r in rows:
        by_run_id[r['run_id']].append(r)

    # If grouping by run_id produces no group large enough for a
    # meaningful majority comparison (e.g. every run_id is its own
    # singleton corner — true on BLUT files where run_id IS the corner
    # identifier rather than a shared test-case name, as opposed to files
    # where many corner_ids share one run_id/test-case), fall back to a
    # single global group across all corners: comparing a corner against
    # the whole regression is still more informative than comparing it
    # against nothing (a group of one has no "majority" to deviate from).
    if all(len(g) < MIN_GROUP_FOR_MAJORITY for g in by_run_id.values()) \
            and len(rows) >= MIN_GROUP_FOR_MAJORITY:
        groups = {'__all_corners__': rows}
    else:
        groups = by_run_id

    for group_key, group in groups.items():
        n = len(group)
        has_majority = n >= MIN_GROUP_FOR_MAJORITY

        majority_fields = {}
        if has_majority:
            for field in ('n_states_detected', 'determinism', 'completeness',
                         'reachability'):
                mode_v, count, frac = _mode([r[field] for r in group])
                if frac > MAJORITY_FRACTION:
                    majority_fields[field] = (mode_v, count, frac)

        local_n_signals_outliers = iqr_low_outliers([r['n_signals'] for r in group])
        local_ntime_outliers = iqr_low_outliers([r['ntime'] for r in group])
        group_median_coverage = float(np.median([r['speckg_coverage'] for r in group]))

        group_label = ('this test case' if group_key != '__all_corners__'
                       else 'the regression')
        for i, r in enumerate(group):
            reasons = []
            if r['fsm_generation_failed']:
                reasons.append('FSM generation raised an exception')
            for field, (mode_v, count, frac) in majority_fields.items():
                if r[field] != mode_v:
                    reasons.append(
                        f"{field}={r[field]!r} differs from {group_label}'s "
                        f"majority pattern ({mode_v!r}, {count}/{n} corners)")
            if i in local_n_signals_outliers:
                reasons.append(f'n_signals is a low IQR outlier within {group_label}')
            if i in local_ntime_outliers:
                reasons.append(f'ntime is a low IQR outlier within {group_label}')
            if r['speckg_coverage'] < group_median_coverage - 0.2:
                reasons.append(
                    f"speckg_coverage {r['speckg_coverage']:.0%} is >0.2 below "
                    f"{group_label}'s median {group_median_coverage:.0%}")
            r['outlier'] = bool(reasons)
            r['outlier_reasons'] = reasons
            r['group_size'] = n
            r['group_key'] = group_key


def build_parser():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blut_path', default=os.path.join(
        ROOT, 'blut_files', 'regression_multi_corner_ldo.bin'))
    ap.add_argument('--spec_json', default=os.path.join(CFG, 'LDO_1V2.json'))
    ap.add_argument('--signal_map_json',
                    default=os.path.join(CFG, 'signal_map_ldo.json'))
    ap.add_argument('--fsm_strategy', default='hybrid',
                    choices=['logic', 'cluster', 'hybrid'])
    ap.add_argument('--fsm_tree_depth', type=int, default=4)
    ap.add_argument('--ip_type', default='LDO')
    ap.add_argument('--output_dir', default=os.path.join(ROOT, 'output'))
    return ap


def main() -> int:
    args = build_parser().parse_args()

    import main as framework_main
    from digitwin.blut_reader_ext import open_blut
    from core.fsm.signal_capture import SignalCapture
    from core.fsm.state_detector import FSMStateDetector
    from core.fsm.transition_learner import TransitionLearner
    from core.fsm.fsm_codegen import FSMValidator, FSMCodeGenerator
    from core.current_insights.findings import Finding

    kg = framework_main._build_kg(args)
    sm = framework_main._resolve_signal_map(args)
    signal_map_size = len(sm.entries) if sm is not None else 0

    blut = open_blut(args.blut_path)
    run_pairs = [(rid, cid) for rid, cmap in blut.runs.items()
                 for cid in cmap.keys()]
    if not run_pairs:
        print(f"[example9] {args.blut_path}: no runs found")
        return 1

    per_corner_dir = os.path.join(args.output_dir, 'per_corner')
    os.makedirs(per_corner_dir, exist_ok=True)

    rows = []
    all_dim_keys = []  # discovered dimension column names, first-seen order
    print(f"\n{'='*60}\n  Per-corner FSM generation ({len(run_pairs)} corners)"
          f"\n{'='*60}")
    for rid, cid in run_pairs:
        qid = rid if not cid else f'{rid}@{cid}'
        run_meta_obj = blut.runs[rid][cid]

        sc = SignalCapture(spec_kg=kg)
        sc.load_from_blut(args.blut_path, run_id=qid, signal_map=sm)
        n_t = len(sc.time)

        lm, ln, _ = sc.get_logic_signal_matrix()
        om, on, _ = sc.get_output_signal_matrix()
        af = sc.get_analog_features(n_windows=min(10, max(2, n_t // 5)))

        detector = FSMStateDetector(strategy=args.fsm_strategy, spec_kg=kg)
        try:
            seq = detector.detect(lm, ln, af, output_matrix=om, output_names=on)
            learner = TransitionLearner(fsm_tree_depth=args.fsm_tree_depth)
            transitions = learner.learn(seq, lm, ln, detector.state_defs,
                                        boundary_mask=None)
            validator = FSMValidator(spec_kg=kg)
            report = validator.validate(detector.state_defs, transitions,
                                        ip_type=args.ip_type)
            codegen = FSMCodeGenerator(spec_kg=kg, ip_type=args.ip_type)
            va_code = codegen.generate_veriloga(detector.state_defs, transitions,
                                                kg.ports)
            sv_code = codegen.generate_systemverilog(detector.state_defs,
                                                      transitions)
            # Directory MUST be keyed by the full qualified (run_id,
            # corner_id) pair, not run_id alone — many corner_ids share
            # one run_id (test case) on real multi-corner files, and a
            # bare-run_id directory would silently overwrite one corner's
            # .vams/.sv with the next corner under the same test case.
            corner_dir = os.path.join(per_corner_dir, _sanitize(qid))
            os.makedirs(corner_dir, exist_ok=True)
            ip = args.ip_type.lower()
            with open(os.path.join(corner_dir, f'{ip}_fsm.vams'), 'w',
                      encoding='utf-8') as f:
                f.write(va_code)
            with open(os.path.join(corner_dir, f'{ip}_fsm.sv'), 'w',
                      encoding='utf-8') as f:
                f.write(sv_code)
            failed = False
        except Exception as e:
            print(f"  {qid}: FSM generation failed — {e}")
            report = None
            failed = True

        dims, dims_source, meta_dict, cid_dict = resolve_corner_dims(
            run_meta_obj.meta, cid)
        for k in dims:
            if k not in all_dim_keys:
                all_dim_keys.append(k)

        row = {
            'run_id': rid,
            'corner_id': cid,
            'qid': qid,
            'dims': dims,
            'dims_source': dims_source,
            'meta_dims': meta_dict,
            'corner_id_dims': cid_dict,
            'n_signals': run_meta_obj.n_signals,
            'signal_completeness_pct': (
                round(100.0 * run_meta_obj.n_signals / signal_map_size, 1)
                if signal_map_size else None),
            'ntime': run_meta_obj.ntime,
            'meta_raw': run_meta_obj.meta,
            'fsm_generation_failed': failed,
            'n_states_detected': len(detector.state_defs) if not failed else 0,
            'state_names': ([d['name'] for d in detector.state_defs.values()]
                            if not failed else []),
            'output_signature_summary': (detector.output_signatures
                                         if not failed else {}),
            'reachability': report.reachability if report else False,
            'completeness': report.completeness if report else False,
            'determinism': report.determinism if report else False,
            'speckg_coverage': round(report.speckg_coverage, 4) if report else 0.0,
            'missing_states': list(report.missing_states) if report else [],
        }
        rows.append(row)
        print(f"  {qid:60s} n_signals={row['n_signals']:3d} "
              f"ntime={row['ntime']:7d} states={row['n_states_detected']:2d} "
              f"det={row['determinism']!s:5s}")

    # ── Outlier detection: relative to sibling corners under the same
    # run_id (test case) — see group_outliers() docstring for rationale.
    group_outliers(rows)

    # ── Meta-trustworthiness checks. Two complementary scopes, since
    # neither alone catches both known failure shapes:
    #  (a) per-run_id: one test case's corners all share identical meta
    #      despite distinct corner_ids (meta broken for THAT test case
    #      only) — needs >1 corner per run_id to even be checkable, so
    #      this is a no-op on files where run_id IS the corner id (every
    #      run_id group is a singleton).
    #  (b) global: meta barely varies across the WHOLE file relative to
    #      how many distinct corner_ids exist — catches exactly that
    #      singleton-run_id case (a real fixture in this codebase's
    #      history has 27 distinct corner-bearing run_ids but only 2
    #      distinct meta strings, neither tracking the actual corner).
    hard_findings = []
    by_run_id = collections.defaultdict(list)
    for r in rows:
        by_run_id[r['run_id']].append(r)

    def _meta_trust_finding(scope_label: str, group: list, category: str):
        # Compare meta diversity against the actual number of DISTINCT
        # RUNS in this group (qid — always unique per row by
        # construction), not against distinct corner_id count: corner_id
        # itself is empty ("") on files that never populate the v8
        # corner_id field, in which case run_id alone is what actually
        # distinguishes corners, and this check must still be able to
        # catch meta being untrustworthy there too.
        distinct_meta = {r['meta_raw'] for r in group}
        distinct_qids = {r['qid'] for r in group}
        n = len(distinct_qids)
        if n <= 1:
            return None
        # "barely varies": far fewer distinct meta strings than distinct
        # runs — a hard 1-vs-many case (a) or a loose ratio for (b).
        if len(distinct_meta) == 1 or len(distinct_meta) < 0.5 * n:
            sample_meta = sorted(distinct_meta)[:3]
            return Finding(
                analyzer='per_corner_fsm_correlate',
                category=category,
                severity='high',
                summary=(f"{scope_label}: {n} distinct runs but only "
                         f"{len(distinct_meta)} distinct meta string(s) "
                         f"({sample_meta}) — meta does not reliably "
                         f"distinguish corners here; corner_id/run_id is "
                         f"the more trustworthy source"),
                evidence={'scope': scope_label, 'n_corners': n,
                          'n_distinct_meta': len(distinct_meta),
                          'sample_meta': sample_meta},
                recommended_action=('treat corner_id/run_id (not meta) as '
                                    'ground truth here; fix meta population '
                                    'in BLUT generation'))
        return None

    for run_id, group in by_run_id.items():
        if len(group) < MIN_GROUP_FOR_MAJORITY:
            continue
        f = _meta_trust_finding(run_id, group, 'meta-not-trustworthy-for-run_id')
        if f:
            hard_findings.append(f)

    # The global check only makes sense when run_id grouping is
    # DEGENERATE (every run_id is its own singleton corner, so the
    # per-run_id checks above never ran) — the same condition
    # group_outliers() uses to decide whether to fall back to one global
    # comparison group. When run_id groups ARE meaningful (many corners
    # share one test-case run_id), the same 27-ish physical corners are
    # normally reused across several test cases, so meta legitimately
    # repeats ACROSS run_ids — that repetition is not a data-quality bug
    # and must not trigger this check; only repetition WITHIN a run_id's
    # own corner set (checked above) is suspicious in that case.
    run_id_grouping_meaningful = any(
        len(g) >= MIN_GROUP_FOR_MAJORITY for g in by_run_id.values())
    if not run_id_grouping_meaningful and len(rows) >= MIN_GROUP_FOR_MAJORITY:
        f = _meta_trust_finding('__all_corners__ (whole file)', rows,
                                'meta-not-trustworthy-globally')
        if f:
            hard_findings.append(f)

    for r in rows:
        if r['outlier']:
            hard_findings.append(Finding(
                analyzer='per_corner_fsm_correlate',
                category='corner-outlier',
                severity='high' if r['fsm_generation_failed'] else 'medium',
                summary=f"{r['qid']}: {'; '.join(r['outlier_reasons'])}",
                evidence={'run_id': r['run_id'], 'corner_id': r['corner_id'],
                          'n_signals': r['n_signals'], 'ntime': r['ntime']},
                affected_states=r['state_names'],
                recommended_action=('inspect this corner\'s raw BLUT signals '
                                    'for truncated/missing capture before '
                                    'trusting its FSM/spec results')))

    # ── Reports ──────────────────────────────────────────────────────────
    md_path = os.path.join(args.output_dir, 'per_corner_correlation.md')
    json_path = os.path.join(args.output_dir, 'per_corner_correlation.json')

    L = ['# Per-Corner FSM Correlation Report', '',
         f'BLUT source: `{args.blut_path}`  |  strategy: `{args.fsm_strategy}`  '
         f'|  corners: {len(rows)}  |  test cases: {len(by_run_id)}', '']

    if hard_findings:
        L += ['## Findings', '',
              '| severity | category | summary |', '|---|---|---|']
        from core.current_insights.findings import SEVERITY_ORDER
        for f in sorted(hard_findings,
                        key=lambda x: SEVERITY_ORDER.get(x.severity, 0),
                        reverse=True):
            L.append(f'| {f.severity} | {f.category} | {f.summary} |')
        L.append('')

    outliers = [r for r in rows if r['outlier']]
    L += [f'## Outlier corners ({len(outliers)}/{len(rows)})', '']
    if outliers:
        for r in outliers:
            L.append(f"- **{r['qid']}**: {'; '.join(r['outlier_reasons'])}")
    else:
        L.append('None flagged.')
    L.append('')

    dim_headers = ''.join(f' {k} |' for k in all_dim_keys)
    L += ['## Per-corner table', '',
          f'| run_id | corner_id |{dim_headers} n_signals | completeness% | '
          'ntime | n_states | determinism | speckg_coverage | outlier |',
          '|---|---|' + '---|' * len(all_dim_keys) +
          '---|---|---|---|---|---|---|']
    for r in sorted(rows, key=lambda x: (x['run_id'], x['corner_id'])):
        dim_cells = ''.join(f" {r['dims'].get(k, '-')} |" for k in all_dim_keys)
        L.append(
            f"| {r['run_id']} | {r['corner_id'] or '-'} |{dim_cells} "
            f"{r['n_signals']} | "
            f"{r['signal_completeness_pct']} | {r['ntime']} | "
            f"{r['n_states_detected']} | {r['determinism']} | "
            f"{r['speckg_coverage']:.0%} | "
            f"{'YES' if r['outlier'] else ''} |")
    L.append('')

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L))
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'blut_path': args.blut_path,
            'fsm_strategy': args.fsm_strategy,
            'findings': [f.as_row() for f in hard_findings],
            'corners': rows,
        }, f, indent=2, default=str)

    print(f"\n{'='*60}\n  SUMMARY")
    print(f"{'='*60}")
    print(f"  {len(rows)} corners across {len(by_run_id)} test cases processed, "
          f"{len(outliers)} flagged as outliers")
    print(f"  report: {md_path} (+ .json)")
    print(f"  per-corner .vams/.sv: {per_corner_dir}/<run_id>@<corner_id>/")
    return 0


if __name__ == '__main__':
    sys.exit(main())
