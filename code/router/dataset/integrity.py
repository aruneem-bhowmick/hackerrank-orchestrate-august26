"""Pre-flight guard the loader runs before opening any dataset file.

This currently is a placeholder that always passes; the real allowlist and
suspicious-filename checks land in a follow-up change. The loader already
calls it unconditionally so wiring it up later needs no change to the
loader itself.
"""

from pathlib import Path


def enforce_dataset_integrity(
    repo_root: Path, dataset_dir: Path, allowlist: frozenset[str]
) -> None:
    """Validate no organizer-only or hidden ground-truth file is discoverable.

    Placeholder implementation: always passes. Replaced by a real scan in
    a follow-up change.
    """
    return None
