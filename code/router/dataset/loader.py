"""Loads and schema-validates every dataset file into one in-memory bundle."""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from router.dataset import integrity
from router.dataset.schema import DATASET_ALLOWLIST, DATASET_FILES, DatasetFileSpec
from router.errors import DatasetSchemaError


@dataclass
class DatasetBundle:
    """Every dataset/*.csv file loaded into memory, one DataFrame per file."""

    messages: pd.DataFrame
    output_template: pd.DataFrame
    sample_messages: pd.DataFrame
    users: pd.DataFrame
    groups: pd.DataFrame
    group_members: pd.DataFrame
    business_accounts: pd.DataFrame
    user_business_history: pd.DataFrame
    message_history: pd.DataFrame
    message_events: pd.DataFrame
    images: pd.DataFrame
    voice_notes: pd.DataFrame
    daily_notification_summary: pd.DataFrame


_ATTRIBUTE_BY_FILENAME = {
    "messages.csv": "messages",
    "output.csv": "output_template",
    "sample_messages.csv": "sample_messages",
    "users.csv": "users",
    "groups.csv": "groups",
    "group_members.csv": "group_members",
    "business_accounts.csv": "business_accounts",
    "user_business_history.csv": "user_business_history",
    "message_history.csv": "message_history",
    "message_events.csv": "message_events",
    "images.csv": "images",
    "voice_notes.csv": "voice_notes",
    "daily_notification_summary.csv": "daily_notification_summary",
}


def load_dataset_bundle(
    dataset_dir: str | Path, repo_root: str | Path | None = None
) -> DatasetBundle:
    """Load and schema-validate all dataset files into a DatasetBundle.

    Runs the dataset integrity guard first, scanning repo_root (default:
    dataset_dir's parent, correct for the real project layout where
    dataset/ is a direct child of the repo root) for organizer-only or
    hidden ground-truth files. Pass repo_root explicitly to scope that
    scan to something other than the default, e.g. in a test where
    dataset_dir's real parent is a shared fixtures directory unrelated to
    this call. Raises DatasetSchemaError if any file is missing,
    unreadable, or missing a required column, and DatasetIntegrityError
    (via the guard) if an organizer-only or hidden ground-truth file is
    discoverable. Never returns a partially-populated bundle: either every
    file loads and validates, or the call raises.
    """
    dataset_path = Path(dataset_dir)
    root_path = _resolve_repo_root(dataset_path, repo_root)

    integrity.enforce_dataset_integrity(
        repo_root=root_path,
        dataset_dir=dataset_path,
        allowlist=DATASET_ALLOWLIST,
    )

    loaded = {
        _ATTRIBUTE_BY_FILENAME[spec.filename]: _load_csv(dataset_path, spec)
        for spec in DATASET_FILES
    }
    return DatasetBundle(**loaded)


def _resolve_repo_root(dataset_dir: Path, repo_root: str | Path | None) -> Path:
    """Resolve the root to scan for integrity violations.

    Defaults to dataset_dir's parent, correct when dataset/ is a direct
    child of the repo root (the real project layout). Callers with a
    different layout must pass repo_root explicitly; this function makes
    that default an explicit, independently testable contract rather than
    an inline expression.
    """
    return Path(repo_root) if repo_root is not None else dataset_dir.parent


def _load_csv(dataset_dir: Path, spec: DatasetFileSpec) -> pd.DataFrame:
    """Read one CSV as all-string columns and validate its required columns."""
    path = dataset_dir / spec.filename
    if not path.exists():
        raise DatasetSchemaError(
            f"Missing dataset file: expected '{spec.filename}' at '{path}'."
        )

    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise DatasetSchemaError(
            f"Could not parse '{spec.filename}' at '{path}': {exc}"
        ) from exc

    missing = sorted(set(spec.required_columns) - set(frame.columns))
    if missing:
        raise DatasetSchemaError(
            f"'{spec.filename}' is missing required column(s): {', '.join(missing)}."
        )

    return frame
