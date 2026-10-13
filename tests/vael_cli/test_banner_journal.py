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


@pytest.mark.parametrize("width", [60, 80, 100, 160])
def test_the_page_fits_its_width_and_loses_nothing(width):
    """No row runs past the page (capped on a wide terminal), the rows under the head share the
    margin, and a path too long for one row continues on the next, whole."""
    skills = {"research": [f"s{i}" for i in range(15)], "software-development": ["a", "b"]}
    cwd = "/srv/" + "/".join(f"level-{i:02d}" for i in range(14))
    text = _render(width, skills_by_category=skills, session_id="20261012_222734_8dd6f4", cwd=cwd)
    rows = [line for line in text.splitlines() if line.strip()]
    for row in rows:
        assert cell_len(row.rstrip()) <= min(width, MAX_WIDTH), row
    body = rows[next(i for i, row in enumerate(rows) if "TOOLS" in row):]
    assert all(row[GUTTER:GUTTER + 2] == "  " for row in body)
    assert cwd in "".join(text.split())


def test_the_wordmark_gives_way_to_the_name_on_a_narrow_terminal():
    """The mark and wordmark need room; without it the name still leads the page."""
    wide, narrow = _render(100), _render(60)
    assert "███████╗" in wide
    assert "█" not in narrow and narrow.lstrip().startswith("VAEL")


def test_counts_are_whole_numbers_of_what_loaded_and_nothing_is_elided():
    """The page states totals rather than cut lists; a toolset that did not load is named and
    adds nothing to the tool count."""
    toolset_of = {"read_file": "file", "terminal": "terminal", "web_search": "web"}.get
    availability = {
        "unavailable_toolsets": [{"name": "homeassistant", "tools": ["ha_call", "ha_list"]}],
        "lazy_tools": [], "disabled_tools": ["ha_call", "ha_list"]}
    skills = {"research": [f"skill-{i:02d}" for i in range(15)], "security": ["auth", "vault"]}
    text = _render(tools=[_tool(n) for n in ("read_file", "terminal", "web_search")],
                   toolset_of=toolset_of, availability=availability, skills_by_category=skills)
    assert re.search(r"TOOLS\s+3 in 2 groups", text)
    assert re.search(r"SKILLS\s+17 in 2 groups", text)
    assert "not loaded: homeassistant" in text
    assert "more" not in text and "..." not in text
