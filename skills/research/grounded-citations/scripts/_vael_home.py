"""Resolve VAEL_HOME for standalone skill scripts.

Skill scripts may run outside the VAEL process (system Python, nix env,
CI) where ``vael_constants`` is not importable.  This module provides the
same ``get_vael_home()`` contract without requiring it on ``sys.path``.

When ``vael_constants`` IS available it is used directly so profile
resolution and any future enhancements are picked up automatically.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from vael_constants import get_vael_home as get_vael_home
except (ModuleNotFoundError, ImportError):

    def get_vael_home() -> Path:
        """Return the VAEL home directory (default: ``~/.vael``)."""
        val = os.environ.get("VAEL_HOME", "").strip()
        return Path(val) if val else Path.home() / ".vael"
