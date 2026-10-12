"""Resolve VAEL_HOME for standalone skill scripts.

Skill scripts may run outside the VAEL process (e.g. system Python,
nix env, CI) where ``vael_constants`` is not importable.  This module
provides the same ``get_vael_home()`` and ``display_vael_home()``
contracts as ``vael_constants`` without requiring it on ``sys.path``.

When ``vael_constants`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``vael_constants.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``VAEL_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from vael_constants import display_vael_home as display_vael_home
    from vael_constants import get_vael_home as get_vael_home
except (ModuleNotFoundError, ImportError):

    def get_vael_home() -> Path:
        """Return the VAEL home directory (default: ~/.vael).

        Mirrors ``vael_constants.get_vael_home()``."""
        val = os.environ.get("VAEL_HOME", "").strip()
        return Path(val) if val else Path.home() / ".vael"

    def display_vael_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``vael_constants.display_vael_home()``."""
        home = get_vael_home()
        try:
            return "~/" + home.relative_to(Path.home()).as_posix()
        except ValueError:
            return str(home)
