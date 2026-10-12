"""The journal welcome page: one margin for every row, counts that agree, nothing elided."""

import re
from unittest.mock import patch

import pytest
from rich.cells import cell_len
from rich.console import Console

import model_tools
import tools.mcp_tool_discovery
import vael_cli.banner as banner
from vael_cli.journal import GUTTER, MAX_WIDTH


def _tool(name: str) -> dict:
    return {"function": {"name": name}}


def _render(width: int = 100, **kwargs) -> str:
    kwargs.setdefault("skills_by_category", {})
    kwargs.setdefault("availability", {"unavailable_toolsets": [], "lazy_tools": [], "disabled_tools": []})
    with (
        patch.object(model_tools, "check_tool_availability", return_value=([], [])),
        patch.object(banner, "get_update_result", return_value=None),
        patch.object(banner, "get_latest_release_tag", return_value=None),
        patch.object(tools.mcp_tool_discovery, "get_mcp_status", return_value=[]),
    ):
        console = Console(record=True, force_terminal=False, color_system=None, width=width)
        banner.build_welcome_banner(
            console=console, model="anthropic/test-model", cwd=kwargs.pop("cwd", "/tmp/project"),
            tools=kwargs.pop("tools", []),
            get_toolset_for_tool=kwargs.pop("toolset_of", lambda _name: None), **kwargs)
    return console.export_text()


@pytest.mark.parametrize("width", [80, 100, 160])
def test_every_row_hangs_off_one_margin_and_stays_on_the_page(width):
    """Rows share the margin and the label column, and stop at the page width even on a wide
    terminal — a row that drifts or runs on is the layout breaking. A value too long for its row
    continues on the next one, whole."""
    skills = {"research": [f"s{i}" for i in range(15)], "software-development": ["a", "b"]}
    cwd = "/srv/" + "/".join(f"level-{i:02d}" for i in range(14))
    text = _render(width, skills_by_category=skills, session_id="20261012_222734_8dd6f4", cwd=cwd)
    rows = [line for line in text.splitlines() if line.strip()]
    assert rows
    for row in rows:
        assert cell_len(row.rstrip()) <= min(width, MAX_WIDTH), row
        assert row[GUTTER:GUTTER + 2] == "  ", row
    where = text.split("where", 1)[1].split("session", 1)[0]
    assert "".join(where.split()) == cwd


def test_skill_groups_carry_their_counts_and_nothing_is_elided():
    """A group is shown whole or not at all: its name and its count, never a cut list."""
    skills = {"research": [f"skill-{i:02d}" for i in range(15)], "security": ["auth", "vault"]}
    text = _render(80, skills_by_category=skills)
    assert re.search(r"\b15\s+research\b", text)
    assert re.search(r"\b2\s+security\b", text)
    assert "17 in 2 groups" in text
    assert "more" not in text and "..." not in text


def test_group_counts_add_up_to_the_tool_total_and_name_what_did_not_load():
    """The headline count and the per-group counts describe the same loaded tools; a toolset that
    could not load is named and flagged, and adds to neither."""
    toolset_of = {"read_file": "file", "terminal": "terminal", "web_search": "web"}.get
    availability = {
        "unavailable_toolsets": [{"name": "homeassistant", "tools": ["ha_call", "ha_list"]}],
        "lazy_tools": [], "disabled_tools": ["ha_call", "ha_list"]}
    text = _render(tools=[_tool(n) for n in ("read_file", "terminal", "web_search")],
                   toolset_of=toolset_of, availability=availability)
    headline = int(re.search(r"TOOLS\s+(\d+) in", text).group(1))
    section = text.split("TOOLS", 1)[1].split("SKILLS", 1)[0].splitlines()[1:]
    counts = [int(m.group(1)) for line in section if (m := re.search(r"\s(\d+)\s*$", line))]
    assert headline == sum(counts) == 3
    assert "homeassistant*" in text and "not loaded" in text
