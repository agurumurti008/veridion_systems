"""
fcov_forge/parsers/yaml_parser.py
==================================
Parses the FCovForge YAML format into the internal FeatureModel.

YAML Format Summary:
  project: "MyChip"
  features:
    - name: feature_name
      description: "..."
      tags: [tag1, tag2]
      covergroups:
        - name: cg_name
          clock: "posedge clk"
          condition: "reset_n"
          per_instance: true
          auto_bin_max: 64
          goal: 100
          args:
            - type: int
              name: channel_id
          coverpoints:
            - name: cp_name
              variable: "dut.signal"
              condition: "valid"
              bins:
                # VALUES bin
                - name: BIN_A
                  values: [1, 2, 3]

                # RANGE bin
                - name: BIN_RANGE
                  ranges: [[0, 15], [32, 47]]

                # MIXED values+ranges
                - name: BIN_MIXED
                  values: [64]
                  ranges: [[128, 255]]

                # TRANSITION bin
                - name: BIN_TRANS
                  type: transition
                  transitions:
                    - [IDLE, ACTIVE, DONE]
                    - [IDLE, ERROR]

                # WILDCARD bin
                - name: BIN_WILD
                  type: wildcard
                  pattern: "4'b1?0?"

                # AUTO bin
                - name: BIN_AUTO
                  type: auto
                  auto_bin_max: 16

                # DEFAULT bin
                - name: BIN_DEFAULT
                  type: default

                # IGNORE bin
                - name: BIN_IGNORE
                  type: ignore
                  values: [255]

                # ILLEGAL bin
                - name: BIN_ILLEGAL
                  type: illegal
                  ranges: [[256, 511]]

          crosses:
            - name: width_x_burst
              coverpoints: [width_cp, burst_cp]
              exclude_bins: [width_cp.BIN_8BIT]

  feature_crosses:
    - name: dma_x_interrupt
      targets:
        - dma_transfer.data_width_cg.width_cp
        - interrupt_handling.priority_cg
      comment: "Verify DMA width behavior under interrupt pressure"
      goal: 100
      exclude_combinations:
        - dma_transfer.data_width_cg.width_cp.BIN_8BIT: true
          interrupt_handling.priority_cg.high_cp.BIN_HIGH: true
"""

from __future__ import annotations
import yaml
from pathlib import Path
from typing import Any

from core.model import (
    FeatureModel, Feature, CoverGroup, CoverPoint, CoverBin,
    CrossDef, FeatureCross, FeatureCrossTarget, BinType
)


# ---------------------------------------------------------------------------
# Bin type mapping
# ---------------------------------------------------------------------------

_BIN_TYPE_MAP = {
    "values":     BinType.VALUES,
    "range":      BinType.RANGE,
    "transition": BinType.TRANSITION,
    "default":    BinType.DEFAULT,
    "ignore":     BinType.IGNORE,
    "illegal":    BinType.ILLEGAL,
    "wildcard":   BinType.WILDCARD,
    "auto":       BinType.AUTO,
}


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_bin(raw: dict) -> CoverBin:
    name = raw["name"]
    raw_type = raw.get("type", "values").lower()

    # Auto-detect type if 'type' not specified
    if "transitions" in raw and raw_type == "values":
        raw_type = "transition"
    if "pattern" in raw:
        raw_type = "wildcard"
    if "auto_bin_max" in raw and raw_type == "values":
        raw_type = "auto"

    bin_type = _BIN_TYPE_MAP.get(raw_type, BinType.VALUES)

    # Parse ranges: [[lo, hi], ...]
    raw_ranges = raw.get("ranges", [])
    ranges = [tuple(r) for r in raw_ranges]

    # Parse transitions: [[s1, s2, s3], [s1, s4]]
    raw_transitions = raw.get("transitions", [])

    return CoverBin(
        name=name,
        bin_type=bin_type,
        values=raw.get("values", []),
        ranges=ranges,
        transitions=raw_transitions,
        wildcard_pattern=raw.get("pattern"),
        auto_bin_max=raw.get("auto_bin_max"),
        min_hits=raw.get("min_hits", 1),
        weight=raw.get("weight"),
        comment=raw.get("comment"),
    )


def _parse_coverpoint(raw: dict) -> CoverPoint:
    bins = [_parse_bin(b) for b in raw.get("bins", [])]
    return CoverPoint(
        name=raw["name"],
        variable=raw["variable"],
        bins=bins,
        condition=raw.get("condition"),
        comment=raw.get("comment"),
    )


def _parse_cross_def(raw: dict) -> CrossDef:
    return CrossDef(
        name=raw["name"],
        coverpoints=raw.get("coverpoints", []),
        exclude_bins=raw.get("exclude_bins", []),
        bins_of=raw.get("bins_of", []),
        comment=raw.get("comment"),
    )


def _parse_covergroup(raw: dict) -> CoverGroup:
    coverpoints = [_parse_coverpoint(cp) for cp in raw.get("coverpoints", [])]
    crosses = [_parse_cross_def(c) for c in raw.get("crosses", [])]

    # Parse args: [{type: int, name: channel_id}]
    raw_args = raw.get("args", [])
    args = [(a["type"], a["name"]) for a in raw_args]

    return CoverGroup(
        name=raw["name"],
        coverpoints=coverpoints,
        crosses=crosses,
        clock_event=raw.get("clock"),
        sample_condition=raw.get("condition"),
        per_instance=raw.get("per_instance", False),
        auto_bin_max=raw.get("auto_bin_max"),
        goal=raw.get("goal", 100),
        comment=raw.get("comment"),
        args=args,
    )


def _parse_feature(raw: dict) -> Feature:
    covergroups = [_parse_covergroup(cg) for cg in raw.get("covergroups", [])]
    return Feature(
        name=raw["name"],
        description=raw.get("description"),
        covergroups=covergroups,
        tags=raw.get("tags", []),
        source_doc=raw.get("source_doc"),
    )


def _parse_feature_cross(raw: dict) -> FeatureCross:
    targets = [FeatureCrossTarget(address=t) for t in raw.get("targets", [])]
    return FeatureCross(
        name=raw["name"],
        targets=targets,
        exclude_combinations=raw.get("exclude_combinations", []),
        comment=raw.get("comment"),
        goal=raw.get("goal", 100),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_yaml(path: str | Path) -> FeatureModel:
    """Parse a FCovForge YAML file and return a FeatureModel."""
    path = Path(path)
    with open(path) as f:
        raw = yaml.safe_load(f)

    features = [_parse_feature(f) for f in raw.get("features", [])]
    feature_crosses = [_parse_feature_cross(fc) for fc in raw.get("feature_crosses", [])]

    return FeatureModel(
        project_name=raw.get("project", path.stem),
        features=features,
        feature_crosses=feature_crosses,
        metadata=raw.get("metadata", {}),
    )


def parse_yaml_string(content: str, project_name: str = "unnamed") -> FeatureModel:
    """Parse YAML from a string."""
    raw = yaml.safe_load(content)
    features = [_parse_feature(f) for f in raw.get("features", [])]
    feature_crosses = [_parse_feature_cross(fc) for fc in raw.get("feature_crosses", [])]
    return FeatureModel(
        project_name=raw.get("project", project_name),
        features=features,
        feature_crosses=feature_crosses,
        metadata=raw.get("metadata", {}),
    )
