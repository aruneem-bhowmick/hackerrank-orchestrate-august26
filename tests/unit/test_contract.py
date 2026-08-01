"""Unit tests for the messages/output row-count parity validator."""

import pandas as pd
import pytest

from router.dataset.contract import validate_row_count_parity
from router.errors import RowCountParityError


def test_validate_row_count_parity_passes_on_matching_ids_in_any_order():
    """Equal row counts and identical ID sets pass regardless of row order."""
    messages = pd.DataFrame({"message_id": ["m1", "m2"]})
    output = pd.DataFrame({"message_id": ["m2", "m1"]})
    assert validate_row_count_parity(messages, output) is None


def test_validate_row_count_parity_raises_on_count_mismatch():
    """Differing row counts raise, naming both counts."""
    messages = pd.DataFrame({"message_id": ["m1", "m2"]})
    output = pd.DataFrame({"message_id": ["m1"]})
    with pytest.raises(RowCountParityError, match="Row count mismatch"):
        validate_row_count_parity(messages, output)


def test_validate_row_count_parity_raises_on_id_set_mismatch_with_equal_counts():
    """Equal row counts with a differing ID set still raise."""
    messages = pd.DataFrame({"message_id": ["m1", "m2"]})
    output = pd.DataFrame({"message_id": ["m1", "m3"]})
    with pytest.raises(RowCountParityError, match="message_id sets disagree"):
        validate_row_count_parity(messages, output)


def test_count_and_id_mismatch_errors_are_distinguishable():
    """The two failure shapes produce different, non-generic error messages."""
    messages = pd.DataFrame({"message_id": ["m1", "m2"]})
    with pytest.raises(RowCountParityError) as count_exc:
        validate_row_count_parity(messages, pd.DataFrame({"message_id": ["m1"]}))
    with pytest.raises(RowCountParityError) as id_exc:
        validate_row_count_parity(messages, pd.DataFrame({"message_id": ["m1", "m3"]}))
    assert str(count_exc.value) != str(id_exc.value)
