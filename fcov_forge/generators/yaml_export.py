"""
fcov_forge/generators/yaml_export.py
======================================
Exports a FeatureModel back to normalized FCovForge YAML.
Useful for:
  - Normalizing hand-written YAML
  - Round-trip: Excel → FeatureModel → YAML
  - AI extraction output normalization
  - Merging multiple feature files
"""

from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml

from core.model import FeatureModel, Feature, CoverGroup, CoverPoint, CoverBin, BinType, FeatureCross


def _bin_to_dict(b: CoverBin) -> dict:
    d: dict[str, Any] = {"name": b.name}

    if b.bin_type != BinType.VALUES:
        d["type"] = b.bin_type.value

    if b.values:
        d["values"] = b.values
    if b.ranges:
        d["ranges"] = [list(r) for r in b.ranges]
    if b.transitions:
        d["transitions"] = b.transitions
    if b.wildcard_pattern:
        d["pattern"] = b.wildcard_pattern
    if b.auto_bin_max is not None:
        d["auto_bin_max"] = b.auto_bin_max
    if b.min_hits > 1:
        d["min_hits"] = b.min_hits
    if b.weight is not None:
        d["weight"] = b.weight
    if b.comment:
        d["comment"] = b.comment

    return d


def _cp_to_dict(cp: CoverPoint) -> dict:
    d: dict[str, Any] = {"name": cp.name, "variable": cp.variable}
    if cp.condition:
        d["condition"] = cp.condition
    if cp.comment:
        d["comment"] = cp.comment
    if cp.bins:
        d["bins"] = [_bin_to_dict(b) for b in cp.bins]
    return d


def _cross_to_dict(cross) -> dict:
    d: dict[str, Any] = {"name": cross.name, "coverpoints": cross.coverpoints}
    if cross.exclude_bins:
        d["exclude_bins"] = cross.exclude_bins
    if cross.comment:
        d["comment"] = cross.comment
    return d


def _cg_to_dict(cg: CoverGroup) -> dict:
    d: dict[str, Any] = {"name": cg.name}
    if cg.clock_event:
        d["clock"] = cg.clock_event
    if cg.sample_condition:
        d["condition"] = cg.sample_condition
    if cg.per_instance:
        d["per_instance"] = True
    if cg.auto_bin_max is not None:
        d["auto_bin_max"] = cg.auto_bin_max
    if cg.goal is not None and cg.goal != 100:
        d["goal"] = cg.goal
    if cg.comment:
        d["comment"] = cg.comment
    if cg.args:
        d["args"] = [{"type": t, "name": n} for t, n in cg.args]
    if cg.coverpoints:
        d["coverpoints"] = [_cp_to_dict(cp) for cp in cg.coverpoints]
    if cg.crosses:
        d["crosses"] = [_cross_to_dict(c) for c in cg.crosses]
    return d


def _feature_to_dict(feat: Feature) -> dict:
    d: dict[str, Any] = {"name": feat.name}
    if feat.description:
        d["description"] = feat.description
    if feat.tags:
        d["tags"] = feat.tags
    if feat.source_doc:
        d["source_doc"] = feat.source_doc
    if feat.covergroups:
        d["covergroups"] = [_cg_to_dict(cg) for cg in feat.covergroups]
    return d


def _feature_cross_to_dict(fc: FeatureCross) -> dict:
    d: dict[str, Any] = {
        "name": fc.name,
        "targets": [t.address for t in fc.targets],
    }
    if fc.goal and fc.goal != 100:
        d["goal"] = fc.goal
    if fc.comment:
        d["comment"] = fc.comment
    if fc.exclude_combinations:
        d["exclude_combinations"] = fc.exclude_combinations
    return d


def export_to_yaml(model: FeatureModel, output: Path | None = None) -> str:
    """
    Export FeatureModel to normalized YAML string.
    Optionally write to file if output path given.
    """
    doc: dict[str, Any] = {"project": model.project_name}

    if model.metadata:
        doc["metadata"] = model.metadata

    if model.features:
        doc["features"] = [_feature_to_dict(f) for f in model.features]

    if model.feature_crosses:
        doc["feature_crosses"] = [_feature_cross_to_dict(fc) for fc in model.feature_crosses]

    yaml_str = yaml.dump(doc, default_flow_style=False, sort_keys=False, allow_unicode=True)

    if output:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(yaml_str, encoding="utf-8")

    return yaml_str


def merge_models(models: list[FeatureModel], project_name: str) -> FeatureModel:
    """
    Merge multiple FeatureModels into one.
    Features with duplicate names are merged (covergroups unioned).
    """
    from core.model import FeatureModel

    merged_features: dict[str, Feature] = {}
    all_crosses: list = []

    for model in models:
        for feat in model.features:
            if feat.name not in merged_features:
                merged_features[feat.name] = feat
            else:
                # Merge covergroups
                existing_cg_names = {cg.name for cg in merged_features[feat.name].covergroups}
                for cg in feat.covergroups:
                    if cg.name not in existing_cg_names:
                        merged_features[feat.name].covergroups.append(cg)

        all_crosses.extend(model.feature_crosses)

    # Deduplicate crosses by name
    seen_crosses = set()
    unique_crosses = []
    for fc in all_crosses:
        if fc.name not in seen_crosses:
            seen_crosses.add(fc.name)
            unique_crosses.append(fc)

    return FeatureModel(
        project_name=project_name,
        features=list(merged_features.values()),
        feature_crosses=unique_crosses,
    )
