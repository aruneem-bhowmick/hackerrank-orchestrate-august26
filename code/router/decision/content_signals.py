"""Deterministic content-based signals shared across fusion and message_type selection.

Kept in one module so both consumers read identical urgency language rather
than drifting into two independently-tuned regexes for the same concept.
"""

import re

_URGENT_CONTENT_PATTERN = re.compile(
    r"\basap\b|\burgent\b|immediately|before (?:eod|midnight)|\bescalat\w*|"
    r"expire[sd]? today|within \d+ (?:minutes?|hours?)|in \d+ mins?|"
    r"quick heads-up|retry count crossed",
    re.IGNORECASE,
)

_URGENT_NEGATION_PATTERN = re.compile(
    r"\b(?:nothing|not|no)\s+urgent\b", re.IGNORECASE
)
"""Strips an explicit disclaimer (e.g. "nothing urgent") before matching, so
a message that names urgency only to deny it is not misread as urgent."""


def detect_content_urgency(text: str) -> bool:
    """Return whether text contains explicit urgency/deadline language.

    Applies the negation guard first: a message containing only a denial of
    urgency (no other urgent phrase) is not flagged.
    """
    stripped = _URGENT_NEGATION_PATTERN.sub("", text or "")
    return bool(_URGENT_CONTENT_PATTERN.search(stripped))


__all__ = ["detect_content_urgency"]
