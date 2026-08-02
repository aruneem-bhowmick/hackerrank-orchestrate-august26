"""Validates that messages.csv and output.csv agree on which rows exist."""

import pandas as pd

from router.dataset.identifiers import diff_id_sets
from router.errors import RowCountParityError


def validate_row_count_parity(messages: pd.DataFrame, output: pd.DataFrame) -> None:
    """Raise RowCountParityError unless messages and output match 1:1.

    Checks row-count equality first, then message_id set equality, so a
    pure count mismatch and a same-count-different-rows mismatch produce
    distinguishable error messages. Safe to call more than once against
    the same or an updated output (e.g. once at load time, again after
    predictions are written).
    """
    if len(messages) != len(output):
        raise RowCountParityError(
            f"Row count mismatch: messages.csv has {len(messages)} row(s), "
            f"output.csv has {len(output)} row(s)."
        )

    missing_from_output, missing_from_messages = diff_id_sets(messages["message_id"], output["message_id"])
    if missing_from_output or missing_from_messages:
        raise RowCountParityError(
            "message_id sets disagree between messages.csv and output.csv: "
            f"missing from output.csv: {missing_from_output}; "
            f"missing from messages.csv: {missing_from_messages}."
        )
