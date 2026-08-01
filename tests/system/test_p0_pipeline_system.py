"""System tests for the assembled dataset load and validation stage."""

import subprocess
import sys
from pathlib import Path

from router.dataset.contract import validate_row_count_parity
from router.dataset.loader import load_dataset_bundle
from router.dataset.timeline import build_user_timelines

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_full_load_stage_sequence_on_fixture_dataset():
    """Load, timeline join, and parity check run in sequence without raising."""
    fixture_dir = FIXTURES_DIR / "dataset_valid"
    bundle = load_dataset_bundle(fixture_dir, repo_root=fixture_dir)
    timelines = build_user_timelines(bundle)
    validate_row_count_parity(bundle.messages, bundle.output_template)

    assert len(bundle.messages) == 2
    assert len(timelines) == 2


def test_cli_exits_zero_and_prints_a_plain_summary_on_the_real_dataset():
    """Running the CLI against the real dataset exits 0 with a readable summary."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "code" / "main.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "message(s) to route" in result.stdout
    assert "user(s)" in result.stdout
    assert "{" not in result.stdout
    assert "DatasetBundle" not in result.stdout
