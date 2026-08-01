"""Integration test: score_message against a real loaded DatasetBundle row."""

from router.dataset.loader import load_dataset_bundle
from router.safety.gate import score_message


def test_score_message_accepts_a_real_bundle_row_shape(fixtures_dir):
    """A row produced by DataFrame.to_dict("records") is directly usable."""
    fixture_dir = fixtures_dir / "dataset_valid"
    bundle = load_dataset_bundle(fixture_dir, repo_root=fixture_dir)

    for message in bundle.messages.to_dict("records"):
        verdict = score_message(message, bundle.business_accounts, None)
        assert verdict.message_id == message["message_id"]
        assert isinstance(verdict.risk_signals, list)
