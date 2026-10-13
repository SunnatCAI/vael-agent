"""CyberAI flags never come out of the agent: not in what it reads from tools, not in what it replies.

The mentor rule in the system prompt is advice; these are the contracts behind it.
"""

from __future__ import annotations

import pytest

from agent import ctf_guard
from agent.ctf_guard import WITHHELD, withhold_flags
from agent.turn_finalizer import apply_llm_output_transform


@pytest.mark.parametrize(
    "text",
    [
        "the flag is CYBERAI{s3cr3t_v4lue}",
        "cyberai{lowercase_trick}",
        "C​y​b​e​r​A​I{zero_width}",
        "CYBERAI {spaced}",
        "cut off by a limit: CYBERAI{half_a_fla",
        "two: CYBERAI{a} and CYBERAI{b}",
    ],
)
def test_a_flag_in_any_spelling_is_withheld(text):
    out = withhold_flags(text)
    assert WITHHELD in out
    for leaked in ("s3cr3t", "lowercase_trick", "zero_width", "spaced", "half_a_fla", "{a}", "{b}"):
        assert leaked not in out


@pytest.mark.parametrize("text", ["flags look like CYBERAI{...}", "format: CYBERAI{…}", "plain words", ""])
def test_describing_the_format_is_not_a_flag(text):
    assert withhold_flags(text) == text


def test_non_strings_pass_through_untouched():
    payload = {"k": "CYBERAI{x}"}
    assert withhold_flags(payload) is payload
    assert withhold_flags(None) is None


def test_the_guard_is_idempotent():
    once = withhold_flags("CYBERAI{abc}")
    assert withhold_flags(once) == once


class _Agent:
    session_id = "s"
    model = "m"
    platform = "cli"


def test_the_final_reply_is_scrubbed_before_it_is_stored_or_shown():
    reply, transformed, _ = apply_llm_output_transform(_Agent(), "here: CYBERAI{leak}", turn_id="t1")
    assert "leak" not in reply and WITHHELD in reply


def test_the_scrub_still_applies_when_the_turn_already_recorded_an_outcome():
    agent = _Agent()
    apply_llm_output_transform(agent, "first", turn_id="t1")
    reply, _, _ = apply_llm_output_transform(agent, "again CYBERAI{leak}", turn_id="t1")
    assert "leak" not in reply


def test_the_mentor_rule_names_the_flag_format_and_forbids_solving():
    text = ctf_guard.CYBERAI_MENTOR_GUIDANCE
    assert "CYBERAI{" in text and "Never" in text
