"""Unit coverage for submission-field validation."""

import math

import pandas as pd
import pytest

from router.errors import OutputValidationError
from router.output.validation import validate_output_frame
from router.output.writer import OUTPUT_COLUMNS


def _messages() -> pd.DataFrame:
    """Return the minimal source-message frame required by the parity guard."""
    return pd.DataFrame({"message_id": ["one"]})


def _output(**overrides: object) -> pd.DataFrame:
    """Return one valid output row with selected values overridden."""
    row = {
        "message_id": "one",
        "action": "notify",
        "message_type": "personal",
        "reason": "A direct request needs attention.",
        "confidence": 0.8,
        "evidence_message_ids": "none",
    }
    row.update(overrides)
    return pd.DataFrame([row], columns=OUTPUT_COLUMNS)


def test_validate_output_frame_accepts_complete_boundary_values():
    """REQ-P5-03 accepts both confidence endpoints and the `none` evidence sentinel."""
    first = _output(confidence=0.0, evidence_message_ids="none")
    second = _output(confidence=1.0, evidence_message_ids="history_1,history_2")

    validate_output_frame(_messages(), first)
    validate_output_frame(_messages(), second)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("action", ""),
        ("message_type", "  "),
        ("reason", None),
        ("confidence", ""),
        ("evidence_message_ids", None),
    ],
)
def test_validate_output_frame_rejects_blank_public_fields(field, value):
    """REQ-P5-03 rejects null, empty, and whitespace-only required values."""
    with pytest.raises(OutputValidationError, match=field):
        validate_output_frame(_messages(), _output(**{field: value}))


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("action", "later", "invalid action"),
        ("message_type", "invented", "invalid message_type"),
        ("confidence", True, "non-numeric"),
        ("confidence", "unknown", "non-numeric"),
        ("confidence", math.nan, "blank confidence"),
        ("confidence", math.inf, "outside"),
        ("confidence", -0.01, "outside"),
        ("confidence", 1.01, "outside"),
        ("evidence_message_ids", "history_1,", "invalid evidence"),
        ("evidence_message_ids", ",history_1", "invalid evidence"),
    ],
)
def test_validate_output_frame_rejects_invalid_field_values(field, value, match):
    """REQ-P5-03 rejects unsupported action/type/confidence/evidence values."""
    with pytest.raises(OutputValidationError, match=match):
        validate_output_frame(_messages(), _output(**{field: value}))


def test_validate_output_frame_rejects_wrong_header_and_identifier_parity():
    """REQ-P5-03 retains exact-header and one-to-one identifier enforcement."""
    wrong_header = _output().rename(columns={"reason": "why"})
    wrong_id = _output(message_id="other")

    with pytest.raises(OutputValidationError, match="columns"):
        validate_output_frame(_messages(), wrong_header)
    with pytest.raises(OutputValidationError, match="message_id sets disagree"):
        validate_output_frame(_messages(), wrong_id)
