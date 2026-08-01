"""Unit tests for the coarse image category boundary."""

import pytest

from router.ingestion.categories import IMAGE_CATEGORIES, VOICE_NOTE_CATEGORY, validate_image_category


@pytest.mark.parametrize("category", sorted(IMAGE_CATEGORIES))
def test_known_image_categories_are_preserved(category):
    """Every approved coarse category can inform later message-type selection."""
    assert validate_image_category(category) == category


@pytest.mark.parametrize("category", [None, "", "invoice", "poster", "VOICE_NOTE"])
def test_unknown_image_categories_are_rejected_without_guessing(category):
    """Off-taxonomy model output cannot silently invent an internal category."""
    assert validate_image_category(category) is None


def test_voice_notes_use_one_fixed_category():
    """Voice messages do not need an image-style classifier to identify their modality."""
    assert VOICE_NOTE_CATEGORY == "voice_note"
