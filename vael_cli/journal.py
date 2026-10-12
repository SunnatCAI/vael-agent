"""Journal layout — the console's one page.

Every row hangs off a fixed left margin that carries its time and state, then a label column, the
value, and a right-aligned figure or next command. The welcome screen and the startup notices build
their rows here, so their columns cannot drift apart.

The margin is painted with the status bar's field colour and reads only the colours a skin already
pairs with that field, so any skin (and its light palette) gets a legible margin without new keys.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Union

if TYPE_CHECKING:
    from rich.console import Console
    from rich.text import Text

GUTTER = 9       # pad · HH:MM · space · state glyph · pad
LABEL = 11
MAX_WIDTH = 100  # rows stop here on wide terminals, so a right-aligned hint stays beside its row

# state -> (glyph, ASCII stand-in, role on the margin field). A state is never colour alone.
_STATES = {
    "blocked": ("●", "*", "warn"),
    "running": ("▸", ">", "good"),
    "done": ("✓", "+", "good"),
    "ask": ("?", "?", "warn"),
    "notice": ("!", "!", "warn"),
    "failed": ("✗", "x", "bad"),
}

Content = Union[str, "Text", None]


@dataclass(frozen=True)
class Palette:
    """Journal colours resolved from the active skin."""
    accent: str
    warn: str
    error: str
    text: str
    dim: str
    strong: str
    field: str        # margin fill
    field_dim: str    # the time, on the field
    field_good: str
    field_warn: str
    field_bad: str
    mark_bg: str
    mark_fg: str


def palette() -> Palette:
    from vael_cli.skin_engine import get_active_skin
    color = get_active_skin().get_color
    return Palette(
        accent=color("banner_accent", "#18AA7F"), warn=color("ui_warn", "#E0A83C"),
        error=color("ui_error", "#EF6B5E"), text=color("banner_text", "#D3DCD7"),
        dim=color("banner_dim", "#7C8B85"), strong=color("banner_title", "#F2F6F4"),
        field=color("status_bar_bg", "#12211C"), field_dim=color("status_bar_dim", "#8A9A93"),
        field_good=color("status_bar_good", "#18AA7F"), field_warn=color("status_bar_warn", "#E0A83C"),
        field_bad=color("status_bar_critical", "#F0786C"),
        mark_bg=color("status_bar_strong", "#18AA7F"), mark_fg=color("status_bar_bg", "#12211C"))


class Journal:
    """Builds journal rows for one console at its current width."""

    def __init__(self, console: "Console", *, clock: Optional[str] = None):
        self.console = console
        self.width = min(console.width, MAX_WIDTH)
        self.pal = palette()
        self.ascii = bool(console.options.ascii_only)
        self.clock = clock if clock is not None else time.strftime("%H:%M")

    # ── pieces ────────────────────────────────────────────────────────────────

    def text(self, content: Content, style: str = "") -> "Text":
        """``content`` as Rich ``Text``: a ``str`` is plain (never parsed as markup). The style is a
        span, not the ``Text``'s base style, so nothing appended later inherits it."""
        from rich.text import Text
        if isinstance(content, Text):
            return content.copy()
        return Text.assemble((content or "", style))

    def cmd(self, command: str, note: str = "") -> "Text":
        """A command the reader can run, optionally followed by a dim note."""
        out = self.text(command, self.pal.accent)
        if note:
            out.append(f"  {note}", style=self.pal.dim)
        return out

    def dim(self, content: str) -> "Text":
        return self.text(content, self.pal.dim)

    def strong(self, content: str) -> "Text":
        return self.text(content, f"bold {self.pal.strong}")

    def _margin(self, state: str, stamp: bool, mark: str) -> "Text":
        from rich.text import Text
        pal = self.pal
        field = f"on {pal.field}"
        if mark:
            out = Text.assemble((" ", field))
            out.append(f" {mark} ", style=f"bold {pal.mark_fg} on {pal.mark_bg}")
            out.append(" " * max(0, GUTTER - out.cell_len), style=field)
            return out
        glyph, fallback, role = _STATES.get(state, (" ", " ", "dim"))
        tone = getattr(pal, f"field_{role}")
        out = Text.assemble((" ", field))
        out.append(self.clock if stamp else " " * 5, style=f"{tone if state else pal.field_dim} on {pal.field}")
        out.append(" ", style=field)
        out.append(fallback if self.ascii else glyph, style=f"bold {tone} on {pal.field}")
        out.append(" ", style=field)
        return out

    # ── rows ──────────────────────────────────────────────────────────────────

    def rows(self, label: str = "", value: Content = None, hint: Content = None, *, state: str = "",
             stamp: bool = False, mark: str = "", label_style: Optional[str] = None) -> List["Text"]:
        """One logical row. A value too long for the line continues on further rows under the
        value column; the hint stays on the first."""
        from rich.text import Text
        pal = self.pal
        body = self.text(value, pal.text)
        tail = self.text(hint, pal.dim)
        if state in ("blocked", "ask", "notice") and label_style is None:
            label_style = f"bold {pal.warn}"
        elif state == "failed" and label_style is None:
            label_style = f"bold {pal.error}"
        head = self.text(label, label_style or pal.dim)
        label_cells = max(LABEL, head.cell_len + 1) if label else LABEL
        room = self.width - GUTTER - 2 - label_cells - 1
        first_room = room - (tail.cell_len + 2 if tail.cell_len else 0)
        if body.cell_len <= first_room or first_room < 12:
            pieces = [body]
        else:
            pieces = self._continue(body, first_room, room)
        out: List[Text] = []
        for i, piece in enumerate(pieces):
            piece.rstrip()
            line = self._margin(state if i == 0 else "", stamp and i == 0, mark if i == 0 else "")
            line.append("  ")
            line.append_text(head if i == 0 else Text(""))
            line.append(" " * (label_cells - (head.cell_len if i == 0 else 0)))
            line.append_text(piece)
            if i == 0 and tail.cell_len:
                line.append(" " * max(2, self.width - 1 - line.cell_len - tail.cell_len))
                line.append_text(tail)
            out.append(line)
        return out

    def _continue(self, body: "Text", first_room: int, room: int) -> List["Text"]:
        """Split ``body`` over rows: ``first_room`` cells on the first, ``room`` on the rest. A value
        with no space to break at (a path) is cut after a separator rather than mid-name."""
        pieces: List["Text"] = []
        rest, limit = body, first_room
        while rest.cell_len > limit:
            first = rest.wrap(self.console, limit)[0]
            cut = len(first.plain)
            if cut < len(rest.plain) and rest.plain[cut] != " " and " " not in first.plain:
                at = max(first.plain.rfind("\\"), first.plain.rfind("/"))
                if at >= limit // 2:
                    cut = at + 1
            pieces.append(rest[:cut])
            while cut < len(rest.plain) and rest.plain[cut] == " ":
                cut += 1
            rest, limit = rest[cut:], room
        return [*pieces, rest]

    def blank(self) -> "Text":
        return self._margin("", False, "")

    def tool_rows(self, parts: List[tuple], duration: float) -> List["Text"]:
        """A finished tool call: one stamped row per ``(verb, detail, failure)``, the failure
        reason and the duration at the right edge of the last one."""
        from rich.text import Text
        pal = self.pal
        out: List[Text] = []
        for i, (verb, detail, failure) in enumerate(parts):
            tail = Text()
            if failure:
                tail.append(failure, style=pal.error)
            if i == len(parts) - 1:
                tail.append(f"{'  ' if failure else ''}{duration:.1f}s", style=pal.dim)
            out.extend(self.rows(verb, detail, tail if tail.plain else None, state="failed" if failure else "done",
                                 stamp=i == 0, label_style=None if failure else pal.text))
        return out

    def section(self, title: str, summary: Content = None, hint: Content = None) -> List["Text"]:
        """A section heading: bold capitals in the label column."""
        return self.rows(title.upper(), summary, hint, label_style=f"bold {self.pal.strong}")

    def columns(self, cells: List["Text"], *, gap: int = 2, limit: int = 3) -> List["Text"]:
        """Lay equal-width cells out across the value column, ``limit`` to a row at most."""
        from rich.text import Text
        if not cells:
            return []
        cell_width = max(c.cell_len for c in cells) + gap
        room = self.width - GUTTER - 2 - LABEL - 1
        per_row = max(1, min(limit, (room + gap) // cell_width))
        out: List[Text] = []
        for start in range(0, len(cells), per_row):
            line = Text()
            for cell in cells[start:start + per_row]:
                line.append_text(cell)
                line.append(" " * (cell_width - cell.cell_len))
            line.rstrip()
            out.extend(self.rows("", line))
        return out

    def print(self, *lines: "Text") -> None:
        for line in lines:
            self.console.print(line, no_wrap=True, overflow="ignore", crop=False, highlight=False)


def render_ansi(build, *, width: Optional[int] = None) -> List[str]:
    """The rows ``build(journal)`` returns as ANSI strings, one per row — for output that must go
    through prompt_toolkit's renderer once the prompt owns the terminal (the same reason as
    ``banner._render_markup_to_ansi``)."""
    import shutil
    from io import StringIO
    from rich.console import Console as _Console
    buf = StringIO()
    console = _Console(file=buf, force_terminal=True, color_system="truecolor", highlight=False,
                       width=width or shutil.get_terminal_size().columns)
    journal = Journal(console)
    journal.print(*build(journal))
    return buf.getvalue().rstrip("\n").split("\n")


def notice_ansi(label: str, value: str, hint: str = "", *, state: str = "notice", width: Optional[int] = None) -> str:
    """One stamped journal row as an ANSI string."""
    return "\n".join(render_ansi(
        lambda j: j.rows(label, value, j.cmd(hint) if hint else None, state=state, stamp=True), width=width))
