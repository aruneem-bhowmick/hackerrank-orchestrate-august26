"""Validation gates for the final six-column submission artifact."""

import math

import pandas as pd

from router.dataset.contract import validate_row_count_parity
from router.decision.message_type import ALLOWED_MESSAGE_TYPES
from router.errors import OutputValidationError, RowCountParityError
from router.output.writer import OUTPUT_COLUMNS

ALLOWED_ACTIONS = frozenset({"notify", "digest", "mute"})
"""The fixed action values accepted by the submission contract."""


def validate_output_frame(messages: pd.DataFrame, output: pd.DataFrame) -> None:
    """Raise OutputValidationError unless output is a valid submission frame.

    Checks exact columns/order, one-to-one message-id parity, populated action,
    message type, reason, confidence, and evidence fields, allowed actions and
    message types, finite confidence in ``[0, 1]``, and a meaningful evidence
    representation. Neither input frame is modified.
    """
    _validate_columns(output)
    _validate_parity(messages, output)
    for row_index, row in output.iterrows():
        _validate_required_values(row_index, row)
        _validate_action(row_index, row["action"])
        _validate_message_type(row_index, row["message_type"])
        _validate_confidence(row_index, row["confidence"])
        _validate_evidence(row_index, row["evidence_message_ids"])


def _validate_columns(output: pd.DataFrame) -> None:
    """Reject an output frame whose header does not exactly match the contract."""
    actual = tuple(output.columns)
    if actual != OUTPUT_COLUMNS:
        raise OutputValidationError(
            f"output columns must be {OUTPUT_COLUMNS}; received {actual}."
        )


def _validate_parity(messages: pd.DataFrame, output: pd.DataFrame) -> None:
    """Translate the shared parity guard's failure into an output-specific error."""
    try:
        validate_row_count_parity(messages, output)
    except RowCountParityError as exc:
        raise OutputValidationError(str(exc)) from exc


def _validate_required_values(row_index: object, row: pd.Series) -> None:
    """Reject blank/null values in every public value-bearing output field."""
    for field in ("action", "message_type", "reason", "confidence", "evidence_message_ids"):
        if _is_blank(row[field]):
            raise OutputValidationError(f"output row {row_index} has blank {field}.")


def _validate_action(row_index: object, value: object) -> None:
    """Require an action from the fixed notify/digest/mute vocabulary."""
    if value not in ALLOWED_ACTIONS:
        raise OutputValidationError(
            f"output row {row_index} has invalid action {value!r}; expected one of {sorted(ALLOWED_ACTIONS)}."
        )


def _validate_message_type(row_index: object, value: object) -> None:
    """Require a message type from the decision classifier's fixed vocabulary."""
    if value not in ALLOWED_MESSAGE_TYPES:
        raise OutputValidationError(f"output row {row_index} has invalid message_type {value!r}.")


def _validate_confidence(row_index: object, value: object) -> None:
    """Require a finite numeric confidence within the inclusive unit interval."""
    if isinstance(value, bool):
        raise OutputValidationError(f"output row {row_index} has non-numeric confidence {value!r}.")
    try:
        confidence = float(value)
    except (TypeError, ValueError) as exc:
        raise OutputValidationError(
            f"output row {row_index} has non-numeric confidence {value!r}."
        ) from exc
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise OutputValidationError(
            f"output row {row_index} has confidence outside [0, 1]: {value!r}."
        )


def _validate_evidence(row_index: object, value: object) -> None:
    """Require `none` or a comma-separated list of distinct, non-blank ids.

    `none` is only valid as the entire field; it may not appear alongside
    other ids, and no id may repeat.
    """
    if not isinstance(value, str):
        raise OutputValidationError(f"output row {row_index} has invalid evidence_message_ids {value!r}.")
    if value == "none":
        return
    parts = [part.strip() for part in value.split(",")]
    if any(not part for part in parts) or "none" in parts or len(set(parts)) != len(parts):
        raise OutputValidationError(f"output row {row_index} has invalid evidence_message_ids {value!r}.")


def _is_blank(value: object) -> bool:
    """Return whether a scalar output cell is null, empty, or whitespace-only."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False
