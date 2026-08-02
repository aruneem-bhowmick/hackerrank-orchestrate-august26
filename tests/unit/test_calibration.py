"""Unit coverage for solved-example calibration metrics."""

import pandas as pd
import pytest

from router.decision.trace import DecisionRecord
from router.errors import OutputValidationError
from router.output.calibration import build_sample_bundle, format_calibration_report, measure_calibration


def _record(message_id: str, action: str, message_type: str) -> DecisionRecord:
    """Return a minimal complete record with caller-selected public labels."""
    return DecisionRecord(
        message_id=message_id,
        action=action,
        message_type=message_type,
        reason="A concrete routing signal supports this choice.",
        confidence=0.8,
        evidence_message_ids=(),
        safety_confidence=0.0,
        value_score=0.5,
        urgency_score=0.5,
        signal_agreement=1.0,
        decision_basis=("no_signals",),
    )


def _sample() -> pd.DataFrame:
    """Return two solved rows with independent action and type outcomes."""
    return pd.DataFrame(
        [
            {"message_id": "one", "action": "notify", "message_type": "personal"},
            {"message_id": "two", "action": "digest", "message_type": "event"},
        ]
    )


def test_measure_calibration_reports_independent_action_and_type_rates():
    """REQ-P5-02 does not collapse action and message-type agreement into one metric."""
    decisions = {
        "one": _record("one", "notify", "personal"),
        "two": _record("two", "digest", "business_update"),
    }

    report = measure_calibration(decisions, _sample())

    assert (report.total, report.action_matches, report.message_type_matches) == (2, 2, 1)
    assert report.action_agreement == 1.0
    assert report.message_type_agreement == 0.5
    assert format_calibration_report(report) == "Sample calibration: action 2/2 (100.0%); message_type 1/2 (50.0%)."


def test_build_sample_bundle_excludes_solved_labels_from_routing_input(load_fixture_bundle):
    """REQ-P5-02 exposes only messages-schema fields to the sample routing path."""
    bundle = load_fixture_bundle("dataset_valid")

    sample_bundle = build_sample_bundle(bundle)

    assert tuple(sample_bundle.messages.columns) == tuple(bundle.messages.columns)
    assert "action" not in sample_bundle.messages
    assert sample_bundle.messages.equals(bundle.sample_messages.loc[:, bundle.messages.columns])


@pytest.mark.parametrize(
    ("sample", "decisions", "match"),
    [
        (pd.DataFrame(columns=["message_id", "action", "message_type"]), {}, "at least one"),
        (_sample().drop(columns="action"), {}, "missing calibration columns"),
        (pd.concat([_sample(), _sample().iloc[[0]]], ignore_index=True), {}, "duplicate"),
        (_sample(), {"one": _record("one", "notify", "personal")}, "disagree"),
    ],
)
def test_measure_calibration_rejects_uncomparable_sample_inputs(sample, decisions, match):
    """REQ-P5-02 rejects empty, malformed, duplicate, and id-mismatched samples."""
    with pytest.raises(OutputValidationError, match=match):
        measure_calibration(decisions, sample)
