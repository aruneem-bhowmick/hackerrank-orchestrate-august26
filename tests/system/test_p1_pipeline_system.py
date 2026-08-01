"""System tests for the assembled P0 + safety-gate pipeline."""

import subprocess
import sys

from router.dataset.contract import validate_row_count_parity
from router.dataset.loader import load_dataset_bundle
from router.dataset.timeline import build_user_timelines
from router.safety.gate import run_safety_gate


def test_full_load_and_safety_gate_sequence_on_fixture_dataset(fixtures_dir):
    """Load, timeline join, parity check, and safety gate run in sequence without raising."""
    fixture_dir = fixtures_dir / "dataset_valid"
    bundle = load_dataset_bundle(fixture_dir, repo_root=fixture_dir)
    build_user_timelines(bundle)
    validate_row_count_parity(bundle.messages, bundle.output_template)
    verdicts = run_safety_gate(bundle)

    assert len(verdicts) == len(bundle.messages)
    assert set(verdicts) == set(bundle.messages["message_id"])


def test_cli_reports_a_safety_gate_summary_on_the_real_dataset(repo_root):
    """Running the CLI against the real dataset prints the blocked/borderline/clean summary."""
    result = subprocess.run(
        [sys.executable, str(repo_root / "code" / "main.py")],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "Safety gate:" in result.stdout
    assert "blocked" in result.stdout
    assert "borderline" in result.stdout
    assert "clean" in result.stdout
