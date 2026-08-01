"""Integration tests for row-count parity against real loaded fixtures."""

import pytest

from router.dataset.contract import validate_row_count_parity
from router.errors import RowCountParityError


def test_validate_row_count_parity_passes_on_valid_fixture(load_fixture_bundle):
    """A fixture whose messages and output template agree passes parity."""
    bundle = load_fixture_bundle("dataset_valid")
    assert validate_row_count_parity(bundle.messages, bundle.output_template) is None


def test_validate_row_count_parity_raises_on_row_count_mismatch_fixture(load_fixture_bundle):
    """A fixture with an extra output row fails parity, naming the mismatch."""
    bundle = load_fixture_bundle("dataset_row_count_mismatch")
    with pytest.raises(RowCountParityError, match="Row count mismatch"):
        validate_row_count_parity(bundle.messages, bundle.output_template)
