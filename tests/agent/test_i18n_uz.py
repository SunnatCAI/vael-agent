"""The Uzbek (Latin) catalog: registered, reachable by its names, and safe where the code parses input.

Key and placeholder parity with English is already enforced for every bundled language by
test_i18n.py and test_i18n_tui_packs.py; this file covers what is specific to a language whose word
for "no" begins with the letter the code treats as "yes".
"""

from __future__ import annotations

import pytest

from agent import i18n
from agent.i18n_languages import BUNDLED_LANGUAGE_INFO


@pytest.fixture(autouse=True)
def _clean_language_state(tmp_path, monkeypatch):
    monkeypatch.setenv("VAEL_HOME", str(tmp_path))
    i18n.reset_language_cache()
    yield
    i18n.reset_language_cache()


def test_uzbek_is_a_bundled_language_with_a_native_name():
    assert "uz" in i18n.SUPPORTED_LANGUAGES
    endonym, rtl = BUNDLED_LANGUAGE_INFO["uz"]
    assert endonym != "uz" and rtl is False


@pytest.mark.parametrize("name", ["uz", "UZ", "uz-UZ", "uz_uz", "uzbek", "Uzbek", "o'zbek", "o'zbekcha"])
def test_uzbek_is_reachable_by_code_region_and_name(name):
    assert i18n.resolve_language_id(name) == "uz"


def test_a_translated_sentence_is_served_for_uz_and_english_for_en():
    key = "gateway.approve.no_pending"
    assert i18n.t(key, lang="uz") != i18n.t(key, lang="en")


_APPROVAL_INPUTS = ("approve", "deny", "always", "session", "confirm_once", "confirm_always", "confirm_cancel")


@pytest.mark.parametrize("name", _APPROVAL_INPUTS)
def test_approval_replies_still_accept_the_english_words(name):
    """Typed replies are matched against these lists: a language adds its own words, never drops English."""
    def tokens(lang):
        return {w.strip() for w in i18n.t(f"approval.inputs.{name}", lang=lang).split(",")}
    assert tokens("en") <= tokens("uz")


def test_no_word_means_both_yes_and_no():
    def tokens(name):
        return {w.strip() for w in i18n.t(f"approval.inputs.{name}", lang="uz").split(",")}
    assert not tokens("approve") & tokens("deny")
    assert not tokens("always") & tokens("deny")


def test_yes_no_prompt_never_offers_the_letter_the_code_treats_as_yes_for_no():
    """cli_output treats any answer starting with ``y`` as yes. The Uzbek "no" (yo'q) starts with it,
    so the prompt must offer another letter for "no" and its own initial for "yes"."""
    yes_initial = i18n.t("cli.shared.yes_initial", lang="uz").strip().lower()
    assert yes_initial and yes_initial != "y"
    for key in ("cli.shared.yes_no_default_yes", "cli.shared.yes_no_default_no"):
        hint = i18n.t(key, lang="uz").lower()
        assert yes_initial in hint
        assert "y" not in hint.split("/")[1]
