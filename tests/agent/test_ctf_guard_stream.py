"""A CyberAI flag split across streamed tokens never reaches the screen.

``test_ctf_guard.py`` covers whole strings; a stream arrives in pieces, so the tail that could still
become a flag is held back until it is known not to be one.
"""

from __future__ import annotations

import pytest

from agent.ctf_guard import WITHHELD, StreamingFlagScrubber
from agent.memory_manager import StreamingContextScrubber
from agent.stream_delivery import StreamDeliveryMixin


def stream(chunks):
    scrubber = StreamingFlagScrubber()
    out = [scrubber.feed(c) for c in chunks]
    out.append(scrubber.flush())
    return "".join(out)


@pytest.mark.parametrize(
    "chunks",
    [
        ["the flag is ", "CYBERAI{s3cr3t}", " ok"],
        ["flag: CYBER", "AI{s3c", "r3t} done"],
        ["flag: C", "y", "b", "e", "r", "a", "i", "{", "s", "3cr3t", "}", "."],
        ["cyberai", " {lower}", " tail"],
        ["x C​yb​er", "AI{zw}"],
    ],
)
def test_a_flag_split_across_chunks_is_withheld(chunks):
    out = stream(chunks)
    assert WITHHELD in out
    for leaked in ("s3cr3t", "s3c", "lower", "zw", "r3t}"):
        assert leaked not in out


def test_text_that_only_looks_like_the_start_of_a_flag_is_released():
    # Held back while it could still become a flag, released the moment it cannot.
    assert stream(["cyber ", "security is fun, cyberspace too"]) == "cyber security is fun, cyberspace too"
    assert stream(["a c", "at sat on a mat"]) == "a cat sat on a mat"


def test_nothing_is_lost_or_reordered_for_ordinary_text():
    chunks = ["Hello, ", "this is a long ", "answer about ", "cryptography and ", "c"]
    assert stream(chunks) == "".join(chunks)


def test_describing_the_format_passes_through():
    assert stream(["flags look like CYBER", "AI{...}", " here"]) == "flags look like CYBERAI{...} here"


def test_an_unterminated_flag_is_redacted_at_the_end_of_the_stream():
    out = stream(["leak: CYBERAI{half"])
    assert "half" not in out and WITHHELD in out


def test_a_very_long_open_brace_does_not_hold_the_stream_forever():
    out = stream(["CYBERAI{" + "a" * 900])
    assert "aaaa" not in out


class _Harness(StreamDeliveryMixin):
    """The delta path of AIAgent, with just the attributes it touches."""

    def __init__(self):
        self.seen = []
        self.stream_delta_callback = self.seen.append
        self._stream_callback = None
        self._stream_needs_break = False
        self._stream_context_scrubber = StreamingContextScrubber()
        self._stream_think_scrubber = None
        self._stream_flag_scrubber = StreamingFlagScrubber()
        self._streamed_assistant_text_parts = []

    def _stream_writer_superseded(self):
        return False

    def _strip_think_blocks(self, text):
        return text

    def _enqueue_stream_hook(self, event, **fields):
        pass


def test_the_real_delta_path_scrubs_a_split_flag_and_the_end_of_stream_flush():
    agent = _Harness()
    for piece in ["answer: CYBER", "AI{leak", "ed} and also CYBER", "AI{tail"]:
        agent._fire_stream_delta(piece)
    agent._reset_stream_delivery_tracking()
    shown = "".join(agent.seen)
    assert "leak" not in shown and "tail" not in shown
    assert shown.count(WITHHELD) == 2
    assert shown.startswith("answer: ")
