#!/usr/bin/env python3
"""
digitwin/spec_signal_map.py — SpecKG <-> BLUT signal-name resolution.

Real designs' internal hierarchy names (top.u1.vref, xdut.mp0.d) never
match the short port names in a SpecKG (VREF, VOUT, EN). SignalMap bridges
the two, with kind-aware disambiguation for the common case where the same
BLUT base name is exported twice: once as a voltage and once as its $flow
current pair (e.g. top.u1.vout and top.u1.vout$flow both map to base name
"top.u1.vout" but must resolve to different SpecKG names/kinds).
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from .blut_reader_ext import (classify_signal_kind, strip_kind_suffix,
                              DEFAULT_CURRENT_SUFFIXES)

log = logging.getLogger("digitwin.spec_signal_map")


@dataclass
class SignalMapEntry:
    speckg_name: str                     # e.g. "VOUT" — must match a Port.name or SpecConstraint.name
    blut_signal: str                     # e.g. "top.u1.vout" (base name, no $flow suffix)
    kind: str                            # "voltage" | "current" — must agree with classify_signal_kind
    run_scope: Optional[str] = None      # None = applies to all runs; else restrict to one run_id


class SignalMap:
    """Bidirectional, kind-disambiguated SpecKG <-> BLUT signal name map."""

    def __init__(self, entries: Optional[List[SignalMapEntry]] = None):
        self.entries: List[SignalMapEntry] = list(entries) if entries else []
        self._warned_once: bool = False

    # ─── Construction ──────────────────────────────────────────────────────

    @classmethod
    def from_spec_json(cls, spec_json_path: str) -> "SignalMap":
        """Reads an optional top-level "signal_map" array from the spec
        JSON. Returns an empty SignalMap if the key is absent (backward
        compatible with existing ldo_spec.json / ota_spec.json, which have
        no such key)."""
        if not spec_json_path or not os.path.exists(spec_json_path):
            return cls()

        with open(spec_json_path, encoding='utf-8') as f:
            data = json.load(f)

        raw_entries = data.get("signal_map", [])
        entries = []
        for e in raw_entries:
            blut_signal = e["blut_signal"]
            kind = e.get("kind", "voltage")
            # The reader strips the current-probe suffix ($flow) before
            # reverse_resolve, so a map that stores the full probe path
            # (e.g. "...X_DUT.VDD_1V2_$flow") must be normalized to the base
            # name here or its current entries never match. Voltage entries
            # are untouched.
            if kind == "current":
                blut_signal = strip_kind_suffix(blut_signal)
            entries.append(SignalMapEntry(
                speckg_name=e["speckg_name"],
                blut_signal=blut_signal,
                kind=kind,
                run_scope=e.get("run_scope"),
            ))
        return cls(entries)

    def to_json_list(self) -> List[dict]:
        """Serialize entries back to the JSON-schema list form, for
        round-tripping through SpecKG.export_to_json."""
        return [
            {
                "speckg_name": e.speckg_name,
                "blut_signal": e.blut_signal,
                "kind": e.kind,
                "run_scope": e.run_scope,
            }
            for e in self.entries
        ]

    def add(self, entry: SignalMapEntry) -> None:
        self.entries.append(entry)

    # ─── Resolution ─────────────────────────────────────────────────────────

    def resolve(self, speckg_name: str, run_id: Optional[str] = None) -> Optional[str]:
        """speckg_name -> blut_signal, honoring run_scope. Run-scoped
        entries take priority over unscoped (run_scope=None) entries for
        the same speckg_name when run_id is given. Returns None if unmapped."""
        scoped_match = None
        unscoped_match = None
        for e in self.entries:
            if e.speckg_name != speckg_name:
                continue
            if e.run_scope is not None:
                if run_id is not None and e.run_scope == run_id:
                    scoped_match = e.blut_signal
            else:
                unscoped_match = e.blut_signal
        return scoped_match if scoped_match is not None else unscoped_match

    def resolve_with_kind(
        self, speckg_name: str, kind: str, run_id: Optional[str] = None
    ) -> Optional[str]:
        """Like resolve(), but additionally disambiguates by kind — needed
        when the same speckg_name family maps a voltage and a current entry
        (e.g. VOUT voltage vs IOUT current) or, more importantly, when two
        DIFFERENT speckg_names map to the SAME blut_signal under different
        kinds. Prefer this over resolve() whenever the caller knows which
        kind it wants."""
        scoped_match = None
        unscoped_match = None
        for e in self.entries:
            if e.speckg_name != speckg_name or e.kind != kind:
                continue
            if e.run_scope is not None:
                if run_id is not None and e.run_scope == run_id:
                    scoped_match = e.blut_signal
            else:
                unscoped_match = e.blut_signal
        return scoped_match if scoped_match is not None else unscoped_match

    def reverse_resolve(
        self, blut_signal: str, run_id: Optional[str] = None, kind: Optional[str] = None
    ) -> Optional[str]:
        """blut_signal -> speckg_name, for labeling decoded arrays back onto
        ports/specs. If kind is given, disambiguates the same blut_signal
        mapped twice under different kinds (voltage vs current)."""
        scoped_match = None
        unscoped_match = None
        for e in self.entries:
            if e.blut_signal != blut_signal:
                continue
            if kind is not None and e.kind != kind:
                continue
            if e.run_scope is not None:
                if run_id is not None and e.run_scope == run_id:
                    scoped_match = e.speckg_name
            else:
                unscoped_match = e.speckg_name
        return scoped_match if scoped_match is not None else unscoped_match

    # ─── Diagnostics ────────────────────────────────────────────────────────

    def unmapped_speckg_names(self, kg) -> List[str]:
        """Every Port.name and SpecConstraint.name in kg with no SignalMap
        entry at all (any kind, any scope)."""
        mapped_names = {e.speckg_name for e in self.entries}
        all_names = {p.name for p in kg.ports} | {s.name for s in kg.specs}
        return sorted(all_names - mapped_names)

    def print_unmapped_warning(self, kg, force: bool = False) -> None:
        """Print the unmapped-names table once per SignalMap instance (the
        mapping gap is a property of (signal_map, spec_kg), not of any
        individual caller/run, so repeated calls — e.g. one per BLUT run in
        a multi-run FSM/reference pass — print the identical table only
        once unless force=True)."""
        if getattr(self, '_warned_once', False) and not force:
            return
        unmapped = self.unmapped_speckg_names(kg)
        if not unmapped:
            self._warned_once = True
            return
        print(f"\n[SignalMap] WARNING: {len(unmapped)} SpecKG name(s) have no BLUT "
              f"signal mapping and will fall back to raw BLUT names if present:")
        for name in unmapped:
            print(f"    - {name}")
        print()
        self._warned_once = True

    def auto_suggest(self, kg, blut_names: Dict[str, dict]) -> List[SignalMapEntry]:
        """Best-effort fuzzy suggestion: case-insensitive suffix/substring
        match of kg Port/SpecConstraint names against BLUT base names.
        Printed as a ready-to-paste JSON snippet; NEVER applied automatically
        — the caller must review and explicitly construct a SignalMap from
        the suggestions (or hand-edit the spec JSON)."""
        kg_names = [p.name for p in kg.ports] + [s.name for s in kg.specs]
        kg_names = sorted(set(kg_names))

        suggestions: List[SignalMapEntry] = []
        for kg_name in kg_names:
            kg_lower = kg_name.lower()
            best_match = None
            best_kind = "voltage"
            for key, info in blut_names.items():
                base_lower = info["base_name"].lower()
                # substring or suffix match either direction
                if kg_lower in base_lower or base_lower.endswith(kg_lower) or \
                   base_lower.split(".")[-1] == kg_lower:
                    best_match = info["base_name"]
                    best_kind = info["kind"]
                    break
            if best_match is not None:
                suggestions.append(SignalMapEntry(
                    speckg_name=kg_name,
                    blut_signal=best_match,
                    kind=best_kind,
                ))

        if suggestions:
            print(f"\n[SignalMap] Auto-suggested mapping ({len(suggestions)} entries) — "
                  f"review before use, paste into spec JSON \"signal_map\" if correct:")
            print(json.dumps([
                {"speckg_name": s.speckg_name, "blut_signal": s.blut_signal, "kind": s.kind}
                for s in suggestions
            ], indent=2))
            print()
        else:
            print("\n[SignalMap] Auto-suggest found no plausible matches — "
                  "write the signal_map by hand.\n")

        return suggestions
