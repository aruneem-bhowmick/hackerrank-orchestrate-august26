"""System checks for the documented batch-submission command."""

import os
import shutil
import subprocess
import sys

import pandas as pd
import pytest

from router.output.validation import validate_output_frame
from router.output.writer import OUTPUT_COLUMNS


@pytest.mark.req("REQ-P5-04")
def test_cli_help_describes_the_documented_path_options(repo_root):
    """REQ-P5-04 exposes discoverable dataset and output path overrides."""
    result = subprocess.run(
        [sys.executable, str(repo_root / "code" / "main.py"), "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "--dataset-dir" in result.stdout
    assert "--output" in result.stdout


@pytest.mark.req("REQ-P5-04")
def test_keyless_command_generates_a_valid_fixture_submission(repo_root, fixtures_dir, tmp_path):
    """REQ-P5-01/02/03/04 run the complete command without live media credentials."""
    dataset_dir = tmp_path / "dataset"
    shutil.copytree(fixtures_dir / "dataset_valid", dataset_dir)
    output_path = tmp_path / "submission.csv"
    environment = os.environ.copy()
    environment.pop("ANTHROPIC_API_KEY", None)
    environment.pop("OPENAI_API_KEY", None)

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "code" / "main.py"),
            "--dataset-dir",
            str(dataset_dir),
            "--output",
            str(output_path),
        ],
        cwd=repo_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert "Sample calibration:" in result.stdout
    assert "Wrote validated submission:" in result.stdout
    output = pd.read_csv(output_path, dtype=str, keep_default_na=False)
    messages = pd.read_csv(dataset_dir / "messages.csv", dtype=str, keep_default_na=False)
    assert tuple(output.columns) == OUTPUT_COLUMNS
    validate_output_frame(messages, output)
