"""System-level checks for the decision fusion stage.

Assembles the full P0-P4 pipeline (via run_decision_fusion) over small
synthetic and real batches, and proves the safety-override guarantee
survives end to end.
"""

import os
import subprocess
import sys

import pandas as pd
from ingestion_fakes import FakeASRClient, FakeOCRClient

from router.dataset.timeline import build_user_timelines
from router.decision.message_type import ALLOWED_MESSAGE_TYPES
from router.decision.pipeline import run_decision_fusion
from router.ingestion.pipeline import run_media_ingestion
from router.personalization.pipeline import run_personalization
from router.safety.gate import run_safety_gate


def test_full_p0_to_p4_pipeline_over_a_small_assembled_batch(load_fixture_bundle, fixtures_dir):
    """The assembled P0-P4 pipeline produces one DecisionRecord per message."""
    bundle = load_fixture_bundle("dataset_valid")
    timelines = build_user_timelines(bundle)
    normalized = run_media_ingestion(bundle, fixtures_dir / "dataset_valid", FakeOCRClient(), FakeASRClient())
    verdicts = run_safety_gate(bundle, normalized)
    evidence = run_personalization(normalized, bundle, timelines)

    decisions = run_decision_fusion(bundle, normalized, verdicts, evidence)

    assert set(decisions) == set(bundle.messages["message_id"])
    for record in decisions.values():
        assert record.action in ("notify", "digest", "mute")
        assert record.message_type in ALLOWED_MESSAGE_TYPES
        assert record.reason
        assert 0.0 <= record.confidence <= 1.0


def test_safety_override_holds_through_the_full_assembled_pipeline(load_fixture_bundle, fixtures_dir):
    """A blocked scam message still mutes even with maximally favorable synthetic history."""
    bundle = load_fixture_bundle("dataset_valid")
    scam_row = bundle.messages.iloc[0].copy()
    scam_row.update(
        {
            "message_id": "scam_regression",
            "message_text": "Your account will be blocked in 2 hours. Reply with the OTP now.",
            "media_type": "",
            "media_id": "",
        }
    )
    bundle.messages = pd.concat([bundle.messages, pd.DataFrame([scam_row])], ignore_index=True)
    timelines = build_user_timelines(bundle)
    normalized = run_media_ingestion(bundle, fixtures_dir / "dataset_valid", FakeOCRClient(), FakeASRClient())
    verdicts = run_safety_gate(bundle, normalized)
    evidence = run_personalization(normalized, bundle, timelines)

    decisions = run_decision_fusion(bundle, normalized, verdicts, evidence)

    assert verdicts["scam_regression"].is_blocked is True
    assert decisions["scam_regression"].action == "mute"
    assert decisions["scam_regression"].message_type == "scam"


def test_cli_reports_decision_fusion_summary_for_the_real_dataset(repo_root, tmp_path):
    """A key-less local run reports a decision summary without modifying dataset/output.csv."""
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
    assert "Decision fusion:" in result.stdout
    assert "notify" in result.stdout
    assert "digest" in result.stdout
    assert "mute" in result.stdout
    assert "Sample calibration:" in result.stdout
