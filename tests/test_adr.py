"""Issue #4, acceptance criterion 6.

ADR 0001 was written by role:researcher, which has no test directory
to prove its own acceptance criteria against. This test is that proof,
added by the engineer child instead. It reads the committed ADR file
and asserts its structure and required facts are present - it does
not re-derive the numbers, only that the document states them.
"""

from __future__ import annotations

from pathlib import Path

ADR_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "decisions"
    / "0001-model-and-gpu-selection.md"
)

REQUIRED_HEADERS = [
    "## Context",
    "## Decision",
    "## Consequences",
    "## Alternatives rejected",
]

REQUIRED_FACTS = [
    "Qwen2.5-14B-Instruct",
    "14.7B",
    "L40S",
    "Gated weights: No",
]


def _read_adr() -> str:
    return ADR_PATH.read_text(encoding="utf-8")


def test_adr_file_exists() -> None:
    assert ADR_PATH.is_file(), f"expected ADR at {ADR_PATH}"


def test_adr_has_required_section_headers() -> None:
    text = _read_adr()
    for header in REQUIRED_HEADERS:
        assert header in text, f"ADR is missing section header {header!r}"


def test_adr_states_required_facts() -> None:
    text = _read_adr()
    for fact in REQUIRED_FACTS:
        assert fact in text, f"ADR is missing required fact {fact!r}"


def test_adr_has_cost_estimate_with_numeric_monthly_total() -> None:
    text = _read_adr()
    assert "### Cost estimate" in text, "ADR is missing a '### Cost estimate' subsection"
    cost_section = text.split("### Cost estimate", 1)[1].split("## Consequences", 1)[0]
    assert "Monthly cost" in cost_section
    assert "$" in cost_section and "/month" in cost_section, (
        "cost estimate section has no numeric monthly total"
    )
