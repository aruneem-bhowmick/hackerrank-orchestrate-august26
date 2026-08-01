from pathlib import Path

from router.dataset.integrity import (
    DEFAULT_EXCLUDED_DIR_NAMES,
    SUSPICIOUS_NAME_PATTERNS,
    find_disallowed_dataset_files,
    find_suspicious_files,
)
from router.dataset.schema import DATASET_ALLOWLIST

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def test_find_disallowed_dataset_files_returns_empty_for_valid_fixture():
    assert find_disallowed_dataset_files(FIXTURES_DIR / "dataset_valid", DATASET_ALLOWLIST) == []


def test_find_disallowed_dataset_files_returns_the_extra_file():
    fixture_dir = FIXTURES_DIR / "dataset_with_extra_csv"
    disallowed = find_disallowed_dataset_files(fixture_dir, DATASET_ALLOWLIST)
    assert [path.name for path in disallowed] == ["notes.csv"]


def test_find_suspicious_files_returns_empty_when_nothing_matches(tmp_path):
    (tmp_path / "notes.txt").write_text("nothing suspicious here")
    assert find_suspicious_files(tmp_path, tmp_path / "dataset") == []


def test_find_suspicious_files_matches_case_insensitively(tmp_path):
    (tmp_path / "GROUND_TRUTH.csv").write_text("message_id,action\n")
    matches = find_suspicious_files(tmp_path, tmp_path / "dataset")
    assert [path.name for path in matches] == ["GROUND_TRUTH.csv"]


def test_find_suspicious_files_does_not_flag_a_suspicious_directory_name(tmp_path):
    suspicious_dir = tmp_path / "ground_truth_archive"
    suspicious_dir.mkdir()
    (suspicious_dir / "notes.txt").write_text("an ordinary file inside a suspicious directory")
    assert find_suspicious_files(tmp_path, tmp_path / "dataset") == []


def test_find_suspicious_files_excludes_the_dataset_directory_itself(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    (dataset_dir / "ground_truth.csv").write_text("message_id,action\n")
    assert find_suspicious_files(tmp_path, dataset_dir) == []


def test_find_suspicious_files_on_real_fixture_tree():
    fixture_dir = FIXTURES_DIR / "repo_with_ground_truth_file"
    matches = find_suspicious_files(fixture_dir, fixture_dir / "dataset")
    assert [path.name for path in matches] == ["ground_truth_labels.csv"]


def test_suspicious_name_patterns_and_excluded_dirs_are_pinned():
    assert SUSPICIOUS_NAME_PATTERNS == (
        "ground_truth",
        "groundtruth",
        "answer_key",
        "answers",
        "solution",
        "labels",
        "hidden_eval",
        "gold",
    )
    assert DEFAULT_EXCLUDED_DIR_NAMES == frozenset(
        {
            ".git",
            ".zed",
            ".vscode",
            ".specstory",
            ".history",
            ".cursorindexingignore",
            "node_modules",
            "tests",
        }
    )
