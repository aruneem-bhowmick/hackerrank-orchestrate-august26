"""The fixed media_category taxonomy for normalized messages, per SPEC.md §1.2/ADR-007."""

IMAGE_CATEGORIES: frozenset[str] = frozenset(
    {
        "poster_promo",
        "screenshot",
        "document_photo",
        "meme",
        "personal_photo",
        "unclassified",
    }
)
"""The fixed coarse taxonomy for media_category on image messages, per
REQ-P2-03's example list plus an "unclassified" catch-all the vision model
may return when no bucket genuinely fits. Never extend this set to match a
model's off-taxonomy output — see validate_image_category."""

VOICE_NOTE_CATEGORY: str = "voice_note"
"""The fixed media_category value for every media_type == "voice" message —
there is only one voice sub-type, unlike images' five, so no classification
call is needed."""


def validate_image_category(raw: str | None) -> str | None:
    """Return raw if it is a member of IMAGE_CATEGORIES, else None.

    Never coerces an unrecognized value into "unclassified" or any other
    member — an off-taxonomy response is treated the same as "no category
    available," per REQ-P2-04's "never silently guess" contract.
    """
    return raw if raw in IMAGE_CATEGORIES else None
