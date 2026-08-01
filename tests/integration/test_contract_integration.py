from pathlib import Path

import pytest

from router.dataset.contract import validate_row_count_parity
from router.dataset.loader import load_dataset_bundle
from router.errors import RowCountParityError

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _load(fixture_name: str):
    fixture_dir = FIXTURES_DIR / fixture_name
    return load_dataset_bundle(fixture_dir, repo_root=fixture_dir)


def test_validate_row_count_parity_passes_on_valid_fixture():
    bundle = _load("dataset_valid")
    assert validate_row_count_parity(bundle.messages, bundle.output_template) is None


def test_validate_row_count_parity_raises_on_row_count_mismatch_fixture():
    bundle = _load("dataset_row_count_mismatch")
    with pytest.raises(RowCountParityError, match="Row count mismatch"):
        validate_row_count_parity(bundle.messages, bundle.output_template)
