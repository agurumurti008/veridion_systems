"""
core/templates/param_manifest.py — ParamSpec + ParamManifest.

A ParamManifest is the single source of truth for a template's parameter
set: ordering (vector layout used by every fitter/provider), physical
bounds, log-scale fitting flags, per-state delta eligibility
(mode_affected), and the fit stage each parameter belongs to.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

import numpy as np

VALID_FIT_STAGES = ("dc", "linear", "transient", "fixed")


@dataclass
class ParamSpec:
    name: str            # e.g. "Gm_ea"
    unit: str
    default: float
    lo: float            # fit bound
    hi: float            # fit bound
    log_scale: bool      # fit in log-space for positive-definite params
    mode_affected: bool  # eligible for per-state delta (Section 5)
    fit_stage: str       # "dc" | "linear" | "transient" | "fixed"
    description: str

    def validate(self) -> None:
        if self.fit_stage not in VALID_FIT_STAGES:
            raise ValueError(
                f"ParamSpec {self.name}: fit_stage {self.fit_stage!r} not in "
                f"{VALID_FIT_STAGES}")
        if not (self.lo <= self.default <= self.hi):
            raise ValueError(
                f"ParamSpec {self.name}: default {self.default} outside "
                f"bounds [{self.lo}, {self.hi}]")
        if self.log_scale and self.lo <= 0:
            raise ValueError(
                f"ParamSpec {self.name}: log_scale requires lo > 0 "
                f"(got lo={self.lo})")


class ParamManifest:
    """Ordered parameter manifest with vector/dict conversion, fit-space
    (log where flagged) transforms, bound arrays, and JSON round-trip."""

    def __init__(self, specs: List[ParamSpec]):
        names = [s.name for s in specs]
        if len(set(names)) != len(names):
            dupes = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(f"Duplicate parameter names in manifest: {dupes}")
        for s in specs:
            s.validate()
        self.specs: List[ParamSpec] = list(specs)
        self._by_name: Dict[str, ParamSpec] = {s.name: s for s in specs}

    # ─── Introspection ──────────────────────────────────────────────────────

    @property
    def names(self) -> List[str]:
        return [s.name for s in self.specs]

    def __len__(self) -> int:
        return len(self.specs)

    def __contains__(self, name: str) -> bool:
        return name in self._by_name

    def spec(self, name: str) -> ParamSpec:
        return self._by_name[name]

    def defaults(self) -> Dict[str, float]:
        return {s.name: s.default for s in self.specs}

    def names_for_stage(self, stage: str) -> List[str]:
        return [s.name for s in self.specs if s.fit_stage == stage]

    def mode_affected_names(self) -> List[str]:
        return [s.name for s in self.specs if s.mode_affected]

    # ─── Vector layout ──────────────────────────────────────────────────────

    def to_vector(self, params: Dict[str, float],
                  names: Optional[List[str]] = None) -> np.ndarray:
        """Dict -> ordered vector. `names` restricts/reorders to a subset
        (defaults to the full manifest order). Missing keys fall back to
        manifest defaults so partial dicts round-trip predictably."""
        use = names if names is not None else self.names
        return np.array(
            [float(params.get(n, self._by_name[n].default)) for n in use],
            dtype=float)

    def from_vector(self, vec: np.ndarray,
                    names: Optional[List[str]] = None) -> Dict[str, float]:
        use = names if names is not None else self.names
        vec = np.asarray(vec, dtype=float).reshape(-1)
        if len(vec) != len(use):
            raise ValueError(
                f"from_vector: got {len(vec)} values for {len(use)} names")
        return {n: float(v) for n, v in zip(use, vec)}

    def bounds(self, names: Optional[List[str]] = None):
        """(lo_array, hi_array) in natural units, manifest order (or the
        given subset order)."""
        use = names if names is not None else self.names
        lo = np.array([self._by_name[n].lo for n in use], dtype=float)
        hi = np.array([self._by_name[n].hi for n in use], dtype=float)
        return lo, hi

    # ─── Fit-space transforms (log where flagged) ───────────────────────────

    def to_fit_space(self, vec: np.ndarray,
                     names: Optional[List[str]] = None) -> np.ndarray:
        use = names if names is not None else self.names
        vec = np.asarray(vec, dtype=float).reshape(-1)
        out = vec.copy()
        for i, n in enumerate(use):
            if self._by_name[n].log_scale:
                out[i] = np.log(max(vec[i], 1e-300))
        return out

    def from_fit_space(self, vec: np.ndarray,
                       names: Optional[List[str]] = None) -> np.ndarray:
        use = names if names is not None else self.names
        vec = np.asarray(vec, dtype=float).reshape(-1)
        out = vec.copy()
        for i, n in enumerate(use):
            if self._by_name[n].log_scale:
                out[i] = np.exp(vec[i])
        return out

    def fit_space_bounds(self, names: Optional[List[str]] = None):
        lo, hi = self.bounds(names)
        return (self.to_fit_space(lo, names), self.to_fit_space(hi, names))

    def clip(self, params: Dict[str, float]) -> Dict[str, float]:
        """Clamp a param dict into manifest bounds (unknown keys pass
        through untouched so provider-side extras survive)."""
        out = dict(params)
        for n, v in params.items():
            if n in self._by_name:
                s = self._by_name[n]
                out[n] = float(min(max(v, s.lo), s.hi))
        return out

    # ─── JSON round-trip ────────────────────────────────────────────────────

    def to_json(self) -> str:
        return json.dumps([asdict(s) for s in self.specs], indent=2)

    @classmethod
    def from_json(cls, text: str) -> "ParamManifest":
        raw = json.loads(text)
        return cls([ParamSpec(**d) for d in raw])
