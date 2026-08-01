"""Pre-flight guard the loader runs before opening any dataset file.

Two independent checks both have to pass: every CSV physically present in
the dataset directory has to be one of the known dataset files, and no file
anywhere else in the repository may carry a name that suggests it is an
organizer-only or hidden ground-truth file. Either kind of violation halts
the run rather than being logged and skipped.
"""

import os
import re
from pathlib import Path

from router.errors import DatasetIntegrityError

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")

SUSPICIOUS_NAME_PATTERNS: tuple[str, ...] = (
    "ground_truth",
    "groundtruth",
    "answer_key",
    "answers",
    "solution",
    "labels",
    "hidden_eval",
    "gold",
)

DEFAULT_EXCLUDED_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".zed",
        ".vscode",
        ".specstory",
        ".history",
        ".cursorindexingignore",
        "node_modules",
    }
)

# Synthetic fixtures for this guard's own tests intentionally use
# ground-truth-suggestive names; they are committed test assets, not
# organizer-dropped files. Excluded by exact relative path rather than by
# bare directory name so a real ground-truth file placed anywhere else
# under "tests/" (or any other directory literally named "tests") is
# still caught.
FIXTURES_EXCLUDED_PATH: Path = Path("tests/fixtures")


def _matches_suspicious_pattern(stem: str) -> bool:
    """Return True if stem contains a SUSPICIOUS_NAME_PATTERNS phrase as whole tokens.

    Tokenizes the stem on non-alphanumeric characters and requires each
    pattern (itself underscore-joined for multi-word phrases) to appear as
    a contiguous run of whole tokens, so a pattern embedded inside an
    unrelated longer word (e.g. "gold" inside "marigold") does not match.
    """
    tokens = [token for token in _TOKEN_SPLIT_RE.split(stem.lower()) if token]
    for pattern in SUSPICIOUS_NAME_PATTERNS:
        pattern_tokens = pattern.split("_")
        window = len(pattern_tokens)
        if any(
            tokens[i : i + window] == pattern_tokens
            for i in range(len(tokens) - window + 1)
        ):
            return True
    return False


def find_disallowed_dataset_files(dataset_dir: Path, allowlist: frozenset[str]) -> list[Path]:
    """Return every *.csv file directly under dataset_dir not in allowlist."""
    return sorted(
        (path for path in dataset_dir.glob("*.csv") if path.name not in allowlist),
        key=lambda path: path.name,
    )


def find_suspicious_files(repo_root: Path, dataset_dir: Path) -> list[Path]:
    """Return files under repo_root whose stem matches a suspicious ground-truth pattern.

    Excludes dataset_dir's own contents (governed by the allowlist check
    instead), this project's own test fixtures at FIXTURES_EXCLUDED_PATH,
    and any directory named in DEFAULT_EXCLUDED_DIR_NAMES. Excluded
    directories are pruned from the walk itself (via os.walk's in-place
    dirnames mutation) rather than filtered out after visiting every file
    beneath them, so large excluded trees like .git/ or node_modules/ are
    never descended into at all.
    """
    matches: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        current_dir = Path(dirpath)
        dirnames[:] = [
            name
            for name in dirnames
            if name not in DEFAULT_EXCLUDED_DIR_NAMES
            and current_dir / name != dataset_dir
            and (current_dir / name).relative_to(repo_root) != FIXTURES_EXCLUDED_PATH
        ]
        for filename in filenames:
            if _matches_suspicious_pattern(Path(filename).stem):
                matches.append(current_dir / filename)
    return sorted(matches, key=lambda path: str(path))


def enforce_dataset_integrity(
    repo_root: Path, dataset_dir: Path, allowlist: frozenset[str]
) -> None:
    """Raise DatasetIntegrityError if any disallowed or suspicious file is discoverable."""
    disallowed = find_disallowed_dataset_files(dataset_dir, allowlist)
    suspicious = find_suspicious_files(repo_root, dataset_dir)

    if disallowed or suspicious:
        offenders = sorted(str(path) for path in (*disallowed, *suspicious))
        raise DatasetIntegrityError(
            "Organizer-only or unexpected file(s) discoverable, refusing to run: "
            + ", ".join(offenders)
        )
