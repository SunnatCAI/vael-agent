"""The journal's activity rows and overlay panels: the same facts as the framed layout, on the margin."""

import json
import re

import pytest
from rich.cells import cell_len
from rich.console import Console

from agent.display import get_cute_tool_message, tool_completion_parts
from vael_cli import skin_engine
from vael_cli.cli_tui_mixin import _modal_panel
from vael_cli.journal import GUTTER, Journal

_FRAME = set("╭╮╰╯│─")


@pytest.fixture(autouse=True)
def _default_skin():
    skin_engine._active_skin, skin_engine._active_skin_name = None, "default"
    yield
    skin_engine._active_skin, skin_engine._active_skin_name = None, "default"


def _rows(tool: str, args: dict, result=None, duration: float = 0.2) -> list[str]:
    console = Console(record=True, force_terminal=False, color_system=None, width=100)
    journal = Journal(console, clock="10:00")
    journal.print(*journal.tool_rows(tool_completion_parts(tool, args, result), duration))
    return console.export_text().splitlines()


def test_a_finished_call_is_one_stamped_row_carrying_what_the_feed_line_carries():
    """Both layouts print the same verb and detail for a call; the journal puts them on the margin
    with the duration at the right edge, and no pictogram."""
    args = {"path": "logs/errors.log"}
    ((verb, detail, failure),) = tool_completion_parts("read_file", args)
    feed = get_cute_tool_message("read_file", args, 0.2)
    assert verb in feed and detail in feed and failure == ""

    (row,) = _rows("read_file", args)
    assert row.startswith(" 10:00 ✓ ") and row[GUTTER:GUTTER + 2] == "  "
    assert re.search(rf"{re.escape(verb)}\s+{re.escape(detail)}\s+0\.2s$", row.rstrip())
    assert all(ord(ch) < 0x1F000 for ch in row), "no emoji pictograms on a journal row"


def test_a_failed_call_says_so_in_words_beside_its_duration():
    """Failure is a glyph and a reason, never colour alone."""
    (row,) = _rows("terminal", {"command": "npm run typecheck"}, json.dumps({"exit_code": 2, "output": ""}), 11.8)
    assert row.startswith(" 10:00 ✗ ")
    assert re.search(r"exit 2\s+11\.8s$", row.rstrip())


def test_an_overlay_panel_follows_the_layout_of_the_active_skin():
    """Under the journal a question hangs off the margin with no frame, its first row stamped and
    marked as waiting on the reader; a skin that ships art keeps the framed panel."""
    def text_of(panel) -> str:
        panel.row("class:approval-title", "⚠️  Dangerous Command")
        panel.blank()
        panel.row("class:approval-cmd", "rm -rf build")
        return "".join(text for _style, text in panel.close())

    journal = text_of(_modal_panel("class:approval-border", 46))
    lines = journal.splitlines()
    assert not _FRAME & set(journal)
    # First row stamped and marked "waiting on you"; every row carries the bar in the ninth cell,
    # and the band behind them is one width, so the question reads as one block.
    assert re.match(r" \d\d:\d\d \?▌ Dangerous Command\s+$", lines[0])
    assert all(line[GUTTER - 1] == "▌" for line in lines), lines
    assert len({cell_len(line) for line in lines}) == 1, lines
    assert lines[-1].startswith(" " * (GUTTER - 1) + "▌ rm -rf build")

    skin_engine.set_active_skin("ares")
    framed = text_of(_modal_panel("class:approval-border", 46))
    assert framed.startswith("╭") and "⚠️  Dangerous Command" in framed
