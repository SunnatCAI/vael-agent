"""Welcome page, skills summary, and update check for the CLI."""
import json
import logging
import os
import re
import shutil
import sys
import threading
from pathlib import Path
from vael_cli import source_check
# Historical updater import (tests/compat/old_updater_surface.json). In-tree callers use the owner.
from vael_cli.source_check import _github_compare_behind  # noqa: F401
from vael_constants import get_vael_home
from typing import TYPE_CHECKING, Any, Dict, List, Optional

# rich and prompt_toolkit are imported lazily: this module sits on the TUI gateway's critical
# startup path purely for the lightweight update-check helpers, and eager rich/prompt_toolkit
# imports cost ~50ms before ``gateway.ready`` could fire.
if TYPE_CHECKING:
    from rich.console import Console

logger = logging.getLogger(__name__)

# ANSI building blocks for conversation display (``_DIM``/``_RST`` are imported by callbacks.py).
_DIM = "\033[2m"
_RST = "\033[0m"


def _check_via_pypi() -> Optional[int]:
    # Shim to stop the old updater doing work until relaunch. no registry query.
    return None


def check_via_pypi() -> Optional[int]:
    # Shim to stop the old updater doing work until relaunch. status is unknown.
    return None


def _quiet(fn, default=None):
    """``fn()``, or ``default`` on any exception — for best-effort display inputs."""
    try:
        return fn()
    except Exception:
        return default


def cprint(text: str):
    """Print ANSI-colored text through prompt_toolkit's renderer."""
    from prompt_toolkit import print_formatted_text as _pt_print
    from prompt_toolkit.formatted_text import ANSI as _PT_ANSI
    # prompt_toolkit needs a real console: on Windows a redirected/absent stdout raises
    # NoConsoleScreenBufferError, and display helpers must never crash the caller over that.
    if _quiet(lambda: _pt_print(_PT_ANSI(text)) or True) is None:
        print(text)


def _active_skin():
    """The active skin object (raises when the skin engine is unavailable)."""
    from vael_cli.skin_engine import get_active_skin
    return get_active_skin()


def _skin_color(key: str, fallback: str) -> str:
    """Get a color from the active skin, or return fallback."""
    return _quiet(lambda: _active_skin().get_color(key, fallback), fallback)


# === Branding ===

from vael_cli import __release_date__ as RELEASE_DATE
from vael_cli.version_info import get_version_info

# === Skills scanning ===

# Per-process caches: ``None`` until computed, then a 1-tuple ``(value,)`` so a computed ``None``
# is distinguishable from "not yet computed". Reset by assigning ``None`` (tests, ``vael skills``).
_available_skills_cache: Optional[tuple] = None
_git_banner_state_cache: Optional[tuple] = None
_latest_release_cache: Optional[tuple] = None

_UNCACHED = object()  # compute() result that must not be memoized


def _memo(cache_name: str, compute):
    """Return the cached value under module global ``cache_name``, computing (and storing) it once.

    Not consulted under a routed profile (VAEL_HOME override): every memo here is derived from the
    launch home (its skills tree, its checkout), and the TUI gateway calls these per profile."""
    from vael_constants import get_vael_home_override
    if get_vael_home_override() is not None:
        return compute()
    cached = globals()[cache_name]
    if cached is not None:
        return cached[0]
    value = compute()
    if value is not _UNCACHED:
        globals()[cache_name] = (value,)
    return value


def get_available_skills() -> Dict[str, List[str]]:
    """Return skills grouped by category, filtered by platform and disabled state.

    Cached per-process (the skills-tree walk costs ~100ms and feeds only the startup banner);
    ``prefetch_banner_data()`` pays it off-thread. A failed scan yields ``{}`` and is not cached.
    """
    def _scan():
        from tools.skills_tool import _find_all_skills
        return _find_all_skills()  # already filtered

    def _compute():
        all_skills = _quiet(_scan)
        if all_skills is None:
            return _UNCACHED
        skills_by_category: Dict[str, List[str]] = {}
        for skill in all_skills:
            skills_by_category.setdefault(skill.get("category") or "general", []).append(skill["name"])
        return skills_by_category
    result = _memo("_available_skills_cache", _compute)
    return {} if result is _UNCACHED else result


def _resolve_repo_dir() -> Optional[Path]:
    """The active VAEL git checkout, or None if this isn't a git install.

    Prefers the running code's location: ``$VAEL_HOME/vael-agent/`` may be a stale copy
    carried over by ``--clone-all``.
    """
    repo_dir = Path(__file__).parent.parent.resolve()
    if not (repo_dir / ".git").exists():
        repo_dir = get_vael_home() / "vael-agent"
    return repo_dir if (repo_dir / ".git").exists() else None


def get_git_banner_state(repo_dir: Optional[Path] = None) -> Optional[dict]:
    """Return upstream/local git hashes for the startup banner.

    Cached per-process (default ``repo_dir`` only): 2-3 git subprocesses (~100ms) whose result
    cannot change under a running CLI. The cache lets ``prefetch_banner_data()`` pay it off-thread.
    """
    if repo_dir is not None:
        return _compute_git_banner_state(repo_dir)
    return _memo("_git_banner_state_cache", _compute_git_banner_state)


def _baked_banner_state() -> Optional[dict]:
    """Banner state from the baked build SHA (Docker image path), or None."""
    def _baked():
        from vael_cli.version_info import get_code_identity
        return get_code_identity().get("short_sha")
    baked = _quiet(_baked)
    return {"upstream": baked, "local": baked, "ahead": 0} if baked else None


def _compute_git_banner_state(repo_dir: Optional[Path] = None) -> Optional[dict]:
    repo_dir = repo_dir or _resolve_repo_dir()
    if repo_dir is None:
        return _baked_banner_state()
    upstream, local = (source_check._git_stdout(["rev-parse", "--short=8", rev], cwd=repo_dir) for rev in ("origin/main", "HEAD"))
    if not upstream or not local:
        # Live-git lookup failed (e.g. shallow clone without origin/main).
        return _baked_banner_state()
    ahead = source_check._git_count(["rev-list", "--count", "origin/main..HEAD"], cwd=repo_dir) or 0
    return {"upstream": upstream, "local": local, "ahead": max(ahead, 0)}


_RELEASE_URL_BASE = "https://github.com/sunnatilla0717/vael-agent/releases/tag"


def get_latest_release_tag(repo_dir: Optional[Path] = None) -> Optional[tuple]:
    """Return ``(tag, release_url)`` for the latest local git tag, or None (a miss is cached too).

    Release URL always points at the canonical sunnatilla0717/vael-agent repo (forks get no link).
    """
    def _compute():
        rd = repo_dir or _resolve_repo_dir()
        tag = source_check._git_stdout(["describe", "--tags", "--abbrev=0"], cwd=rd, timeout=3) if rd else None
        return (tag, f"{_RELEASE_URL_BASE}/{tag}") if tag else None
    return _memo("_latest_release_cache", _compute)


def format_banner_version_label() -> str:
    """Return the version label shown in the startup banner title."""
    from vael_cli.config import get_project_root
    from vael_cli.steward import read_install_stamp
    from vael_cli.update_channel import is_canary_tag

    stamp = read_install_stamp(get_project_root())
    if stamp.get("distribution") == "desktop-app":
        label = f"VAEL Agent v{get_version_info().derived_version}"
        if stamp.get("source") == "commit-build":
            return f"{label} · commit-build · {str(stamp.get('commit') or '')[:12]}"
        if stamp.get("tag"):
            channel = "canary" if is_canary_tag(stamp["tag"]) else "stable"
            return f"{label} · {channel}"
        if stamp.get("payload") == "bootstrap":
            # The old installer shell's CLI backend: the shell never updates
            # itself (`self`), the managed checkout under it does. Name the
            # shell so it doesn't read as a plain packaged build.
            return f"{label} · installer"
        return label

    base = f"VAEL Agent v{get_version_info().derived_version} ({RELEASE_DATE})"
    from vael_cli.config import load_config
    from vael_cli.update_channel import resolve_update_channel

    channel = resolve_update_channel(_quiet(load_config), get_project_root())
    if channel != "main":
        head = source_check._git_stdout(["rev-parse", "HEAD"], cwd=get_project_root())
        return f"{base} · {channel}" + (f" · local {head[:12]}" if head else "")
    state = get_git_banner_state()
    if not state:
        return base
    upstream, local = state["upstream"], state["local"]
    ahead = int(state.get("ahead") or 0)
    if ahead <= 0 or upstream == local:
        return f"{base} · upstream {upstream}"
    return f"{base} · upstream {upstream} · local {local} (+{ahead} carried {_plural(ahead, 'commit')})"


# === Non-blocking update check ===

_update_result: Optional[int] = None
_update_check_done = threading.Event()


def _daemon(name: Optional[str], target) -> None:
    """Start a daemon thread running ``target`` with any exception swallowed."""
    threading.Thread(target=lambda: _quiet(target), name=name, daemon=True).start()


def _skip_background_prefetch() -> bool:
    """True when the banner's background prefetch threads must not start.

    Under pytest the prefetch daemon threads shell out to git (``rev-parse``,
    ``remote get-url``, the banner's git state) at an arbitrary point after
    import, and any test that patches the process-wide ``subprocess`` singleton
    (``patch("subprocess.run")`` / ``patch("subprocess.Popen")``) can record
    that stray spawn in place of the call it meant to pin.  Importing
    ``tui_gateway.server`` starts this prefetch, which is what flaked
    tests/tui_gateway/test_bot_relay_methods.py.
    Nothing under pytest needs a live update check; tests that exercise the
    prefetch itself monkeypatch this predicate to False.

    ``PYTEST_CURRENT_TEST`` is only set while a test runs, not during
    collection-time imports, hence the ``sys.modules`` check as well.
    """
    return "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules


def prefetch_update_check():
    """Kick off update check in a background daemon thread.

    No-op under pytest — see ``_skip_background_prefetch``.
    """
    if _skip_background_prefetch():
        _update_check_done.set()
        return

    def _run():
        global _update_result
        _update_result = source_check.check_for_updates(passive=True).get("behind")
        _update_check_done.set()
    _daemon(None, _run)


_banner_data_prefetch_started = False


def prefetch_banner_data():
    """Warm the banner's subprocess/I/O-heavy inputs in a daemon thread.

    Git state (~130ms) and the skills index (~110ms) are cached per-process by their own modules,
    so warming them while the main thread pays the CPU-bound imports overlaps GIL-releasing I/O
    with import work. Idempotent; failures don't matter because the banner recomputes anything missing.
    """
    global _banner_data_prefetch_started
    if _banner_data_prefetch_started:
        return
    if _skip_background_prefetch():
        # Same stray-git-spawn cross-talk class as prefetch_update_check:
        # get_git_banner_state() shells out via the shared subprocess
        # singleton from a daemon thread, poisoning process-wide subprocess
        # mocks in unrelated tests.
        _banner_data_prefetch_started = True
        return
    _banner_data_prefetch_started = True
    _daemon("banner-data-prefetch", lambda: [_quiet(warm) for warm in (
        get_git_banner_state, get_latest_release_tag, get_available_skills)])


def get_update_result(timeout: float = 0.5) -> Optional[int]:
    """Get result of prefetched check. Returns None if not ready."""
    _update_check_done.wait(timeout=timeout)
    return _update_result


def _update_notice_parts(behind: int) -> tuple:
    """``(text, command)`` for a non-zero ``behind`` result; ``command`` may be empty."""
    from vael_cli.config import get_managed_update_command, recommended_update_command
    if behind > 0:
        return f"{behind} {_plural(behind, 'commit')} behind", recommended_update_command()
    # UPDATE_AVAILABLE_NO_COUNT (nix): an update exists but we don't know by how much, nor how
    # the user installed (nix run, profile, system flake, home-manager).
    return "update available", get_managed_update_command() or ""


def _format_update_notice(behind: int) -> str:
    """Render the update warning line for a non-zero ``behind`` result."""
    text, command = _update_notice_parts(behind)
    suffix = f"[dim yellow] — run [bold]{command}[/bold]{' to update' if behind > 0 else ''}[/]" if command else ""
    return f"[bold yellow]⚠ {text}[/]{suffix}"


_deferred_update_notice_started = False


def _render_markup_to_ansi(markup: str) -> str:
    """Rich markup → ANSI string, for output that must go through prompt_toolkit's renderer.

    Under ``patch_stdout`` (the interactive CLI), a plain ``Console.print`` writes ESC bytes into
    the StdoutProxy, which sanitizes them into visible ``?[1;33m…`` artifacts (#83969).
    """
    from io import StringIO
    from rich.console import Console as _Console
    buf = StringIO()
    _Console(file=buf, force_terminal=True, color_system="truecolor", highlight=False).print(markup)
    return buf.getvalue().rstrip("\n")


def _defer_update_notice(max_wait: float = 30.0) -> None:
    """Print the update warning once the prefetched check completes (at most once per process).

    Used when the banner rendered before the update prefetch finished so startup never blocks on
    git/network. The notice lands after prompt_toolkit owns the terminal, so it is routed through
    ``cprint`` (prompt_toolkit's renderer prints above a running application from any thread).
    """
    global _deferred_update_notice_started
    if _deferred_update_notice_started:
        return
    _deferred_update_notice_started = True

    def _wait_and_print() -> None:
        if _update_check_done.wait(timeout=max_wait) and _update_result:
            if _uses_hero_layout(_quiet(_active_skin)):
                cprint(_render_markup_to_ansi(_format_update_notice(_update_result)))
            else:
                from vael_cli.journal import notice_ansi
                cprint(notice_ansi("update", *_update_notice_parts(_update_result)))
    _daemon("update-notice", _wait_and_print)  # never break the session over an update notice


# === Welcome banner ===

def _plural(n: int, word: str) -> str:
    return word if n == 1 else f"{word}s"


def _format_context_length(tokens: int) -> str:
    """Format a token count for display (e.g. 128000 → '128K', 1048576 → '1M')."""
    for unit, div in (("M", 1_000_000), ("K", 1_000)):
        if tokens >= div:
            val = tokens / div
            rounded = round(val)
            return f"{rounded}{unit}" if abs(val - rounded) < 0.05 else f"{val:.1f}{unit}"
    return str(tokens)


def _display_toolset_name(toolset_name: str) -> str:
    """Normalize internal/legacy toolset identifiers for banner display."""
    return toolset_name.removesuffix("_tools") if toolset_name else "unknown"


def _short_label(name: str) -> str:
    """Truncate a model/preset slug to fit the banner's left column."""
    return name[:25] + "..." if len(name) > 28 else name


# === Banner snapshot — warm-launch fast path ===
# The tool panel needs the full tool registry (~0.5-0.9s cold, the largest chunk of time-to-
# banner). The list is a pure function of (config.yaml, .env, code checkout, enabled toolsets),
# so the rendered inputs are snapshotted to disk and replayed when the fingerprint matches. The
# agent's REAL tool list is still computed fresh at first message; the snapshot only feeds the
# cosmetic panel, and a background refresh (cli.show_banner) re-verifies it right after render.

_BANNER_SNAPSHOT_VERSION = 1


def _banner_snapshot_path() -> Path:
    return get_vael_home() / "cache" / "banner_snapshot.json"


def banner_snapshot_fingerprint() -> Optional[str]:
    """Fingerprint the inputs the banner tool panel depends on."""
    import hashlib
    def _inputs():
        from vael_cli.config import get_config_path
        return (get_config_path(), get_vael_home() / ".env")
    paths = _quiet(_inputs)
    if paths is None:
        return None
    parts = [f"v{_BANNER_SNAPSHOT_VERSION}"]
    for p in paths:
        st = _quiet(p.stat)
        parts.append(f"{p.name}:{st.st_mtime_ns}:{st.st_size}" if st else f"{p.name}:absent")
    # Code checkout: commit when known, otherwise its derived version.
    version_info = get_version_info()
    parts.append(version_info.commit or version_info.derived_version)
    state = get_git_banner_state()
    if state:
        parts.append(str(state.get("local", "")))
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def load_banner_snapshot(enabled_toolsets: List[str] = None) -> Optional[Dict[str, Any]]:
    """Return the stored banner snapshot when its fingerprint is current."""
    blob = _quiet(lambda: json.loads(_banner_snapshot_path().read_text(encoding="utf-8-sig")))
    if not isinstance(blob, dict):
        return None
    fp = banner_snapshot_fingerprint()
    if (not fp or blob.get("fingerprint") != fp
            or blob.get("enabled_toolsets") != sorted(enabled_toolsets or [])
            or not isinstance(blob.get("tools"), list)
            or not all(isinstance(blob.get(k), dict)
                       for k in ("toolset_map", "availability", "skills_by_category"))):
        return None
    return blob


def save_banner_snapshot(tools: List[dict], enabled_toolsets: List[str], availability: Dict[str, Any],
                         toolset_map: Dict[str, str]) -> None:
    """Persist the banner tool panel inputs for next launch (best-effort)."""
    fp = banner_snapshot_fingerprint()
    if not fp:
        return
    payload = {
        "fingerprint": fp,
        "enabled_toolsets": sorted(enabled_toolsets or []),
        "tools": [{"function": {"name": t["function"]["name"]}}
                  for t in tools if isinstance(t, dict) and t.get("function", {}).get("name")],
        "toolset_map": toolset_map,
        "availability": {
            "unavailable_toolsets": availability.get("unavailable_toolsets", []),
            **{k: list(availability.get(k, [])) for k in ("lazy_tools", "disabled_tools")}},
        "skills_by_category": get_available_skills(),
    }

    def _write():
        from utils import atomic_json_write
        atomic_json_write(_banner_snapshot_path(), payload, indent=None, mode=0o600)
    _quiet(_write)


def compute_toolset_availability(enabled_toolsets: List[str] = None) -> Dict[str, Any]:
    """Compute ``{"unavailable_toolsets", "lazy_tools", "disabled_tools"}`` for the banner.

    Split out so the result can be snapshotted and replayed without importing ``model_tools``.
    """
    from model_tools import check_tool_availability, TOOLSET_REQUIREMENTS
    enabled_toolsets = enabled_toolsets or []
    _, unavailable_toolsets = check_tool_availability(quiet=True)
    # The availability check walks the GLOBAL registry, so it includes toolsets outside this
    # agent's platform set (e.g. `discord` on a CLI session) which must never surface in
    # "Available Tools". Restrict to enabled toolsets; an enabled toolset with unmet deps
    # legitimately shows as disabled/lazy below.
    _enabled_ts = {str(t) for t in enabled_toolsets}
    if _enabled_ts:
        unavailable_toolsets = [
            item for item in unavailable_toolsets if str(item.get("id", item.get("name", ""))) in _enabled_ts]
    # Toolsets with a check_fn are lazy-initialized (e.g. honcho): unavailable at banner time
    # because the check hasn't run yet, but not misconfigured.
    lazy_tools, disabled_tools = set(), set()
    for item in unavailable_toolsets:
        is_lazy = TOOLSET_REQUIREMENTS.get(item.get("name", ""), {}).get("check_fn")
        (lazy_tools if is_lazy else disabled_tools).update(item.get("tools", []))
    return {"unavailable_toolsets": unavailable_toolsets, "lazy_tools": sorted(lazy_tools),
            "disabled_tools": sorted(disabled_tools)}


def _mcp_server_line(srv: dict, *, dim: str, text: str) -> str:
    """One banner line for an MCP server status entry."""
    name, transport = srv["name"], srv["transport"]
    if srv["connected"]:
        return f"[dim {dim}]{name}[/] [{text}]({transport})[/] [dim {dim}]—[/] [{text}]{srv['tools']} tool(s)[/]"
    # Needs srv['tools'], so it cannot live in the suffix dict below. A registered but unspawned
    # server has callable tools; falling through to the red "failed" line misreports a working setup.
    if srv.get("status") == "lazy":
        return (f"[dim {dim}]{name}[/] [{text}]({transport})[/] [dim {dim}]—[/] "
                f"[{text}]{srv['tools']} tool(s)[/] [dim {dim}](lazy, starts on first use)[/]")
    status = "disabled" if srv.get("disabled") else srv.get("status")
    suffix = {"disabled": f"[dim {dim}]— disabled[/]", "connecting": "[yellow]— connecting[/]",
              "configured": f"[dim {dim}]— configured[/]"}.get(status)
    if suffix is not None:
        return f"[dim {dim}]{name}[/] [dim]({transport})[/] {suffix}"
    return _mcp_failed_line(name, transport, srv.get("error"))


def _mcp_failed_line(name: str, transport: str, error: Optional[str]) -> str:
    """Failed MCP connect: the short reason (already humanised by ``_format_connect_error``) and the
    exact next command, so 'failed' is never the whole story."""
    from rich.markup import escape
    reason = escape(" ".join(str(error or "").split())[:120]) or "no details recorded"
    next_cmd = (f"vael mcp login {name}" if re.search(r"\b401\b|unauthori[sz]ed", reason, re.I)
                else f"vael mcp test {name}")
    return (f"[red]{name}[/] [dim]({transport})[/] [red]— could not connect:[/] {reason} "
            f"[dim]— run `{next_cmd}`[/]")


def _truncate_tool_names(tool_names: List[str]) -> List[Optional[str]]:
    """Cut a toolset's tool list to ~42 columns; ``None`` marks the elided tail."""
    if len(", ".join(tool_names)) <= 45:
        return list(tool_names)
    short_names: List[Optional[str]] = []
    length = 0
    for name in tool_names:
        if length + len(name) + 2 > 42:
            short_names.append(None)
            break
        short_names.append(name)
        length += len(name) + 2
    return short_names


def _pack_skill_names(skill_names: List[str], avail: int) -> str:
    """Join skill names into ``avail`` columns, ending with ``+N more`` when they don't all fit."""
    parts: List[str] = []
    length = 0
    for i, name in enumerate(skill_names):
        needed = (2 if parts else 0) + len(name)
        after = len(skill_names) - (i + 1)  # indicator size IF we add this skill then stop
        ind_len = len(f", +{after} more") if after > 0 else 0
        if parts and length + needed + ind_len > avail:
            parts.append(f"+{len(skill_names) - len(parts)} more")
            break
        parts.append(name)
        length += needed
    return ", ".join(parts)


def _moa_aggregator_label(preset_name: str) -> str:
    """Short aggregator-model label for a MoA preset ("" when the preset has none)."""
    from vael_cli.config import load_config
    from vael_cli.moa_config import normalize_moa_config
    preset = normalize_moa_config(load_config().get("moa") or {}).get("presets", {}).get(preset_name)
    model = str(((preset or {}).get("aggregator") or {}).get("model") or "")
    return model.split("/")[-1]


def _mcp_configured() -> bool:
    """Cheap probe: does config.yaml or the persisted plugin key cache name any MCP server?

    The full ``get_mcp_status()`` path resolves portable plugin MCP servers, which JOINS the in-flight
    background plugin discovery (~100ms on the startup path), so skip it when nothing is configured.
    When either probe can't tell, take the full path.
    """
    def _native():
        from vael_cli.config import load_config
        return bool((load_config() or {}).get("mcp_servers"))

    def _portable():
        from vael_cli.plugins import get_portable_mcp_server_names_nowait
        return bool(get_portable_mcp_server_names_nowait())
    return _quiet(_native, True) or _quiet(_portable, True)


def _probe_mcp_status() -> list:
    from tools.mcp_tool_discovery import get_mcp_status
    return get_mcp_status()


def _codex_runtime_active() -> bool:
    """True when the codex_app_server runtime is active (tool counts then live inside codex)."""
    from vael_cli.codex_runtime_switch import get_current_runtime
    from vael_cli.config import load_config
    return get_current_runtime(load_config()) == "codex_app_server"


def _active_profile_name() -> Optional[str]:
    from vael_cli.profiles import get_active_profile_name
    return get_active_profile_name()


def _route_model_for_banner(provider: Any) -> str:
    """The model the resolved route will actually serve when config names none: today only the Nous
    free tier (welcome host -> ``nous/welcome``). Read from the boot record and local auth state;
    no network. Empty when nothing resolves, so the caller keeps its "no model configured" line."""
    if (provider or "auto").strip().lower() not in ("auto", "nous"):
        return ""
    from vael_cli.anon_auth import GUEST_MODEL, free_tier_route
    return GUEST_MODEL if free_tier_route() else ""


def _banner_model_state(model: str, provider: Any, context_length, context_pinned: bool = False):
    """What the session will answer with, for either layout. ``context_pinned`` marks a
    ``model.context_length`` pin so the user can tell it apart from provider metadata (#66168)."""
    from vael_cli.banner_journal import ModelState
    pin = " (pinned)" if context_pinned else ""
    context = f"{_format_context_length(context_length)} context{pin}" if context_length else ""
    if not (model or "").strip():
        # Credentials resolve lazily on the first message; the banner prints first. Ask the route
        # the same question so a fresh free-tier install shows its model, not "not ready".
        model = _quiet(lambda: _route_model_for_banner(provider), "") or model
    if (provider or "").strip().lower() == "moa":
        # MoA virtual provider: ``model`` is a preset name; show it with its aggregator.
        return ModelState("moa", _short_label(model), _quiet(lambda: _moa_aggregator_label(model), ""), context)
    if not (model or "").strip() or (model or "").strip().lower() == "unknown":
        return ModelState("none")
    return ModelState("model", _short_label(model.split("/")[-1].removesuffix(".gguf")), "", context)


def _banner_left_lines(state, cwd: str, session_id, *, accent: str, dim: str) -> list:
    """Model / cwd / session lines under a skin's hero art."""
    def _dim_sep(label: str) -> str:
        return f" [dim {dim}]·[/] [dim {dim}]{label}[/]" if label else ""
    lines = []
    if state.kind == "moa":
        agg = f"agg {state.aggregator}" if state.aggregator else ""
        lines.append(f"[{accent}]MoA: {state.name}[/]{_dim_sep(agg)}{_dim_sep(state.context)}")
    elif state.kind == "none":
        # Unconfigured install: the clearest place to say what is wrong and how to fix it.
        lines.append(f"[bold red]no model configured[/] [dim {dim}]— run /model or vael setup[/]")
    else:
        lines.append(f"[{accent}]{state.name}[/]{_dim_sep(state.context)}")
    if os.getenv("VAEL_YOLO_MODE"):
        lines.append(f"[bold red]⚠ YOLO mode[/] [dim {dim}]— all approval prompts bypassed[/]")
    lines.append(f"[dim {dim}]{cwd}[/]")
    if session_id:
        lines.append(f"[dim {_skin_color('session_border', '#5E6B66')}]Session: {session_id}[/]")
    return lines


def _banner_tool_lines(
    toolsets_dict: Dict[str, list], *, lazy_tools: set, disabled_tools: set, accent: str, dim: str, text: str) -> list:
    """"Available Tools" section: up to 8 toolsets, each truncated to ~42 columns."""
    lines = [f"[bold {accent}]Available Tools[/]"]

    def _color_tool(name: Optional[str]) -> str:
        if name is None:  # truncation marker
            return "[dim]...[/]"
        color = "red" if name in disabled_tools else "yellow" if name in lazy_tools else text
        return f"[{color}]{name}[/]"
    sorted_toolsets = sorted(toolsets_dict.keys())
    for toolset in sorted_toolsets[:8]:
        tool_names = _truncate_tool_names(sorted(toolsets_dict[toolset]))
        lines.append(f"[dim {dim}]{toolset}:[/] {', '.join(_color_tool(n) for n in tool_names)}")
    if len(sorted_toolsets) > 8:
        lines.append(f"[dim {dim}](and {len(sorted_toolsets) - 8} more toolsets...)[/]")
    return lines


def _banner_skill_lines(skills_by_category: Dict[str, List[str]], skills_enabled: bool, *, dim: str, text: str) -> list:
    """"Available Skills" body, sized to ~60% of the terminal width (the right grid column)."""
    if not skills_enabled:
        return [f"[dim {dim}]Skills toolset disabled[/]"]
    if not skills_by_category:
        return [f"[dim {dim}]No skills installed[/]"]
    right_col_width = max(int(shutil.get_terminal_size().columns * 0.6) - 10, 30)
    lines = []
    for category in sorted(skills_by_category.keys()):
        # Account for the "category: " prefix.
        skills_str = _pack_skill_names(sorted(skills_by_category[category]), max(right_col_width - len(category) - 2, 20))
        lines.append(f"[dim {dim}]{category}:[/] [{text}]{skills_str}[/]")
    return lines


def _uses_hero_layout(skin) -> bool:
    """A skin that ships its own art keeps the framed hero panel; every other skin gets the journal."""
    return bool(getattr(skin, "banner_hero", None) or getattr(skin, "banner_logo", None))


def _toolsets_for_banner(tools: list, unavailable_toolsets: list, get_toolset_for_tool) -> Dict[str, list]:
    """``toolset -> tool names`` for the enabled tools plus the toolsets that could not load."""
    toolsets: Dict[str, list] = {}
    for tool in tools:
        tool_name = tool["function"]["name"]
        toolsets.setdefault(_display_toolset_name(get_toolset_for_tool(tool_name) or "other"), []).append(tool_name)
    for item in unavailable_toolsets:
        names = toolsets.setdefault(_display_toolset_name(item.get("id", item.get("name", "unknown"))), [])
        names.extend(n for n in item.get("tools", []) if n not in names)
    return toolsets


def build_welcome_banner(
    console: "Console", model: str, cwd: str, tools: List[dict] = None, enabled_toolsets: List[str] = None,
    session_id: str = None, get_toolset_for_tool=None, context_length: int = None, provider: str = None,
    availability: Dict[str, Any] = None, skills_by_category: Dict[str, List[str]] = None,
    context_pinned: bool = False,
):
    """Print the welcome page: the journal, or the framed hero panel for a skin that ships art.

    When ``provider == "moa"``, ``model`` is a MoA preset name and the aggregator is rendered.
    Passing a precomputed ``availability`` together with ``get_toolset_for_tool`` avoids any
    ``model_tools`` import (banner snapshot replay).
    """
    if get_toolset_for_tool is None:
        from model_tools import get_toolset_for_tool
    tools = tools or []
    enabled_toolsets = enabled_toolsets or []
    if availability is None:
        availability = compute_toolset_availability(enabled_toolsets)
    _enabled_ts = {str(t) for t in enabled_toolsets}
    _bskin = _quiet(_active_skin)
    state = _banner_model_state(model, provider, context_length, context_pinned)
    unavailable = availability.get("unavailable_toolsets", [])
    # MCP servers (only if configured) — see ``_mcp_configured`` for why the cheap probe.
    mcp_status = _quiet(_probe_mcp_status, []) if _mcp_configured() else []
    # The skills catalog is only reachable when the `skills` toolset is enabled (skill_view /
    # skill_manage). When disabled (Blank Slate) the agent cannot load any skill, so advertising
    # the on-disk catalog would be misleading — reflect the real state.
    _skills_enabled = (not _enabled_ts) or ("skills" in _enabled_ts)
    if not _skills_enabled:
        skills_by_category = {}
    elif skills_by_category is None:
        skills_by_category = get_available_skills()
    # Show active profile name when not 'default'. Never break the banner over a profiles.py bug.
    _profile_name = _quiet(_active_profile_name)
    profile = _profile_name if _profile_name and _profile_name != "default" else None
    # Flag the codex_app_server runtime so users understand why tool counts may not match what's
    # reachable (codex builds its own tool list inside the spawned subprocess).
    codex_runtime = bool(_quiet(_codex_runtime_active, False))
    # Update check — NEVER block the banner on it: the prefetch does git/network work that rarely
    # finishes before render, so a blocking wait adds its full timeout to every startup. If not
    # ready, a daemon thread prints the same notice above the prompt when it lands.
    def _update_behind():
        behind = get_update_result(timeout=0.05)
        if behind is None and not _update_check_done.is_set():
            _defer_update_notice()
        return behind or None
    behind = _quiet(_update_behind)  # Never break the banner over an update check
    release_info = get_latest_release_tag()
    if _uses_hero_layout(_bskin):
        _print_hero_banner(
            console, _bskin, state, cwd, session_id, tools=tools,
            toolsets=_toolsets_for_banner(tools, unavailable, get_toolset_for_tool), availability=availability,
            mcp_status=mcp_status, skills_by_category=skills_by_category, skills_enabled=_skills_enabled,
            profile=profile, codex_runtime=codex_runtime, behind=behind, release_info=release_info)
        return
    from vael_cli import banner_journal
    agent_name = getattr(_bskin, "get_branding", lambda _key, fallback: fallback)("agent_name", "VAEL Agent")
    version, _, build = format_banner_version_label().removeprefix("VAEL Agent ").partition(" · ")
    # An enabled toolset that did not load is named and flagged, and adds nothing to the counts;
    # the availability notices printed after the page say why.
    not_loaded = {_display_toolset_name(item.get("id", item.get("name", "unknown"))) for item in unavailable}
    update_text, update_command = _update_notice_parts(behind) if behind else ("", "")
    banner_journal.render(console, banner_journal.Welcome(
        agent_name=agent_name, version=version, build=build,
        release_url=release_info[1] if release_info else None, cwd=cwd, session_id=session_id,
        profile=profile, model=state, yolo=bool(os.getenv("VAEL_YOLO_MODE")),
        toolsets=_toolsets_for_banner(tools, [], get_toolset_for_tool), not_loaded=not_loaded,
        tool_count=len(tools), codex_runtime=codex_runtime,
        skills=skills_by_category, skills_enabled=_skills_enabled, mcp=mcp_status,
        terminal_backend=(os.getenv("TERMINAL_ENV") or "local").strip().lower(),
        update_text=update_text, update_command=update_command))


def _print_hero_banner(
    console: "Console", skin, state, cwd: str, session_id, *, tools: list, toolsets: Dict[str, list],
    availability: Dict[str, Any], mcp_status: list, skills_by_category: Dict[str, List[str]],
    skills_enabled: bool, profile: Optional[str], codex_runtime: bool, behind: Optional[int], release_info,
) -> None:
    """The framed panel for a skin that ships art: hero on the left, inventory on the right."""
    from rich.panel import Panel
    from rich.table import Table
    # Resolve skin colors once for the entire banner
    accent = _skin_color("banner_accent", "#18AA7F")
    dim = _skin_color("banner_dim", "#7C8B85")
    text = _skin_color("banner_text", "#D3DCD7")
    hero = getattr(skin, "banner_hero", None)
    left_lines = (["", hero, ""] if hero else []) + _banner_left_lines(
        state, cwd, session_id, accent=accent, dim=dim)
    right_lines = _banner_tool_lines(
        toolsets, lazy_tools=set(availability.get("lazy_tools", [])),
        disabled_tools=set(availability.get("disabled_tools", [])), accent=accent, dim=dim, text=text)
    if mcp_status:
        right_lines += ["", f"[bold {accent}]MCP Servers[/]"]
        right_lines.extend(_mcp_server_line(srv, dim=dim, text=text) for srv in mcp_status)
    right_lines += ["", f"[bold {accent}]Available Skills[/]"]
    total_skills = sum(len(s) for s in skills_by_category.values())
    right_lines += _banner_skill_lines(skills_by_category, skills_enabled, dim=dim, text=text)
    right_lines.append("")
    mcp_connected = sum(1 for s in mcp_status if s["connected"])
    summary_parts = [f"{len(tools)} tools", f"{total_skills} skills"]
    if mcp_connected:
        summary_parts.append(f"{mcp_connected} MCP servers")
    summary_parts.append("/help for commands")
    if codex_runtime:
        right_lines.append(f"[bold {accent}]Runtime:[/] [{text}]codex app-server[/] "
                           f"[dim {dim}](terminal/file ops/MCP run inside codex)[/]")
    if profile:
        right_lines.append(f"[bold {accent}]Profile:[/] [{text}]{profile}[/]")
    right_lines.append(f"[dim {dim}]{' · '.join(summary_parts)}[/]")
    if behind:
        right_lines.append(_format_update_notice(behind))
    layout_table = Table.grid(padding=(0, 2))
    layout_table.add_column("left", justify="left")
    layout_table.add_column("right", justify="left")
    layout_table.add_row("\n".join(left_lines), "\n".join(right_lines))
    version_label = format_banner_version_label()
    if release_info:
        version_label = f"[link={release_info[1]}]{version_label}[/link]"
    outer_panel = Panel(
        layout_table, title=f"[bold {_skin_color('banner_title', '#F2F6F4')}]{version_label}[/]",
        border_style=_skin_color("banner_border", "#2E6F5B"), padding=(0, 2))
    console.print()
    logo = getattr(skin, "banner_logo", None)
    if logo and shutil.get_terminal_size().columns >= 95:
        console.print(logo)
        console.print()
    console.print(outer_panel)
