"""Unit tests for resolving image and voice media paths."""

from pathlib import Path

import pandas as pd
import pytest

from router.ingestion.media import lookup_media_file_path, resolve_media_path


def test_resolve_media_path_preserves_the_dataset_relative_location(tmp_path):
    """A media-table path is rooted at the active dataset directory."""
    assert resolve_media_path(tmp_path, "media/images/example.jpg") == (
        tmp_path / "media/images/example.jpg"
    )


@pytest.mark.parametrize("file_path", ["../outside.jpg", "/tmp/outside.jpg"])
def test_resolve_media_path_rejects_absolute_and_parent_traversal_paths(tmp_path, file_path):
    """Unsafe metadata paths cannot escape the dataset media directory."""
    assert resolve_media_path(tmp_path, file_path) is None


def test_resolve_media_path_rejects_a_symlink_that_escapes_the_media_directory(tmp_path):
    """A symlink under media cannot redirect OCR or ASR to an external file."""
    outside = tmp_path.parent / "outside.jpg"
    outside.write_bytes(b"not media")
    link = tmp_path / "media" / "images" / "escape.jpg"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable on this platform")

    assert resolve_media_path(tmp_path, "media/images/escape.jpg") is None


def test_lookup_media_file_path_returns_the_first_matching_record(tmp_path):
    """A known media ID resolves to its recorded relative path."""
    table = pd.DataFrame(
        [
            {"image_id": "img_1", "file_path": "media/images/first.jpg"},
            {"image_id": "img_1", "file_path": "media/images/second.jpg"},
        ]
    )

    assert lookup_media_file_path("img_1", table, "image_id", tmp_path) == (
        tmp_path / "media/images/first.jpg"
    )


def test_lookup_media_file_path_returns_none_for_blank_or_unknown_ids(tmp_path):
    """Missing references defer to the pipeline's graceful fallback path."""
    table = pd.DataFrame([{"voice_note_id": "vn_1", "file_path": "media/audio/one.mp3"}])

    assert lookup_media_file_path("", table, "voice_note_id", tmp_path) is None
    assert lookup_media_file_path("vn_missing", table, "voice_note_id", tmp_path) is None


@pytest.mark.parametrize("file_path", ["", "   ", float("nan"), pd.NA, None])
def test_lookup_media_file_path_returns_none_for_blank_or_non_string_paths(tmp_path, file_path):
    """Invalid media-table paths preserve the helper's never-raises fallback contract."""
    table = pd.DataFrame([{"image_id": "img_1", "file_path": file_path}])

    assert lookup_media_file_path("img_1", table, "image_id", tmp_path) is None


def test_lookup_media_file_path_returns_none_for_an_unsafe_media_reference(tmp_path):
    """Traversal metadata is converted to the caller's normal missing-media fallback."""
    table = pd.DataFrame([{"image_id": "img_1", "file_path": "../outside.jpg"}])

    assert lookup_media_file_path("img_1", table, "image_id", tmp_path) is None
