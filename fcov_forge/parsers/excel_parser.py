"""
fcov_forge/parsers/excel_parser.py
====================================
Parses FCovForge Excel (.xlsx) format into FeatureModel.

Excel Layout (one workbook per project):
  Sheet "Features"    — Feature registry
  Sheet "CoverGroups" — CoverGroup definitions
  Sheet "CoverPoints" — CoverPoint definitions
  Sheet "Bins"        — Bin definitions (all types)
  Sheet "Crosses"     — FeatureCross definitions

Column schemas are documented below.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Optional
import re

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

from core.model import (
    FeatureModel, Feature, CoverGroup, CoverPoint, CoverBin,
    CrossDef, FeatureCross, FeatureCrossTarget, BinType
)

# ---------------------------------------------------------------------------
# Column schemas
# ---------------------------------------------------------------------------

# Sheet: Features
# feature_name | description | tags | source_doc
FEATURES_COLS = ["feature_name", "description", "tags", "source_doc"]

# Sheet: CoverGroups
# feature_name | cg_name | clock | condition | per_instance | auto_bin_max | goal | comment | args
COVERGROUPS_COLS = ["feature_name", "cg_name", "clock", "condition",
                    "per_instance", "auto_bin_max", "goal", "comment", "args"]

# Sheet: CoverPoints
# feature_name | cg_name | cp_name | variable | condition | comment
COVERPOINTS_COLS = ["feature_name", "cg_name", "cp_name", "variable", "condition", "comment"]

# Sheet: Bins
# feature_name | cg_name | cp_name | bin_name | type | values | ranges | transitions | pattern | auto_bin_max | min_hits | weight | comment
BINS_COLS = ["feature_name", "cg_name", "cp_name", "bin_name", "type",
             "values", "ranges", "transitions", "pattern",
             "auto_bin_max", "min_hits", "weight", "comment"]

# Sheet: Crosses (Feature-level)
# cross_name | targets | exclude_combinations | comment | goal
CROSSES_COLS = ["cross_name", "targets", "exclude_combinations", "comment", "goal"]

# Sheet: CG_Crosses (within-covergroup crosses)
# feature_name | cg_name | cross_name | coverpoints | exclude_bins | comment
CG_CROSSES_COLS = ["feature_name", "cg_name", "cross_name", "coverpoints", "exclude_bins", "comment"]


def _safe(val: Any, default: Any = None) -> Any:
    if val is None or (isinstance(val, float) and str(val) == "nan"):
        return default
    return val


def _parse_list(val: Any, sep: str = ",") -> list[str]:
    """Parse a comma/semicolon separated string into a list."""
    if not val:
        return []
    return [v.strip() for v in str(val).split(sep) if v.strip()]


def _parse_values(val: Any) -> list[Any]:
    """Parse '1, 2, 3' or '0x1, 0xFF' into a list."""
    if not val:
        return []
    items = []
    for v in str(val).split(","):
        v = v.strip()
        if not v:
            continue
        # Try int (hex or decimal)
        try:
            items.append(int(v, 0))
        except (ValueError, TypeError):
            items.append(v)
    return items


def _parse_ranges(val: Any) -> list[tuple]:
    """
    Parse '0:15, 32:47' or '[[0,15],[32,47]]' into list of (lo, hi) tuples.
    """
    if not val:
        return []
    text = str(val).strip()
    # Try JSON-like format
    if text.startswith("["):
        import json
        try:
            parsed = json.loads(text)
            return [tuple(r) for r in parsed]
        except Exception:
            pass
    # Try 'lo:hi, lo:hi' format
    ranges = []
    for part in text.split(","):
        part = part.strip()
        if ":" in part:
            lo, hi = part.split(":", 1)
            try:
                ranges.append((int(lo.strip(), 0), int(hi.strip(), 0)))
            except ValueError:
                ranges.append((lo.strip(), hi.strip()))
    return ranges


def _parse_transitions(val: Any) -> list[list[str]]:
    """
    Parse transitions: 'IDLE=>ACTIVE=>DONE | IDLE=>ERROR'
    Pipes separate sequences, => separates states within a sequence.
    """
    if not val:
        return []
    text = str(val).strip()
    sequences = []
    for seq_str in text.split("|"):
        states = [s.strip() for s in seq_str.split("=>") if s.strip()]
        if states:
            sequences.append(states)
    return sequences


def _sheet_to_dicts(sheet) -> list[dict]:
    """Convert an openpyxl sheet to list of dicts using first row as headers."""
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h).strip().lower() if h else f"col_{i}" for i, h in enumerate(rows[0])]
    result = []
    for row in rows[1:]:
        if all(v is None for v in row):
            continue
        result.append(dict(zip(headers, row)))
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_excel(path: str | Path) -> FeatureModel:
    """Parse a FCovForge Excel workbook into a FeatureModel."""
    if not OPENPYXL_AVAILABLE:
        raise ImportError("openpyxl is required for Excel parsing: pip install openpyxl")

    path = Path(path)
    wb = openpyxl.load_workbook(path, data_only=True)

    # ---- Features ----
    features_map: dict[str, Feature] = {}
    if "Features" in wb.sheetnames:
        for row in _sheet_to_dicts(wb["Features"]):
            fn = _safe(row.get("feature_name"), "")
            if not fn:
                continue
            features_map[fn] = Feature(
                name=fn,
                description=_safe(row.get("description")),
                tags=_parse_list(_safe(row.get("tags"), "")),
                source_doc=_safe(row.get("source_doc")),
            )

    # ---- CoverGroups ----
    cg_map: dict[tuple, CoverGroup] = {}  # (feature_name, cg_name)
    if "CoverGroups" in wb.sheetnames:
        for row in _sheet_to_dicts(wb["CoverGroups"]):
            fn = _safe(row.get("feature_name"), "")
            cgn = _safe(row.get("cg_name"), "")
            if not fn or not cgn:
                continue
            # Parse args: "int channel_id, logic [7:0] addr"
            raw_args = _safe(row.get("args"), "")
            args = []
            if raw_args:
                for arg in str(raw_args).split(","):
                    parts = arg.strip().rsplit(" ", 1)
                    if len(parts) == 2:
                        args.append((parts[0].strip(), parts[1].strip()))

            cg = CoverGroup(
                name=cgn,
                clock_event=_safe(row.get("clock")),
                sample_condition=_safe(row.get("condition")),
                per_instance=bool(_safe(row.get("per_instance"), False)),
                auto_bin_max=_safe(row.get("auto_bin_max")),
                goal=int(_safe(row.get("goal", 100))),
                comment=_safe(row.get("comment")),
                args=args,
            )
            cg_map[(fn, cgn)] = cg
            if fn in features_map:
                features_map[fn].covergroups.append(cg)
            else:
                # Auto-create feature if not in Features sheet
                features_map[fn] = Feature(name=fn, covergroups=[cg])

    # ---- CoverPoints ----
    cp_map: dict[tuple, CoverPoint] = {}  # (fn, cgn, cpn)
    if "CoverPoints" in wb.sheetnames:
        for row in _sheet_to_dicts(wb["CoverPoints"]):
            fn = _safe(row.get("feature_name"), "")
            cgn = _safe(row.get("cg_name"), "")
            cpn = _safe(row.get("cp_name"), "")
            if not all([fn, cgn, cpn]):
                continue
            cp = CoverPoint(
                name=cpn,
                variable=_safe(row.get("variable"), cpn),
                condition=_safe(row.get("condition")),
                comment=_safe(row.get("comment")),
            )
            cp_map[(fn, cgn, cpn)] = cp
            key = (fn, cgn)
            if key in cg_map:
                cg_map[key].coverpoints.append(cp)

    # ---- Bins ----
    _BIN_TYPE_MAP = {
        "values": BinType.VALUES, "range": BinType.RANGE, "ranges": BinType.RANGE,
        "transition": BinType.TRANSITION, "default": BinType.DEFAULT,
        "ignore": BinType.IGNORE, "illegal": BinType.ILLEGAL,
        "wildcard": BinType.WILDCARD, "auto": BinType.AUTO,
    }
    if "Bins" in wb.sheetnames:
        for row in _sheet_to_dicts(wb["Bins"]):
            fn = _safe(row.get("feature_name"), "")
            cgn = _safe(row.get("cg_name"), "")
            cpn = _safe(row.get("cp_name"), "")
            bn = _safe(row.get("bin_name"), "")
            if not all([fn, cgn, cpn, bn]):
                continue
            raw_type = str(_safe(row.get("type"), "values")).lower()
            bin_type = _BIN_TYPE_MAP.get(raw_type, BinType.VALUES)

            b = CoverBin(
                name=bn,
                bin_type=bin_type,
                values=_parse_values(_safe(row.get("values"))),
                ranges=_parse_ranges(_safe(row.get("ranges"))),
                transitions=_parse_transitions(_safe(row.get("transitions"))),
                wildcard_pattern=_safe(row.get("pattern")),
                auto_bin_max=_safe(row.get("auto_bin_max")),
                min_hits=int(_safe(row.get("min_hits", 1))),
                weight=_safe(row.get("weight")),
                comment=_safe(row.get("comment")),
            )
            key = (fn, cgn, cpn)
            if key in cp_map:
                cp_map[key].bins.append(b)

    # ---- CG-level Crosses ----
    if "CG_Crosses" in wb.sheetnames:
        for row in _sheet_to_dicts(wb["CG_Crosses"]):
            fn = _safe(row.get("feature_name"), "")
            cgn = _safe(row.get("cg_name"), "")
            xn = _safe(row.get("cross_name"), "")
            if not all([fn, cgn, xn]):
                continue
            cross = CrossDef(
                name=xn,
                coverpoints=_parse_list(_safe(row.get("coverpoints"), "")),
                exclude_bins=_parse_list(_safe(row.get("exclude_bins"), "")),
                comment=_safe(row.get("comment")),
            )
            key = (fn, cgn)
            if key in cg_map:
                cg_map[key].crosses.append(cross)

    # ---- Feature Crosses ----
    feature_crosses = []
    if "Crosses" in wb.sheetnames:
        for row in _sheet_to_dicts(wb["Crosses"]):
            xn = _safe(row.get("cross_name"), "")
            if not xn:
                continue
            targets_raw = _parse_list(_safe(row.get("targets"), ""), sep="|")
            targets = [FeatureCrossTarget(address=t.strip()) for t in targets_raw]
            fc = FeatureCross(
                name=xn,
                targets=targets,
                comment=_safe(row.get("comment")),
                goal=int(_safe(row.get("goal", 100))),
            )
            feature_crosses.append(fc)

    model = FeatureModel(
        project_name=path.stem,
        features=list(features_map.values()),
        feature_crosses=feature_crosses,
    )
    return model
