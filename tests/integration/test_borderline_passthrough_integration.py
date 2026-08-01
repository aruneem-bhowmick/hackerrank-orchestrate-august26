"""Integration test: a real DatasetBundle row lands in the borderline band end-to-end."""

import pandas as pd

from router.dataset.loader import load_dataset_bundle
from router.safety.gate import score_message
from router.safety.thresholds import T_SPAM

_BUSINESS_ACCOUNTS_COLUMNS = [
    "business_id",
    "display_name",
    "brand_name",
    "category",
    "verified",
    "official_domain",
    "domain_used_by_sender",
    "account_age_days",
    "messages_sent_30d",
    "user_reports_30d",
    "domain_used_by_sender_age_days",
]


def test_real_fixture_row_lands_in_borderline_band(fixtures_dir):
    """A real bundle-loaded message from an unverified business is borderline, not blocked or cleared.

    dataset_valid's own business (business_001) is verified, so its
    promo-language message is clean under the safety gate (promotional
    volume from a verified sender is a personalization concern, not a
    spam signal) — score it against an unverified business shaped like
    the real dataset's spammy accounts instead, to exercise the
    borderline contract with a genuinely load_dataset_bundle-sourced
    message row.
    """
    fixture_dir = fixtures_dir / "dataset_valid"
    bundle = load_dataset_bundle(fixture_dir, repo_root=fixture_dir)
    message = bundle.messages[bundle.messages["message_id"] == "msg_test_002"].iloc[0].to_dict()

    unverified_promo_business = pd.DataFrame(
        [
            {
                "business_id": message["business_id"],
                "display_name": "Discount Desk",
                "brand_name": "Discount Desk",
                "category": "retail",
                "verified": "0",
                "official_domain": "discountdesk.example",
                "domain_used_by_sender": "discountdesk.example",
                "account_age_days": "40",
                "messages_sent_30d": "80",
                "user_reports_30d": "0",
                "domain_used_by_sender_age_days": "40",
            }
        ],
        columns=_BUSINESS_ACCOUNTS_COLUMNS,
    )

    verdict = score_message(message, unverified_promo_business, None)

    assert verdict.is_blocked is False
    assert verdict.risk_type == "spam"
    assert 0 < verdict.risk_confidence < T_SPAM
    assert verdict.risk_signals != []
