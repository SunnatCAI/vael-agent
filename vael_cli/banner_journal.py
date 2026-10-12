"""The welcome page in journal form: what blocks the reader first, then where they are, what the
agent can use, and what it is linked to. ``banner.build_welcome_banner`` gathers the facts; this
module only lays them out, so it never touches the tool registry or the network."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Set

from vael_cli.journal import Journal

if TYPE_CHECKING:
    from rich.console import Console
    from rich.text import Text

# Toolsets by what they are for, in reading order. One not named here gets the "other" row.
_TOOL_GROUPS = (
    ("workspace", ("file", "terminal", "code_execution", "debugging", "project")),
    ("web", ("web", "search", "browser", "browser-use", "x_search")),
    ("computer", ("computer_use", "vision", "video", "desktop_ui")),
    ("media", ("image_gen", "video_gen", "tts")),
    ("memory", ("memory", "session_search", "todo", "skills", "context_engine")),
    ("people", ("clarify", "delegation", "connections", "cronjob", "kanban", "bot_room")),
)
_GROUP_OF = {toolset: group for group, members in _TOOL_GROUPS for toolset in members}
_OTHER = "other"

# Terminal backends that keep commands off this machine's own shell.
_LOCAL_BACKEND = "local"


@dataclass
class ModelState:
    """What the session will answer with. ``kind``: ``none`` | ``model`` | ``moa``."""
    kind: str = "none"
    name: str = ""
    aggregator: str = ""
    context: str = ""


@dataclass
class Welcome:
    """Every fact the welcome page prints."""
    agent_name: str = "VAEL Agent"
    version: str = ""
    build: str = ""
    release_url: Optional[str] = None
    cwd: str = ""
    session_id: Optional[str] = None
    profile: Optional[str] = None
    model: ModelState = field(default_factory=ModelState)
    yolo: bool = False
    toolsets: Dict[str, List[str]] = field(default_factory=dict)   # loaded toolset -> its tools
    not_loaded: Set[str] = field(default_factory=set)              # enabled toolsets that did not load
    tool_count: int = 0
    codex_runtime: bool = False
    skills: Dict[str, List[str]] = field(default_factory=dict)
    skills_enabled: bool = True
    mcp: List[dict] = field(default_factory=list)
    terminal_backend: str = _LOCAL_BACKEND
    update_text: str = ""
    update_command: str = ""


def _plural(n: int, word: str) -> str:
    return word if n == 1 else f"{word}s"


def _split_name(agent_name: str) -> tuple:
    """``("VAEL", "Agent")``: the first word goes on the margin's field when it fits there."""
    first, _, rest = agent_name.strip().partition(" ")
    return (first, rest) if 0 < len(first) <= 6 else ("", agent_name.strip())


def _state_rows(j: Journal, w: Welcome) -> List["Text"]:
    from rich.text import Text
    pal = j.pal
    if w.model.kind == "none":
        rows = j.rows("NOT READY", "No model is configured, so VAEL cannot answer yet.",
                      state="blocked", stamp=True)
        rows += j.rows("next", j.cmd("/model", "choose a provider and model"), j.cmd("vael setup", "guided start"))
    else:
        value = Text()
        if w.model.kind == "moa":
            value.append("MoA ", style=pal.dim)
        value.append(w.model.name, style=f"bold {pal.strong}")
        for part in (f"agg {w.model.aggregator}" if w.model.aggregator else "", w.model.context):
            if part:
                value.append(f" · {part}", style=pal.dim)
        rows = j.rows("READY", value, state="done", stamp=True, label_style=f"bold {pal.accent}")
    if w.yolo:
        rows += j.rows("YOLO", "Every approval prompt is bypassed in this session.", state="notice")
    return rows


def _place_rows(j: Journal, w: Welcome) -> List["Text"]:
    rows = j.rows("where", w.cwd)
    if w.session_id:
        rows += j.rows("session", w.session_id)
    if w.profile:
        rows += j.rows("profile", w.profile)
    if w.build:
        rows += j.rows("build", j.dim(w.build))
    return rows


def _tool_rows(j: Journal, w: Welcome) -> List["Text"]:
    from rich.text import Text
    pal = j.pal
    grouped: Dict[str, List[str]] = {}
    for toolset in sorted(set(w.toolsets) | w.not_loaded):
        grouped.setdefault(_GROUP_OF.get(toolset, _OTHER), []).append(toolset)
    order = [g for g, _ in _TOOL_GROUPS if g in grouped] + ([_OTHER] if _OTHER in grouped else [])
    summary = j.strong(str(w.tool_count))
    summary.append(f" in {len(order)} {_plural(len(order), 'group')}", style=pal.dim)
    rows = j.section("Tools", summary, j.cmd("/tools"))
    for group in order:
        value = Text()
        for toolset in grouped[group]:
            # Tools that belong to no toolset have no shorter name than their own.
            loose = toolset == _OTHER and toolset in w.toolsets
            flagged = toolset not in w.toolsets
            for name in (sorted(w.toolsets[toolset]) if loose else [toolset]):
                if value.plain:
                    value.append(" · ", style=pal.dim)
                value.append(f"{name}*" if flagged else name, style=pal.warn if flagged else pal.text)
        count = sum(len(w.toolsets.get(t, ())) for t in grouped[group])
        rows += j.rows(group, value, j.dim(str(count)) if count else None)
    if w.not_loaded - set(w.toolsets):
        rows += j.rows("", j.dim("* not loaded in this session"), j.cmd("vael tools"))
    if w.codex_runtime:
        rows += j.rows("runtime", "codex app-server — terminal, file operations and MCP run inside codex")
    return rows


def _skill_rows(j: Journal, w: Welcome) -> List["Text"]:
    from rich.text import Text
    pal = j.pal
    if not w.skills_enabled:
        return j.section("Skills", j.dim("the skills toolset is disabled"), j.cmd("/tools"))
    if not w.skills:
        return j.section("Skills", j.dim("none installed"), j.cmd("/skills"))
    total = sum(len(names) for names in w.skills.values())
    summary = j.strong(str(total))
    summary.append(f" in {len(w.skills)} {_plural(len(w.skills), 'group')}", style=pal.dim)
    width = len(str(max(len(names) for names in w.skills.values())))
    cells = []
    for category in sorted(w.skills, key=lambda c: (-len(w.skills[c]), c)):
        cell = j.text(f"{len(w.skills[category]):>{width}}", pal.accent)
        cell.append(f"  {category}", style=pal.text)
        cells.append(cell)
    return j.section("Skills", summary, j.cmd("/skills")) + j.columns(cells)


def _mcp_row(j: Journal, srv: dict) -> List["Text"]:
    from rich.text import Text
    pal = j.pal
    name, transport = srv["name"], srv["transport"]
    tools = f"{srv.get('tools', 0)} {_plural(int(srv.get('tools') or 0), 'tool')}"
    value = j.dim(f"MCP {transport}")
    status = "disabled" if srv.get("disabled") else srv.get("status")
    if srv["connected"]:
        value.append(f" · {tools}", style=pal.text)
    elif status == "lazy":
        value.append(f" · {tools}", style=pal.text)
        value.append(" · starts on first use", style=pal.dim)
    elif status in ("disabled", "connecting", "configured"):
        value.append(f" · {status}", style=pal.dim)
    else:
        import re
        reason = " ".join(str(srv.get("error") or "").split())[:120] or "no details recorded"
        login = re.search(r"\b401\b|unauthori[sz]ed", reason, re.I)
        value.append(f" · could not connect: {reason}", style=pal.error)
        return j.rows(name, value, j.cmd(f"vael mcp {'login' if login else 'test'} {name}"), state="failed")
    return j.rows(name, value)


def _link_rows(j: Journal, w: Welcome) -> List["Text"]:
    from rich.text import Text
    pal = j.pal
    rows = j.section("Links")
    sandbox = Text()
    if w.terminal_backend == _LOCAL_BACKEND:
        sandbox.append("none", style=pal.text)
        sandbox.append(" · commands run on this machine", style=pal.dim)
    else:
        sandbox.append(w.terminal_backend, style=pal.text)
        sandbox.append(" · commands run inside it", style=pal.dim)
    rows += j.rows("sandbox", sandbox, j.cmd("vael setup terminal"))
    for srv in w.mcp:
        rows += _mcp_row(j, srv)
    return rows


def render(console: "Console", w: Welcome) -> None:
    """Print the welcome page."""
    from rich.text import Text
    j = Journal(console)
    pal = j.pal
    mark, rest = _split_name(w.agent_name)
    version = j.dim(w.version)
    if w.release_url:
        version.stylize(f"link {w.release_url}")
    lines = j.rows(rest, version, mark=mark, label_style=f"bold {pal.strong}")
    lines.append(j.blank())
    lines += _state_rows(j, w)
    lines.append(j.blank())
    lines += _place_rows(j, w)
    lines.append(j.blank())
    lines += _tool_rows(j, w)
    lines.append(j.blank())
    lines += _skill_rows(j, w)
    lines.append(j.blank())
    lines += _link_rows(j, w)
    if w.update_text:
        lines.append(j.blank())
        lines += j.rows("update", w.update_text, j.cmd(w.update_command) if w.update_command else None,
                        state="notice", stamp=True)
    console.print()
    j.print(*lines)
