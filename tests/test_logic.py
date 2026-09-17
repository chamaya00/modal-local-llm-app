"""Issue #4, acceptance criteria 2, 4, and 7.

Exercises the state machine in `chatapp.logic` directly, with a stub
`generate_fn` standing in for the real vLLM call - no Gradio, no
Modal, no GPU required.
"""

from __future__ import annotations

import concurrent.futures
import time

import pytest

from chatapp import logic
from chatapp.logic import ColdStartTracker, Session, handle_message, initial_screen, verify_passcode


class _CountingGenerate:
    """Stub inference call: records whether/how it was invoked."""

    def __init__(self) -> None:
        self.count = 0

    def __call__(self, message: str, history: list) -> str:
        self.count += 1
        return f"echo: {message}"


@pytest.fixture
def executor():
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        yield pool


def test_initial_screen_is_paused_when_flag_set() -> None:
    assert initial_screen("true") == "paused"


def test_initial_screen_is_gate_when_not_paused() -> None:
    assert initial_screen("false") == "gate"
    assert initial_screen(None) == "gate"


def test_verify_passcode_correct_authenticates() -> None:
    session, screen, error = verify_passcode("secret", "secret", "false")
    assert session.authenticated is True
    assert screen == "chat"
    assert error == ""


def test_verify_passcode_wrong_does_not_authenticate() -> None:
    session, screen, error = verify_passcode("nope", "secret", "false")
    assert session.authenticated is False
    assert screen == "gate"
    assert error


def test_verify_passcode_while_paused_shows_paused_not_gate_or_chat() -> None:
    # A visitor who knows the passcode still lands on Paused, not Chat -
    # the paused check runs before the passcode check.
    session, screen, error = verify_passcode("secret", "secret", "true")
    assert session.authenticated is False
    assert screen == "paused"


def test_no_passcode_means_no_inference_call(executor) -> None:
    generate_fn = _CountingGenerate()
    session = Session(authenticated=False)

    events = list(
        handle_message("hi", [], session, "false", generate_fn, ColdStartTracker(), executor)
    )

    assert generate_fn.count == 0
    assert events[-1][0] == "gate"


def test_wrong_passcode_session_means_no_inference_call(executor) -> None:
    generate_fn = _CountingGenerate()
    # Simulates a request forged without a valid session - the exact
    # case the design doc calls out: a client that calls the
    # prediction endpoint directly without going through the gate.
    session = Session(authenticated=False)

    list(handle_message("ignore this", [], session, "false", generate_fn, ColdStartTracker(), executor))

    assert generate_fn.count == 0


def test_paused_blocks_inference_even_if_already_authenticated(executor) -> None:
    generate_fn = _CountingGenerate()
    session = Session(authenticated=True)

    events = list(
        handle_message("hi", [], session, "true", generate_fn, ColdStartTracker(), executor)
    )

    assert generate_fn.count == 0
    assert events[-1][0] == "paused"


def test_authenticated_and_not_paused_calls_inference_and_returns_response(executor) -> None:
    generate_fn = _CountingGenerate()
    session = Session(authenticated=True)
    tracker = ColdStartTracker()

    events = list(handle_message("hi", [], session, "false", generate_fn, tracker, executor))

    assert generate_fn.count == 1
    screen, status, response = events[-1]
    assert screen == "chat"
    assert response == "echo: hi"
    assert tracker.is_cold is False


def test_first_call_is_waking_up_second_call_is_thinking(executor) -> None:
    generate_fn = _CountingGenerate()
    session = Session(authenticated=True)
    tracker = ColdStartTracker()

    first_events = list(handle_message("hi", [], session, "false", generate_fn, tracker, executor))
    second_events = list(handle_message("again", [], session, "false", generate_fn, tracker, executor))

    assert first_events[0][1] == logic.WAKING_UP_TEXT
    assert second_events[0][1] == logic.THINKING_TEXT


def test_slow_cold_start_gets_taking_longer_follow_up(executor, monkeypatch) -> None:
    monkeypatch.setattr(logic, "WAKING_UP_CEILING_SECONDS", 0.01)
    monkeypatch.setattr(logic, "POLL_INTERVAL_SECONDS", 0.01)

    def slow_generate(message: str, history: list) -> str:
        time.sleep(0.1)
        return "done"

    session = Session(authenticated=True)
    tracker = ColdStartTracker()

    events = list(handle_message("hi", [], session, "false", slow_generate, tracker, executor))

    statuses = [status for _, status, _ in events]
    assert logic.STILL_WAKING_TEXT in statuses
