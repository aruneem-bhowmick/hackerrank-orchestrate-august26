"""Deterministic conversion of decision records into the submission CSV."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd

from router.decision.trace import DecisionRecord
from router.errors import OutputValidationError

OUTPUT_COLUMNS = (
    "message_id",
    "action",
    "message_type",
    "reason",
    "confidence",
    "evidence_message_ids",
)
"""The exact, ordered columns required by the submission contract."""


def build_output_frame(
    message_ids: Sequence[str], decisions: Mapping[str, DecisionRecord]
) -> pd.DataFrame:
    """Return one ordered submission row per message id without writing I/O.

    Empty evidence ids are serialized as the required ``none`` sentinel and
    populated evidence ids use a deterministic comma-separated representation.
    Raises OutputValidationError when source identifiers and decision records
    cannot form a one-to-one mapping. Semantic field validation is performed
    separately by ``validate_output_frame``.
    """
    source_ids = list(message_ids)
    _validate_decision_identifiers(source_ids, decisions)
    rows = [_serialize_record(message_id, decisions[message_id]) for message_id in source_ids]
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def write_output_csv(frame: pd.DataFrame, path: str | Path) -> Path:
    """Atomically write a prepared submission frame as UTF-8 CSV and return its path.

    Callers must validate the frame before calling this function. The temporary
    file is written in the destination directory and atomically replaced only
    after CSV generation succeeds, avoiding a partially written artifact.
    """
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", suffix=".tmp", dir=output_path.parent, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            frame.to_csv(temporary, index=False, columns=OUTPUT_COLUMNS, lineterminator="\n")
        temporary_path.replace(output_path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
    return output_path


def _validate_decision_identifiers(
    message_ids: Sequence[str], decisions: Mapping[str, DecisionRecord]
) -> None:
    """Reject duplicate, missing, extra, or internally inconsistent decision identifiers."""
    source_ids = list(message_ids)
    if len(set(source_ids)) != len(source_ids):
        raise OutputValidationError("messages contain duplicate message_id values.")

    source_set = set(source_ids)
    decision_set = set(decisions)
    if decision_set != source_set:
        missing = sorted(source_set - decision_set)
        extra = sorted(decision_set - source_set)
        raise OutputValidationError(
            f"decision records disagree with source message ids: missing={missing}; extra={extra}."
        )

    inconsistent = sorted(
        key for key, record in decisions.items() if key != record.message_id
    )
    if inconsistent:
        raise OutputValidationError(
            f"decision mapping keys do not match DecisionRecord.message_id: {inconsistent}."
        )


def _serialize_record(message_id: str, record: DecisionRecord) -> dict[str, object]:
    """Select the six public fields from one DecisionRecord for CSV serialization."""
    evidence = ",".join(record.evidence_message_ids) if record.evidence_message_ids else "none"
    return {
        "message_id": message_id,
        "action": record.action,
        "message_type": record.message_type,
        "reason": record.reason,
        "confidence": record.confidence,
        "evidence_message_ids": evidence,
    }
