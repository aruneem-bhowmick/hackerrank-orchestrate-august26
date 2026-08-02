"""Integration coverage for routing solved samples without exposing labels."""

from ingestion_fakes import FakeASRClient, FakeOCRClient
import pytest

from router.dataset.timeline import build_user_timelines
from router.decision.pipeline import run_decision_fusion
from router.ingestion.pipeline import run_media_ingestion
from router.output.calibration import build_sample_bundle, measure_calibration
from router.personalization.pipeline import run_personalization
from router.safety.gate import run_safety_gate


def test_solved_sample_uses_the_production_routing_path(load_fixture_bundle, fixtures_dir):
    """REQ-P5-02 routes label-free sample inputs before comparing solved columns."""
    bundle = load_fixture_bundle("dataset_valid")
    sample_bundle = build_sample_bundle(bundle)
    timelines = build_user_timelines(sample_bundle)
    normalized = run_media_ingestion(
        sample_bundle, fixtures_dir / "dataset_valid", FakeOCRClient(), FakeASRClient()
    )
    verdicts = run_safety_gate(sample_bundle, normalized)
    evidence = run_personalization(normalized, sample_bundle, timelines)
    decisions = run_decision_fusion(sample_bundle, normalized, verdicts, evidence)

    report = measure_calibration(decisions, bundle.sample_messages)
    sample_by_id = bundle.sample_messages.set_index("message_id")
    expected_action_matches = sum(
        decision.action == sample_by_id.loc[message_id, "action"]
        for message_id, decision in decisions.items()
    )
    expected_message_type_matches = sum(
        decision.message_type == sample_by_id.loc[message_id, "message_type"]
        for message_id, decision in decisions.items()
    )

    assert report.total == len(bundle.sample_messages)
    assert set(decisions) == set(bundle.sample_messages["message_id"])
    assert report.action_matches == expected_action_matches
    assert report.message_type_matches == expected_message_type_matches
    assert report.action_agreement == pytest.approx(expected_action_matches / report.total)
    assert report.message_type_agreement == pytest.approx(expected_message_type_matches / report.total)
