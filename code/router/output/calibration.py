"""Self-validation metrics for the solved sample-message reference set."""

from dataclasses import dataclass, replace
from collections.abc import Mapping

import pandas as pd

from router.dataset.identifiers import diff_id_sets, find_duplicates
from router.dataset.loader import DatasetBundle
from router.dataset.schema import DATASET_FILES
from router.decision.trace import DecisionRecord
from router.errors import OutputValidationError

_MESSAGE_INPUT_COLUMNS = next(
    spec.required_columns for spec in DATASET_FILES if spec.attribute == "messages"
)
"""The messages.csv input schema, sourced from the dataset schema registry
so this never drifts independently of what the loader actually requires."""


@dataclass(frozen=True)
class CalibrationReport:
    """Action and message-type agreement counts and rates for solved examples."""

    total: int
    action_matches: int
    message_type_matches: int
    action_agreement: float
    message_type_agreement: float


def build_sample_bundle(bundle: DatasetBundle) -> DatasetBundle:
    """Return a bundle view that exposes sample inputs but never solved labels.

    The returned bundle shares all context tables with ``bundle`` and replaces
    only ``messages`` with a copy containing input-schema columns. This keeps
    reference action/type values out of every routing-stage input.
    """
    return replace(bundle, messages=bundle.sample_messages.loc[:, _MESSAGE_INPUT_COLUMNS].copy())


def measure_calibration(
    decisions: Mapping[str, DecisionRecord], sample_messages: pd.DataFrame
) -> CalibrationReport:
    """Return independent action/type agreement metrics for solved examples.

    Raises OutputValidationError for an empty sample, missing expected-label
    columns, duplicate sample ids, or a decision/id mismatch. Rates retain
    full precision so callers can choose their own display rounding.
    """
    _validate_sample_identifiers(decisions, sample_messages)
    total = len(sample_messages)
    action_matches = 0
    message_type_matches = 0
    for row in sample_messages.to_dict("records"):
        decision = decisions[row["message_id"]]
        action_matches += decision.action == row["action"]
        message_type_matches += decision.message_type == row["message_type"]
    return CalibrationReport(
        total=total,
        action_matches=action_matches,
        message_type_matches=message_type_matches,
        action_agreement=action_matches / total,
        message_type_agreement=message_type_matches / total,
    )


def format_calibration_report(report: CalibrationReport) -> str:
    """Render a compact, human-readable calibration summary for CLI output."""
    return (
        "Sample calibration: "
        f"action {report.action_matches}/{report.total} ({report.action_agreement:.1%}); "
        f"message_type {report.message_type_matches}/{report.total} "
        f"({report.message_type_agreement:.1%})."
    )


def _validate_sample_identifiers(
    decisions: Mapping[str, DecisionRecord], sample_messages: pd.DataFrame
) -> None:
    """Reject sample inputs that cannot be compared one-to-one with decisions."""
    required_columns = {"message_id", "action", "message_type"}
    missing_columns = sorted(required_columns - set(sample_messages.columns))
    if missing_columns:
        raise OutputValidationError(
            f"sample_messages is missing calibration columns: {missing_columns}."
        )
    if sample_messages.empty:
        raise OutputValidationError("sample_messages must contain at least one solved row.")
    sample_ids = list(sample_messages["message_id"])
    if find_duplicates(sample_ids):
        raise OutputValidationError("sample_messages contains duplicate message_id values.")
    missing, extra = diff_id_sets(sample_ids, decisions)
    if missing or extra:
        raise OutputValidationError(
            f"sample decisions disagree with sample message ids: missing={missing}; extra={extra}."
        )
