"""Integration test: a real DatasetBundle row lands in the borderline band end-to-end."""

from router.dataset.loader import load_dataset_bundle
from router.safety.gate import score_message
from router.safety.thresholds import T_SPAM


def test_real_fixture_row_lands_in_borderline_band(fixtures_dir):
    """dataset_valid's business-promo message is borderline, not blocked or cleared."""
    fixture_dir = fixtures_dir / "dataset_valid"
    bundle = load_dataset_bundle(fixture_dir, repo_root=fixture_dir)

    verdict = score_message(
        bundle.messages[bundle.messages["message_id"] == "msg_test_002"].iloc[0].to_dict(),
        bundle.business_accounts,
        None,
    )

    assert verdict.is_blocked is False
    assert verdict.risk_type == "spam"
    assert 0 < verdict.risk_confidence < T_SPAM
    assert verdict.risk_signals != []
