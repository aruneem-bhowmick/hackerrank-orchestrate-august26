import pandas as pd
import pytest

from router.dataset.contract import validate_row_count_parity
from router.errors import RowCountParityError


def test_validate_row_count_parity_passes_on_matching_ids_in_any_order():
    messages = pd.DataFrame({"message_id": ["m1", "m2"]})
    output = pd.DataFrame({"message_id": ["m2", "m1"]})
    assert validate_row_count_parity(messages, output) is None


def test_validate_row_count_parity_raises_on_count_mismatch():
    messages = pd.DataFrame({"message_id": ["m1", "m2"]})
    output = pd.DataFrame({"message_id": ["m1"]})
    with pytest.raises(RowCountParityError, match="Row count mismatch"):
        validate_row_count_parity(messages, output)


def test_validate_row_count_parity_raises_on_id_set_mismatch_with_equal_counts():
    messages = pd.DataFrame({"message_id": ["m1", "m2"]})
    output = pd.DataFrame({"message_id": ["m1", "m3"]})
    with pytest.raises(RowCountParityError, match="message_id sets disagree"):
        validate_row_count_parity(messages, output)


def test_count_and_id_mismatch_errors_are_distinguishable():
    messages = pd.DataFrame({"message_id": ["m1", "m2"]})
    with pytest.raises(RowCountParityError) as count_exc:
        validate_row_count_parity(messages, pd.DataFrame({"message_id": ["m1"]}))
    with pytest.raises(RowCountParityError) as id_exc:
        validate_row_count_parity(messages, pd.DataFrame({"message_id": ["m1", "m3"]}))
    assert str(count_exc.value) != str(id_exc.value)
