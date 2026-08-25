"""
digitwin — vendored digiTwin BLUT (v7) support for surrogate_framework.

Contains:
  blut_format.py       — vendored verbatim binary format module (source of truth).
  blut_reader_core.py  — vendored core read/resolve API (open_blut, decode, resolve_requests).
  blut_reader_ext.py   — NEW capability built on top of the vendored reader:
                          bulk/matrix access, $flow current classification,
                          multi-run iteration helpers.
  spec_signal_map.py   — SpecKG <-> BLUT signal-name resolver.
"""
from . import blut_format
from . import blut_reader_core
from . import blut_reader_ext
from . import spec_signal_map

__all__ = ["blut_format", "blut_reader_core", "blut_reader_ext", "spec_signal_map"]
