"""Resolves media_id references from messages.csv against images.csv/voice_notes.csv."""

from pathlib import Path

import pandas as pd


def resolve_media_path(dataset_dir: Path, relative_path: str) -> Path | None:
    """Resolve a media reference only when it remains below dataset_dir/media.

    Resolving before the containment check prevents absolute paths, parent
    traversal, and symlink escapes from reaching OCR or ASR file reads. A
    rejected reference returns None so callers use their established explicit
    media-failure fallback instead of opening an arbitrary local file.
    """
    media_root = (dataset_dir / "media").resolve()
    candidate = (dataset_dir / relative_path).resolve()
    return candidate if candidate.is_relative_to(media_root) else None


def lookup_media_file_path(
    media_id: str, media_table: pd.DataFrame, id_column: str, dataset_dir: Path
) -> Path | None:
    """Resolve media_id to a contained media Path via media_table, or None if absent.

    media_table is bundle.images or bundle.voice_notes; id_column is
    "image_id" or "voice_note_id" respectively. Returns None when media_id
    is blank or has no matching row in media_table — on a duplicate
    media_id, the first match wins, matching
    code/router/safety/gate.py's _lookup_business convention. Never raises:
    a missing record or unsafe path is a normal, expected input for the caller
    to handle as an ingestion fallback case, not this function's error to
    surface.
    """
    if not media_id:
        return None
    matches = media_table.loc[media_table[id_column] == media_id]
    if matches.empty:
        return None
    file_path = matches.iloc[0]["file_path"]
    if not isinstance(file_path, str) or not file_path.strip():
        return None
    return resolve_media_path(dataset_dir, file_path)
