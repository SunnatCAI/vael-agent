"""The journal's message block: a reply is a bar in the margin and a tinted band, not a framed box.

The framed box (header rule, footer rule, flush-left lines) stays for the hero skins; those contracts
live in test_stream_flush_left.py and test_status_lines_held_during_stream_box.py.
"""
import os
import re
import sys
from types import SimpleNamespace

import pytest
from rich.cells import cell_len

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _plain(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


@pytest.fixture
def cli_stub(monkeypatch):
    from cli import VaelCLI
    import cli as climod
    from vael_cli import skin_engine
    from vael_cli.banner import uses_journal_layout

    previous = skin_engine.get_active_skin_name()
    skin_engine.set_active_skin("default")
    assert uses_journal_layout(), "the default skin must get the journal"

    cli = VaelCLI.__new__(VaelCLI)
    cli.show_reasoning = False
    cli.final_response_markdown = "raw"
    cli.show_timestamps = False
    cli._reset_stream_state()
    emitted = []
    monkeypatch.setattr(climod, "_cprint", lambda s: emitted.append(s))
    monkeypatch.setattr(climod, "_terminal_width_for_streaming", lambda: 74)
    monkeypatch.setattr(VaelCLI, "_scrollback_box_width", lambda self: 74)
    yield cli, emitted
    skin_engine.set_active_skin(previous)


def _rows(emitted):
    return [row for e in emitted for row in _plain(e).split("\n")]


def test_streamed_reply_is_a_bar_and_band_without_frame_rules(cli_stub):
    cli, emitted = cli_stub
    cli._stream_delta("First streamed line.\nSecond streamed line.\n")
    cli._flush_stream()
    rows = _rows(emitted)
    content = [r for r in rows if "streamed line" in r]
    assert len(content) == 2
    assert all("▌" in r[:12] for r in content), content
    assert not any(set(r) & set("╭╮╰╯") for r in rows), rows


def test_every_row_of_a_block_spans_the_same_width(cli_stub):
    """The band is one unit down the page: short, long (wrapped) and blank lines alike."""
    cli, emitted = cli_stub
    cli._stream_delta("Short.\n\n" + "word " * 60 + "\n")
    cli._flush_stream()
    widths = {cell_len(r) for r in _rows(emitted) if "▌" in r}
    assert len(widths) == 1, widths


def test_long_reply_line_wraps_inside_the_band(cli_stub):
    cli, emitted = cli_stub
    cli._stream_delta("word " * 80 + "\n")
    cli._flush_stream()
    rows = [r for r in _rows(emitted) if "word" in r]
    assert len(rows) > 1
    assert all("▌" in r for r in rows)
    assert sum(r.count("word") for r in rows) == 80


def test_status_line_waits_until_the_block_is_done(cli_stub):
    """No footer to anchor on, but a held status line still lands after the whole reply."""
    cli, emitted = cli_stub
    cli._stream_delta("First paragraph.\n")
    cli._agent_status_print("  ✓ [set 7 · 2/2] worker  (2175.14s)")
    cli._stream_delta("Second paragraph.\n")
    cli._flush_stream()
    lines = _rows(emitted)
    second = next(i for i, l in enumerate(lines) if "Second paragraph" in l)
    notice = next(i for i, l in enumerate(lines) if "set 7" in l)
    assert second < notice, lines


def test_final_reply_is_one_block_not_a_panel(cli_stub, monkeypatch):
    from rich.panel import Panel
    import cli as climod

    cli, _ = cli_stub
    printed = []
    monkeypatch.setattr(climod, "ChatConsole", lambda: SimpleNamespace(print=printed.append))
    cli._streamed_text_this_turn = ""
    cli._last_turn_interrupted = False
    turn = SimpleNamespace(use_streaming_tts=False, box_opened=False,
                           result={"completed": True, "final_response": "Hello there"})
    cli._chat_print_response_panel(turn, "Hello there")
    assert len(printed) == 1
    assert not isinstance(printed[0], Panel)


def test_block_rows_stay_ascii_safe_without_unicode():
    from io import StringIO
    from rich.console import Console
    from vael_cli.journal import Journal

    journal = Journal(Console(width=60, file=StringIO()))
    journal.ascii = True
    rows = journal.block("plain reply", "assistant")
    assert all("▌" not in r.plain and "|" in r.plain for r in rows)


def test_user_message_is_a_block_with_the_time_at_the_right_edge(cli_stub):
    cli, _ = cli_stub
    cli.show_timestamps = True
    cli.timestamp_format = "%H:%M"
    rows = _plain(cli._user_message_block("Explain this error")).split("\n")
    assert len(rows) == 1
    assert rows[0].startswith(" " * 8 + "▌ Explain this error")
    assert re.search(r"\d\d:\d\d\s*$", rows[0])


def test_long_user_message_shows_its_ends_and_counts_the_rest(cli_stub):
    cli, _ = cli_stub
    cli.show_timestamps = False
    rows = _plain(cli._user_message_block("\n".join(f"line {i}" for i in range(8)))).split("\n")
    text = "\n".join(rows)
    assert "line 0" in text and "line 7" in text and "line 4" not in text
    assert "4" in text  # four lines hidden in the middle
    assert all("▌" in r[:10] for r in rows)
    assert len({cell_len(r) for r in rows}) == 1


def test_a_question_that_waits_on_the_reader_has_a_tinted_band():
    """The overlay's bar and band classes resolve to colours, so the block is visible on any skin."""
    from vael_cli import skin_engine

    skin_engine.set_active_skin("default")
    styles = skin_engine.get_prompt_toolkit_style_overrides()
    assert re.fullmatch(r"bg:#[0-9A-Fa-f]{6}", styles["journal-block-warn"])
    assert styles["journal-block-bar"].split()[1] == styles["journal-block-warn"]
