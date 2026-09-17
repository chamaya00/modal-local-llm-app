"""Issue #4, acceptance criterion 7 (UI-visibility half).

`chatapp.ui._visibility` is the function that turns a screen name into
the three component visibility flags - it is what guarantees
PausedScreen never renders alongside PasscodeGate or ChatPanel.
"""

from __future__ import annotations

from chatapp.ui import _visibility


def test_paused_screen_shows_only_paused_screen() -> None:
    paused, gate, chat = _visibility("paused")
    assert paused["visible"] is True
    assert gate["visible"] is False
    assert chat["visible"] is False


def test_gate_screen_shows_only_gate() -> None:
    paused, gate, chat = _visibility("gate")
    assert paused["visible"] is False
    assert gate["visible"] is True
    assert chat["visible"] is False


def test_chat_screen_shows_only_chat_panel() -> None:
    paused, gate, chat = _visibility("chat")
    assert paused["visible"] is False
    assert gate["visible"] is False
    assert chat["visible"] is True
