from __future__ import annotations

from chatapp.gating import check_passcode, is_paused


def test_check_passcode_correct() -> None:
    assert check_passcode("open-sesame", "open-sesame") is True


def test_check_passcode_wrong() -> None:
    assert check_passcode("nope", "open-sesame") is False


def test_check_passcode_missing_submission() -> None:
    assert check_passcode(None, "open-sesame") is False
    assert check_passcode("", "open-sesame") is False


def test_check_passcode_missing_expected() -> None:
    assert check_passcode("anything", None) is False
    assert check_passcode("anything", "") is False


def test_is_paused_true_values() -> None:
    assert is_paused("true") is True
    assert is_paused("True") is True
    assert is_paused("  TRUE  ") is True


def test_is_paused_false_values() -> None:
    assert is_paused("false") is False
    assert is_paused(None) is False
    assert is_paused("") is False
    assert is_paused("1") is False
