"""Pre-flight guard the loader runs before opening any dataset file.

Two independent checks both have to pass: every CSV physically present in
the dataset directory has to be one of the known dataset files, and no file
anywhere else in the repository may carry a name that suggests it is an
organizer-only or hidden ground-truth file. Either kind of violation halts
the run rather than being logged and skipped.
"""

from pathlib import Path

from router.errors import DatasetIntegrityError

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
        # Synthetic fixtures for this guard's own tests intentionally use
        # ground-truth-suggestive names; they are committed test assets,
        # not organizer-dropped files, so they are excluded from the scan.
        "tests",
    }
)


def find_disallowed_dataset_files(dataset_dir: Path, allowlist: frozenset[str]) -> list[Path]:
    """Return every *.csv file directly under dataset_dir not in allowlist."""
    return sorted(
        (path for path in dataset_dir.glob("*.csv") if path.name not in allowlist),
        key=lambda path: path.name,
    )


def find_suspicious_files(repo_root: Path, dataset_dir: Path) -> list[Path]:
    """Return files under repo_root whose stem matches a suspicious ground-truth pattern.

    Excludes dataset_dir's own contents (governed by the allowlist check
    instead) and any directory named in DEFAULT_EXCLUDED_DIR_NAMES, matched
    relative to repo_root so an excluded name appearing above repo_root on
    disk (e.g. because a fixture happens to live under a real "tests/"
    directory) does not unintentionally exclude files inside repo_root.
    """
    matches: list[Path] = []
    for path in repo_root.rglob("*"):
        if path.is_dir():
            continue
        if dataset_dir in path.parents:
            continue
        relative_dir_parts = path.relative_to(repo_root).parent.parts
        if any(part in DEFAULT_EXCLUDED_DIR_NAMES for part in relative_dir_parts):
            continue
        stem = path.stem.lower()
        if any(pattern in stem for pattern in SUSPICIOUS_NAME_PATTERNS):
            matches.append(path)
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
