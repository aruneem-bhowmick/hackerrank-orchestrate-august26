"""Integration coverage for decision serialization and submission validation."""

from ingestion_fakes import FakeASRClient, FakeOCRClient

from router.dataset.timeline import build_user_timelines
from router.decision.pipeline import run_decision_fusion
from router.ingestion.pipeline import run_media_ingestion
from router.output.validation import validate_output_frame
from router.output.writer import build_output_frame, write_output_csv
from router.personalization.pipeline import run_personalization
from router.safety.gate import run_safety_gate


def test_full_decision_mapping_serializes_to_a_valid_submission(load_fixture_bundle, fixtures_dir, tmp_path):
    """REQ-P5-01/03 preserve every P4 public field through the CSV boundary."""
    bundle = load_fixture_bundle("dataset_valid")
    timelines = build_user_timelines(bundle)
    normalized = run_media_ingestion(bundle, fixtures_dir / "dataset_valid", FakeOCRClient(), FakeASRClient())
    verdicts = run_safety_gate(bundle, normalized)
    evidence = run_personalization(normalized, bundle, timelines)
    decisions = run_decision_fusion(bundle, normalized, verdicts, evidence)

    frame = build_output_frame(bundle.messages["message_id"].tolist(), decisions)
    validate_output_frame(bundle.messages, frame)
    path = write_output_csv(frame, tmp_path / "output.csv")

    assert path.exists()
    assert frame["message_id"].tolist() == bundle.messages["message_id"].tolist()
    assert all(frame["evidence_message_ids"].astype(str).str.strip())
    rows_by_id = frame.set_index("message_id")
    for message_id, decision in decisions.items():
        row = rows_by_id.loc[message_id]
        expected_evidence = ";".join(decision.evidence_message_ids) or "none"
        assert row["action"] == decision.action
        assert row["message_type"] == decision.message_type
        assert row["reason"] == decision.reason
        assert row["confidence"] == decision.confidence
        assert row["evidence_message_ids"] == expected_evidence
