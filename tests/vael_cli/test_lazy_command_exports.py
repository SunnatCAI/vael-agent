"""The frozen updater surface on vael_cli.main stays lazy and resolvable.

``vael_cli/update_cmd*.py`` (frozen: old installed versions call into it) reads
helpers off ``vael_cli.main`` via ``_m().<name>``. main.py resolves the ones that
live in the lazily-imported command modules through PEP 562 ``__getattr__`` so
every ``vael`` invocation (including ``vael --version``) does not pay for
update_cmd's dependency chain (jwt, click, ...) when no subcommand runs.
"""

import subprocess
import sys
import textwrap

import pytest

import vael_cli.main

def test_importing_main_does_not_import_command_modules():
    code = textwrap.dedent(
        """
        import sys
        import vael_cli.main  # noqa: F401
        loaded = [
            m
            for m in (
                "vael_cli.update_cmd",
                "vael_cli.sessions_cmd",
                "vael_cli.dashboard_procs",
            )
            if m in sys.modules
        ]
        assert not loaded, f"eagerly imported: {loaded}"
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr

@pytest.mark.real_concurrent_gate  # conftest autouse stub would shadow one frozen name
def test_frozen_updater_surface_resolves_to_real_objects():
    for module, names in vael_cli.main._FROZEN_UPDATER_SURFACE.items():
        mod = sys.modules[module] if module in sys.modules else __import__(module, fromlist=["_"])
        for name in names:
            got = getattr(vael_cli.main, name)
            # Identity, or the same function after another test importlib.reload()ed the module
            # (the resolved value is cached on vael_cli.main by design).
            assert got is getattr(mod, name) or (
                getattr(got, "__module__", None) == module and getattr(got, "__name__", None) == name
            ), name
