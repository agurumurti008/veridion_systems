"""
fcov_forge/core/model.py
========================
Core data model representing the Feature → CoverGroup → CoverPoint → CoverBin hierarchy.
All elements are addressable via dotted path notation.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import re


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class BinType(str, Enum):
    """Types of coverage bins supported in SystemVerilog."""
    VALUES      = "values"       # bins b = {1, 2, 3}
    RANGE       = "range"        # bins b = {[0:15]}
    TRANSITION  = "transition"   # bins b = (1 => 2 => 3)
    DEFAULT     = "default"      # default bin
    IGNORE      = "ignore"       # ignore_bins
    ILLEGAL     = "illegal"      # illegal_bins
    WILDCARD    = "wildcard"     # wildcard bins b = {4'b1?0?}
    AUTO        = "auto"         # auto bins (SV auto-partition)


class SamplingEdge(str, Enum):
    POSEDGE = "posedge"
    NEGEDGE = "negedge"
    ALWAYS  = "always"


# ---------------------------------------------------------------------------
# CoverBin
# ---------------------------------------------------------------------------

@dataclass
class CoverBin:
    """
    Represents a single coverage bin.

    Supports all SV bin types:
      - values:     {1, 2, 3}
      - range:      {[0:15]}
      - transition: (IDLE => ACTIVE => DONE)
      - wildcard:   {4'b1?0?}
      - default
      - ignore_bins
      - illegal_bins
      - auto (auto_bin_max)
    """
    name: str
    bin_type: BinType = BinType.VALUES

    # For VALUES and RANGE bins
    values: list[Any] = field(default_factory=list)
    # e.g. [[0, 15], [32, 63]]  → {[0:15], [32:63]}
    ranges: list[tuple[Any, Any]] = field(default_factory=list)

    # For TRANSITION bins
    # e.g. ["IDLE", "ACTIVE", "DONE"]
    transitions: list[list[str]] = field(default_factory=list)

    # For WILDCARD bins
    wildcard_pattern: Optional[str] = None  # e.g. "4'b1?0?"

    # For AUTO bins
    auto_bin_max: Optional[int] = None

    # Multiplicity: how many times this bin must be hit (default 1)
    min_hits: int = 1

    # Optional weight (for coverage weighting)
    weight: Optional[int] = None

    # For ignore/illegal, we reuse values/ranges
    comment: Optional[str] = None

    @property
    def sv_keyword(self) -> str:
        if self.bin_type == BinType.IGNORE:
            return "ignore_bins"
        if self.bin_type == BinType.ILLEGAL:
            return "illegal_bins"
        return "bins"

    def to_sv(self, indent: int = 3) -> str:
        """Render this bin as a SystemVerilog statement."""
        pad = "  " * indent
        kw = self.sv_keyword
        hits = f" iff (hit_count >= {self.min_hits})" if self.min_hits > 1 else ""
        comment_str = f"  // {self.comment}" if self.comment else ""

        if self.bin_type == BinType.DEFAULT:
            return f"{pad}{kw} {self.name} = default;{comment_str}"

        if self.bin_type == BinType.WILDCARD:
            return f"{pad}wildcard {kw} {self.name} = {{{self.wildcard_pattern}}};{comment_str}"

        if self.bin_type == BinType.AUTO:
            max_str = f" = {{}}" if not self.auto_bin_max else ""
            return f"{pad}{kw}[] {self.name} = {{}};  // auto{comment_str}"

        if self.bin_type == BinType.TRANSITION:
            # Each transition sequence is a separate path: (a => b => c), (x => y)
            seqs = ", ".join(
                "(" + " => ".join(str(s) for s in seq) + ")"
                for seq in self.transitions
            )
            return f"{pad}{kw} {self.name} = {seqs};{comment_str}"

        # VALUES and RANGE combined
        parts = []
        for v in self.values:
            parts.append(str(v))
        for lo, hi in self.ranges:
            parts.append(f"[{lo}:{hi}]")
        body = ", ".join(parts)

        weight_str = f" iff (1) /* weight={self.weight} */" if self.weight is not None else ""
        return f"{pad}{kw} {self.name} = {{{body}}};{weight_str}{comment_str}"

    def address(self, parent_path: str) -> str:
        return f"{parent_path}.{self.name}"


# ---------------------------------------------------------------------------
# CoverPoint
# ---------------------------------------------------------------------------

@dataclass
class CoverPoint:
    """A coverpoint within a covergroup."""
    name: str
    variable: str                        # SV expression being sampled
    bins: list[CoverBin] = field(default_factory=list)
    condition: Optional[str] = None      # iff (condition)
    comment: Optional[str] = None

    def to_sv(self, indent: int = 2) -> str:
        pad = "  " * indent
        iff_str = f" iff ({self.condition})" if self.condition else ""
        cmt = f"  // {self.comment}" if self.comment else ""
        lines = [f"{pad}{self.name} : coverpoint {self.variable}{iff_str} {{{cmt}"]
        for b in self.bins:
            lines.append(b.to_sv(indent + 1))
        lines.append(f"{pad}}}")
        return "\n".join(lines)

    def get_bin(self, name: str) -> Optional[CoverBin]:
        return next((b for b in self.bins if b.name == name), None)

    def address(self, parent_path: str) -> str:
        return f"{parent_path}.{self.name}"


# ---------------------------------------------------------------------------
# CrossDef (within a covergroup)
# ---------------------------------------------------------------------------

@dataclass
class CrossDef:
    """
    Represents a `cross` statement inside a covergroup.
    Cross between coverpoints within the SAME covergroup.
    For cross BETWEEN covergroups/features, see FeatureCross.
    """
    name: str
    coverpoints: list[str]               # names of coverpoints to cross
    exclude_bins: list[str] = field(default_factory=list)
    bins_of: list[str] = field(default_factory=list)   # binsof() selectors
    comment: Optional[str] = None

    def to_sv(self, indent: int = 2) -> str:
        pad = "  " * indent
        cp_list = ", ".join(self.coverpoints)
        cmt = f"  // {self.comment}" if self.comment else ""
        parts = [f"{pad}{self.name} : cross {cp_list} {{{cmt}"]
        for ex in self.exclude_bins:
            parts.append(f"{pad}  ignore_bins excl = binsof({ex});")
        for bo in self.bins_of:
            parts.append(f"{pad}  bins selected = binsof({bo});")
        parts.append(f"{pad}}}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# CoverGroup
# ---------------------------------------------------------------------------

@dataclass
class CoverGroup:
    """A SystemVerilog covergroup."""
    name: str
    coverpoints: list[CoverPoint] = field(default_factory=list)
    crosses: list[CrossDef] = field(default_factory=list)

    # Sampling control
    clock_event: Optional[str] = None    # e.g. "posedge clk"
    sample_condition: Optional[str] = None  # additional iff

    # Options
    per_instance: bool = False
    auto_bin_max: Optional[int] = None
    goal: Optional[int] = 100
    comment: Optional[str] = None

    # Arguments (for parameterized covergroups)
    args: list[tuple[str, str]] = field(default_factory=list)  # [(type, name)]

    def to_sv(self, indent: int = 1) -> str:
        pad = "  " * indent
        args_str = ""
        if self.args:
            args_str = "(" + ", ".join(f"{t} {n}" for t, n in self.args) + ")"
        clock_str = f" @({self.clock_event})" if self.clock_event else ""
        iff_str = f" iff ({self.sample_condition})" if self.sample_condition else ""
        cmt = f"  // {self.comment}" if self.comment else ""

        lines = [f"{pad}covergroup {self.name}{args_str}{clock_str}{iff_str};{cmt}"]

        if self.per_instance:
            lines.append(f"{pad}  option.per_instance = 1;")
        if self.auto_bin_max is not None:
            lines.append(f"{pad}  option.auto_bin_max = {self.auto_bin_max};")
        if self.goal is not None:
            lines.append(f"{pad}  option.goal = {self.goal};")

        for cp in self.coverpoints:
            lines.append("")
            lines.append(cp.to_sv(indent + 1))

        for cross in self.crosses:
            lines.append("")
            lines.append(cross.to_sv(indent + 1))

        lines.append(f"{pad}endgroup : {self.name}")
        return "\n".join(lines)

    def get_coverpoint(self, name: str) -> Optional[CoverPoint]:
        return next((cp for cp in self.coverpoints if cp.name == name), None)

    def address(self, parent_path: str) -> str:
        return f"{parent_path}.{self.name}"


# ---------------------------------------------------------------------------
# FeatureCross — the core innovation
# ---------------------------------------------------------------------------

@dataclass
class FeatureCrossTarget:
    """
    One side of a feature cross. Addressable to any granularity:
      - "feature_name"                              → entire feature (all CGs)
      - "feature_name.covergroup_name"              → specific CG
      - "feature_name.covergroup_name.coverpoint"   → specific CP
    """
    address: str   # dotted path

    @property
    def parts(self) -> list[str]:
        return self.address.split(".")

    @property
    def feature_name(self) -> str:
        return self.parts[0]

    @property
    def covergroup_name(self) -> Optional[str]:
        return self.parts[1] if len(self.parts) > 1 else None

    @property
    def coverpoint_name(self) -> Optional[str]:
        return self.parts[2] if len(self.parts) > 2 else None

    @property
    def bin_name(self) -> Optional[str]:
        return self.parts[3] if len(self.parts) > 3 else None


@dataclass
class FeatureCross:
    """
    Defines a cross between two or more features (or sub-elements thereof).
    This is the novel abstraction that FCovForge introduces.

    Example:
      name: dma_x_interrupt_cross
      targets:
        - dma_transfer.data_width_cg.width_cp
        - interrupt_handling.priority_cg
    """
    name: str
    targets: list[FeatureCrossTarget]
    exclude_combinations: list[dict] = field(default_factory=list)
    comment: Optional[str] = None
    goal: Optional[int] = 100


# ---------------------------------------------------------------------------
# Feature — top-level abstraction
# ---------------------------------------------------------------------------

@dataclass
class Feature:
    """
    A Feature groups multiple covergroups that together represent one
    device feature. Features are the unit of cross-functional coverage.
    """
    name: str
    description: Optional[str] = None
    covergroups: list[CoverGroup] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source_doc: Optional[str] = None   # traceability

    def get_covergroup(self, name: str) -> Optional[CoverGroup]:
        return next((cg for cg in self.covergroups if cg.name == name), None)

    def resolve(self, dotted_path: str) -> Any:
        """
        Resolve a dotted address within this feature.
        Path should not include the feature name as first component.
        e.g. "data_width_cg.width_cp.BIN_32BIT"
        """
        parts = dotted_path.split(".")
        if not parts:
            return self

        cg = self.get_covergroup(parts[0])
        if cg is None:
            raise ValueError(f"CoverGroup '{parts[0]}' not found in feature '{self.name}'")
        if len(parts) == 1:
            return cg

        cp = cg.get_coverpoint(parts[1])
        if cp is None:
            raise ValueError(f"CoverPoint '{parts[1]}' not found in '{self.name}.{parts[0]}'")
        if len(parts) == 2:
            return cp

        b = cp.get_bin(parts[2])
        if b is None:
            raise ValueError(f"Bin '{parts[2]}' not found in '{self.name}.{parts[0]}.{parts[1]}'")
        return b


# ---------------------------------------------------------------------------
# FeatureModel — the top-level container
# ---------------------------------------------------------------------------

@dataclass
class FeatureModel:
    """Container for all features and cross definitions in a project."""
    project_name: str
    features: list[Feature] = field(default_factory=list)
    feature_crosses: list[FeatureCross] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def get_feature(self, name: str) -> Optional[Feature]:
        return next((f for f in self.features if f.name == name), None)

    def resolve_address(self, address: str) -> Any:
        """
        Resolve a full dotted address:
        "feature.covergroup.coverpoint.bin"
        """
        parts = address.split(".", 1)
        feature = self.get_feature(parts[0])
        if feature is None:
            raise ValueError(f"Feature '{parts[0]}' not found in model")
        if len(parts) == 1:
            return feature
        return feature.resolve(parts[1])
