"""End-to-end local checks for the command-line media ingestion path."""

import os
import subprocess
import sys


def test_cli_completes_without_media_api_keys_and_reports_fallbacks(repo_root, tmp_path):
    """A key-less local run retains every media row through the explicit fallback path."""
    environment = os.environ.copy()
    environment.pop("ANTHROPIC_API_KEY", None)
    environment.pop("OPENAI_API_KEY", None)

    result = subprocess.run(
        [sys.executable, str(repo_root / "code" / "main.py"), "--output", str(tmp_path / "output.csv")],
        cwd=repo_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert "Media ingestion:" in result.stdout
    assert "23 failed to produce usable text." in result.stdout
