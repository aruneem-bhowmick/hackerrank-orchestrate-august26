"""Resolves media_id references from messages.csv against images.csv/voice_notes.csv."""

from pathlib import Path

import pandas as pd


def resolve_media_path(dataset_dir: Path, relative_path: str) -> Path:
    """Join dataset_dir with a file_path value from images.csv/voice_notes.csv."""
    return dataset_dir / relative_path


def lookup_media_file_path(
    media_id: str, media_table: pd.DataFrame, id_column: str, dataset_dir: Path
) -> Path | None:
    """Resolve media_id to an absolute Path via media_table, or None if absent.

    media_table is bundle.images or bundle.voice_notes; id_column is
    "image_id" or "voice_note_id" respectively. Returns None when media_id
    is blank or has no matching row in media_table — on a duplicate
    media_id, the first match wins, matching
    code/router/safety/gate.py's _lookup_business convention. Never raises:
    a missing record is a normal, expected input for the caller to handle
    (see REQ-P2-04's fallback contract), not this function's error to
    surface.
    """
    if not media_id:
        return None
    matches = media_table.loc[media_table[id_column] == media_id]
    if matches.empty:
        return None
    return resolve_media_path(dataset_dir, matches.iloc[0]["file_path"])
