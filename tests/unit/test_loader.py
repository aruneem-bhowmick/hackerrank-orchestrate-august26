"""Unit tests for single-file CSV loading and column validation."""

from pathlib import Path

import pytest

from router.dataset.loader import _load_csv, _resolve_repo_root
from router.dataset.schema import DatasetFileSpec
from router.errors import DatasetSchemaError

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "dataset_valid"


def test_resolve_repo_root_defaults_to_dataset_dir_parent():
    """With no override, the scan root is the dataset directory's parent."""
    assert _resolve_repo_root(Path("/x/dataset"), None) == Path("/x")


def test_resolve_repo_root_honors_explicit_override():
    """An explicit repo_root takes precedence over the default derivation."""
    assert _resolve_repo_root(Path("/x/dataset"), Path("/y")) == Path("/y")


def test_load_csv_returns_string_dtype_with_empty_string_for_blank_cell():
    """A blank cell loads as an empty string, not a pandas NaN."""
    spec = DatasetFileSpec(
        "user_business_history.csv",
        ("user_id", "business_id", "promotions_opted_out_at"),
    )
    frame = _load_csv(FIXTURES_DIR, spec)
    assert frame["promotions_opted_out_at"].dtype == object
    assert frame.loc[0, "promotions_opted_out_at"] == ""


def test_load_csv_raises_on_missing_required_column():
    """A required column absent from the file raises, naming the column."""
    spec = DatasetFileSpec("users.csv", ("user_id", "not_a_real_column"))
    with pytest.raises(DatasetSchemaError, match="not_a_real_column"):
        _load_csv(FIXTURES_DIR, spec)


def test_load_csv_raises_on_missing_file():
    """A file that does not exist on disk raises, naming the filename."""
    spec = DatasetFileSpec("does_not_exist.csv", ())
    with pytest.raises(DatasetSchemaError, match="does_not_exist.csv"):
        _load_csv(FIXTURES_DIR, spec)


def test_load_csv_raises_dataset_schema_error_on_empty_file(tmp_path):
    """A zero-byte CSV raises DatasetSchemaError, not a raw pandas exception."""
    (tmp_path / "empty.csv").write_text("")
    spec = DatasetFileSpec("empty.csv", ())
    with pytest.raises(DatasetSchemaError, match="empty.csv"):
        _load_csv(tmp_path, spec)
