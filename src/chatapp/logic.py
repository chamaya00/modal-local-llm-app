"""Session state machine for the chat flow.

Framework-agnostic: `ui.py` wires these onto Gradio components, but
none of this module imports Gradio, so it can be unit tested directly
against a stub `generate_fn` with no server, no Modal, and no GPU.
"""

from __future__ import annotations

import concurrent.futures
import time
from collections.abc import Callable, Generator
from dataclasses import dataclass
from typing import Any

from chatapp.gating import check_passcode, is_paused

# ADR 0001's cold-start estimate (unverified there; the engineer
# acceptance criteria call for correcting it once measured against a
# real deployment - see the PR description for the measured figure).
WAKING_UP_CEILING_SECONDS = 90
STILL_WAKING_MULTIPLIER = 1.5
POLL_INTERVAL_SECONDS = 1.0

WAKING_UP_TEXT = (
    f"Waking up the model — this can take up to about "
    f"{WAKING_UP_CEILING_SECONDS} seconds on a cold start."
)
STILL_WAKING_TEXT = "Still waking up — this is taking longer than expected."
THINKING_TEXT = "Thinking…"
INCORRECT_PASSCODE_TEXT = "Incorrect passcode — try again."
PAUSED_TEXT = (
    "This demo is paused to stay within its monthly compute budget. "
    "It'll be back after the credit resets."
)

Screen = str  # "paused" | "gate" | "chat"


@dataclass
class ColdStartTracker:
    """Tracks whether this container has already served one response.

    One instance lives per Modal container (set on the serving class),
    so the first inference call after a cold start sees `is_cold`
    True and every call after `mark_warm()` sees it False - that is
    how the UI knows to show "Waking Up" instead of "Thinking".
    """

    warm: bool = False

    @property
    def is_cold(self) -> bool:
        return not self.warm

    def mark_warm(self) -> None:
        self.warm = True


@dataclass
class Session:
    """Per-visitor state held in a Gradio `gr.State`."""

    authenticated: bool = False


def initial_screen(paused_flag: str | None) -> Screen:
    """Which top-level screen a fresh page load should show.

    The paused check runs before anything else, so a visitor who
    knows the passcode sees the same paused screen as one who
    doesn't - it is checked ahead of, not instead of, the gate.
    """
    return "paused" if is_paused(paused_flag) else "gate"


def verify_passcode(
    submitted: str | None, expected_passcode: str | None, paused_flag: str | None
) -> tuple[Session, Screen, str]:
    """Handle a Passcode Gate submission.

    Returns the resulting session, which screen to show, and an error
    message (empty unless the screen is still "gate").
    """
    if is_paused(paused_flag):
        return Session(authenticated=False), "paused", ""
    if check_passcode(submitted, expected_passcode):
        return Session(authenticated=True), "chat", ""
    return Session(authenticated=False), "gate", INCORRECT_PASSCODE_TEXT


def run_chat_turn(
    message: str,
    history: list[Any],
    generate_fn: Callable[[str, list[Any]], str],
    tracker: ColdStartTracker,
    executor: concurrent.futures.Executor,
) -> Generator[tuple[str, str | None], None, None]:
    """Run one inference call, yielding (status_text, response) pairs.

    `response` is None on every yield except the last, so callers can
    tell "still waiting, here is the status line" from "done, here is
    the reply". Runs `generate_fn` on `executor` so this generator can
    keep yielding status updates - including the "taking longer than
    expected" follow-up - while inference is in flight.
    """
    cold = tracker.is_cold
    status = WAKING_UP_TEXT if cold else THINKING_TEXT
    yield status, None

    future = executor.submit(generate_fn, message, history)
    start = time.monotonic()
    warned = False
    while True:
        try:
            response = future.result(timeout=POLL_INTERVAL_SECONDS)
            break
        except concurrent.futures.TimeoutError:
            elapsed = time.monotonic() - start
            if cold and not warned and elapsed > WAKING_UP_CEILING_SECONDS * STILL_WAKING_MULTIPLIER:
                warned = True
                yield STILL_WAKING_TEXT, None

    tracker.mark_warm()
    yield "", response


def handle_message(
    message: str,
    history: list[Any],
    session: Session,
    paused_flag: str | None,
    generate_fn: Callable[[str, list[Any]], str],
    tracker: ColdStartTracker,
    executor: concurrent.futures.Executor,
) -> Generator[tuple[Screen, str, str | None], None, None]:
    """Top-level handler for a submitted chat message.

    This is the single choke point `generate_fn` can be reached
    through, so it is also the function the passcode-gate and paused
    tests assert against: both gates must reject the message *before*
    `run_chat_turn` (and therefore `generate_fn`) is ever called.
    """
    if is_paused(paused_flag):
        yield "paused", "", None
        return
    if not session.authenticated:
        yield "gate", INCORRECT_PASSCODE_TEXT, None
        return
    for status, response in run_chat_turn(message, history, generate_fn, tracker, executor):
        yield "chat", status, response
