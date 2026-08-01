from pathlib import Path

import pytest

from router.dataset.loader import _load_csv
from router.dataset.schema import DatasetFileSpec
from router.errors import DatasetSchemaError

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "dataset_valid"


def test_load_csv_returns_string_dtype_with_empty_string_for_blank_cell():
    spec = DatasetFileSpec(
        "user_business_history.csv",
        ("user_id", "business_id", "promotions_opted_out_at"),
    )
    frame = _load_csv(FIXTURES_DIR, spec)
    assert frame["promotions_opted_out_at"].dtype == object
    assert frame.loc[0, "promotions_opted_out_at"] == ""


def test_load_csv_raises_on_missing_required_column():
    spec = DatasetFileSpec("users.csv", ("user_id", "not_a_real_column"))
    with pytest.raises(DatasetSchemaError, match="not_a_real_column"):
        _load_csv(FIXTURES_DIR, spec)


def test_load_csv_raises_on_missing_file():
    spec = DatasetFileSpec("does_not_exist.csv", ())
    with pytest.raises(DatasetSchemaError, match="does_not_exist.csv"):
        _load_csv(FIXTURES_DIR, spec)
