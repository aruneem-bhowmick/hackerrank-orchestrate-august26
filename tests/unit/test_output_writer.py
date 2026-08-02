"""Unit coverage for deterministic submission-frame serialization."""

import pandas as pd
import pytest

from router.decision.trace import DecisionRecord
from router.errors import OutputValidationError
from router.output.writer import OUTPUT_COLUMNS, build_output_frame, write_output_csv


def _record(message_id: str, evidence_ids: tuple[str, ...] = ()) -> DecisionRecord:
    """Return a complete decision record suitable for output serialization tests."""
    return DecisionRecord(
        message_id=message_id,
        action="digest",
        message_type="personal",
        reason="A direct message has no time-sensitive signal.",
        confidence=0.75,
        evidence_message_ids=evidence_ids,
        safety_confidence=0.0,
        value_score=0.5,
        urgency_score=0.5,
        signal_agreement=1.0,
        decision_basis=("no_signals",),
    )


def test_build_output_frame_preserves_source_order_and_evidence_sentinel():
    """REQ-P5-01 serializes decisions in source order and uses `none` when empty."""
    decisions = {"later": _record("later", ("history_2", "history_1")), "first": _record("first")}

    frame = build_output_frame(["first", "later"], decisions)

    assert tuple(frame.columns) == OUTPUT_COLUMNS
    assert frame["message_id"].tolist() == ["first", "later"]
    assert frame["evidence_message_ids"].tolist() == ["none", "history_2;history_1"]


@pytest.mark.parametrize(
    ("message_ids", "decisions", "match"),
    [
        (["one", "one"], {"one": _record("one")}, "duplicate"),
        (["one"], {}, "missing"),
        (["one"], {"one": _record("one"), "two": _record("two")}, "extra"),
        (["one"], {"one": _record("different")}, "do not match"),
    ],
)
def test_build_output_frame_rejects_identifier_contract_violations(message_ids, decisions, match):
    """REQ-P5-01 rejects duplicate, missing, extra, and mismatched decision ids."""
    with pytest.raises(OutputValidationError, match=match):
        build_output_frame(message_ids, decisions)


def test_write_output_csv_writes_a_readable_utf8_submission(tmp_path):
    """REQ-P5-01 writes the exact serialized frame without an index column."""
    frame = build_output_frame(
        ["one", "two"],
        {"one": _record("one"), "two": _record("two", ("history_2", "history_1"))},
    )
    destination = tmp_path / "nested" / "output.csv"

    written = write_output_csv(frame, destination)

    parsed = pd.read_csv(written, dtype=str, keep_default_na=False)
    assert written == destination
    assert tuple(parsed.columns) == OUTPUT_COLUMNS
    assert parsed.to_dict("records") == frame.astype(str).to_dict("records")
    assert parsed.loc[parsed["message_id"] == "two", "evidence_message_ids"].item() == "history_2;history_1"
    assert b"\r\n" not in written.read_bytes()
