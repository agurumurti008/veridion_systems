"""
fcov_forge/core/cross_engine.py
================================
The Cross Engine is the heart of FCovForge.

It resolves FeatureCross definitions (which can target entire features,
specific covergroups, or specific coverpoints) and synthesizes new
SystemVerilog covergroup structures that implement cross coverage at
the feature level.

Algorithm:
  1. For each FeatureCross, resolve all targets to their coverpoints.
  2. If targets are at different granularities, expand appropriately.
  3. Generate a synthetic "wrapper" covergroup that implements the cross.
  4. Handle exclude combinations.

The output is a list of SynthesizedCross objects, each of which
can render itself to SystemVerilog.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import itertools

from core.model import (
    FeatureModel, Feature, CoverGroup, CoverPoint, CoverBin,
    FeatureCross, FeatureCrossTarget, BinType
)


# ---------------------------------------------------------------------------
# Internal representation of resolved cross target
# ---------------------------------------------------------------------------

@dataclass
class ResolvedTarget:
    """A FeatureCrossTarget resolved to actual CoverPoints."""
    address: str
    feature: Feature
    covergroup: Optional[CoverGroup]
    coverpoint: Optional[CoverPoint]

    # If we resolved to a CG level, we expand to all its CPs
    coverpoints: list[CoverPoint] = field(default_factory=list)

    @property
    def sv_alias(self) -> str:
        """A safe SV identifier for this target."""
        return self.address.replace(".", "_")


# ---------------------------------------------------------------------------
# Synthesized cross — one complete feature cross output
# ---------------------------------------------------------------------------

@dataclass
class SynthesizedCross:
    """
    Represents a synthesized covergroup that implements a feature cross.
    This covergroup includes shadow coverpoints that mirror the original
    signals, plus the cross statement connecting them.
    """
    cross_def: FeatureCross
    resolved_targets: list[ResolvedTarget]

    @property
    def cg_name(self) -> str:
        return f"fcov_cross_{self.cross_def.name}_cg"

    def to_sv(self) -> str:
        """
        Generate SystemVerilog for this feature cross.

        Strategy:
          - Generate a covergroup that references the same variables as the
            source coverpoints (they share the same DUT signals).
          - Add shadow coverpoints mirroring bins of each source coverpoint.
          - Add the cross statement.
          - Wrap in a class or module interface comment block for integration.
        """
        lines = []
        lines.append(f"// =============================================================")
        lines.append(f"// FCovForge Synthesized Feature Cross: {self.cross_def.name}")
        if self.cross_def.comment:
            lines.append(f"// {self.cross_def.comment}")
        lines.append(f"// Targets:")
        for t in self.cross_def.targets:
            lines.append(f"//   - {t.address}")
        lines.append(f"// =============================================================")
        lines.append(f"")

        clock_events = set()
        for rt in self.resolved_targets:
            if rt.covergroup and rt.covergroup.clock_event:
                clock_events.add(rt.covergroup.clock_event)

        # Use first found clock or leave empty
        clock_str = ""
        if clock_events:
            clock_str = f" @({next(iter(clock_events))})"

        lines.append(f"covergroup {self.cg_name}{clock_str};")
        lines.append(f"  option.per_instance = 0;")
        lines.append(f"  option.goal = {self.cross_def.goal};")
        lines.append(f"")

        # Emit shadow coverpoints
        shadow_cp_names = []
        for rt in self.resolved_targets:
            target_cps = rt.coverpoints if rt.coverpoints else ([rt.coverpoint] if rt.coverpoint else [])
            for cp in target_cps:
                shadow_name = f"shadow_{rt.sv_alias}_{cp.name}"
                shadow_cp_names.append(shadow_name)
                iff_str = f" iff ({cp.condition})" if cp.condition else ""
                lines.append(f"  // Shadow of {rt.address}.{cp.name}")
                lines.append(f"  {shadow_name} : coverpoint {cp.variable}{iff_str} {{")
                for b in cp.bins:
                    lines.append(b.to_sv(indent=2))
                lines.append(f"  }}")
                lines.append(f"")

        # Emit the cross
        if len(shadow_cp_names) >= 2:
            cross_targets = ", ".join(shadow_cp_names)
            lines.append(f"  // Feature-level cross")
            lines.append(f"  {self.cross_def.name}_cross : cross {cross_targets} {{")

            # Exclude combinations
            for excl in self.cross_def.exclude_combinations:
                # Format: {addr: true} dicts — convert to binsof expressions
                binsof_parts = []
                for addr, active in excl.items():
                    if active:
                        parts = addr.split(".")
                        if len(parts) >= 4:
                            # feature.cg.cp.bin → binsof(shadow_feature_cg_cp.bin)
                            shadow = f"shadow_{'_'.join(parts[:3])}.{parts[3]}"
                            binsof_parts.append(f"binsof({shadow})")
                if binsof_parts:
                    cond = " && ".join(binsof_parts)
                    lines.append(f"    ignore_bins excl = ({cond});")

            lines.append(f"  }}")

        lines.append(f"endgroup : {self.cg_name}")
        lines.append(f"")
        lines.append(f"// Instantiate in your testbench:")
        lines.append(f"// {self.cg_name} {self.cross_def.name}_inst = new();")
        lines.append(f"// {self.cross_def.name}_inst.sample();")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cross Engine
# ---------------------------------------------------------------------------

class CrossEngine:
    """
    Resolves FeatureCross definitions and synthesizes SV coverage code.
    """

    def __init__(self, model: FeatureModel):
        self.model = model

    def resolve_target(self, target: FeatureCrossTarget) -> ResolvedTarget:
        """
        Resolve a FeatureCrossTarget to actual model objects.
        Supports:
          - "feature_name"                    → all CPs in all CGs
          - "feature_name.cg_name"            → all CPs in that CG
          - "feature_name.cg_name.cp_name"    → specific CP
        """
        feature = self.model.get_feature(target.feature_name)
        if feature is None:
            raise ValueError(f"[CrossEngine] Feature '{target.feature_name}' not found")

        # Feature-level target
        if target.covergroup_name is None:
            all_cps = []
            for cg in feature.covergroups:
                all_cps.extend(cg.coverpoints)
            return ResolvedTarget(
                address=target.address,
                feature=feature,
                covergroup=None,
                coverpoint=None,
                coverpoints=all_cps,
            )

        # CoverGroup-level target
        cg = feature.get_covergroup(target.covergroup_name)
        if cg is None:
            raise ValueError(
                f"[CrossEngine] CoverGroup '{target.covergroup_name}' "
                f"not found in feature '{target.feature_name}'"
            )

        if target.coverpoint_name is None:
            return ResolvedTarget(
                address=target.address,
                feature=feature,
                covergroup=cg,
                coverpoint=None,
                coverpoints=list(cg.coverpoints),
            )

        # CoverPoint-level target
        cp = cg.get_coverpoint(target.coverpoint_name)
        if cp is None:
            raise ValueError(
                f"[CrossEngine] CoverPoint '{target.coverpoint_name}' "
                f"not found in '{target.feature_name}.{target.covergroup_name}'"
            )

        return ResolvedTarget(
            address=target.address,
            feature=feature,
            covergroup=cg,
            coverpoint=cp,
            coverpoints=[cp],
        )

    def synthesize_cross(self, fc: FeatureCross) -> SynthesizedCross:
        """Resolve all targets of a FeatureCross and build a SynthesizedCross."""
        resolved = [self.resolve_target(t) for t in fc.targets]
        return SynthesizedCross(cross_def=fc, resolved_targets=resolved)

    def synthesize_all(self) -> list[SynthesizedCross]:
        """Synthesize all feature crosses in the model."""
        return [self.synthesize_cross(fc) for fc in self.model.feature_crosses]

    def validate(self) -> list[str]:
        """Validate all feature crosses and return list of error messages."""
        errors = []
        for fc in self.model.feature_crosses:
            if len(fc.targets) < 2:
                errors.append(f"FeatureCross '{fc.name}' needs at least 2 targets")
            for t in fc.targets:
                try:
                    self.resolve_target(t)
                except ValueError as e:
                    errors.append(str(e))
        return errors
