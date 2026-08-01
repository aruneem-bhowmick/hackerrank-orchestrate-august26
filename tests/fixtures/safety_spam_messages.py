"""Synthetic spam/benign message cases shared across the safety-gate test suite.

Kept as plain Python (not a CSV) so each case can carry forwarded_count,
an optional business context, and a precomputed forward_chain_open_rate
alongside the message text and expected outcome.
"""

from typing import NamedTuple


class SpamFixtureCase(NamedTuple):
    """One synthetic spam/benign case and its expected outcome."""

    name: str
    message_text: str
    forwarded_count: int
    business: dict | None
    forward_chain_open_rate: float | None
    expected_signal_names: frozenset[str]
    expected_is_blocked: bool


LOW_VOLUME_PROMO_BUSINESS: dict = {
    "business_id": "business_910",
    "display_name": "Corner Cafe",
    "brand_name": "Corner Cafe",
    "category": "food",
    "verified": "0",
    "official_domain": "cornercafe.example",
    "domain_used_by_sender": "cornercafe.example",
    "account_age_days": "800",
    "messages_sent_30d": "200",
    "user_reports_30d": "0",
    "domain_used_by_sender_age_days": "800",
}

HIGH_VOLUME_PROMO_BUSINESS: dict = {
    **LOW_VOLUME_PROMO_BUSINESS,
    "business_id": "business_911",
    "display_name": "Mega Mart",
    "brand_name": "Mega Mart",
    "messages_sent_30d": "5000",
}

VERIFIED_HIGH_VOLUME_PROMO_BUSINESS: dict = {
    **HIGH_VOLUME_PROMO_BUSINESS,
    "business_id": "business_912",
    "display_name": "Thrillophilia",
    "brand_name": "Thrillophilia",
    "verified": "1",
}
"""Modeled on the real dataset's business_092 (Thrillophilia, verified,
messages_sent_30d in the thousands): dataset/sample_messages.csv never
labels a verified business's promotional message message_type "spam" —
verified promotions are muted, if at all, via personalization and labeled
"promotion" instead (e.g. sample_msg_007, sample_msg_015, sample_msg_047).
"""

SPAM_FIXTURES: tuple[SpamFixtureCase, ...] = (
    SpamFixtureCase(
        name="mass_forward_chain_language_alone",
        message_text="Forward this to ten people for blessings. Do not ignore, luck changes when you share.",
        forwarded_count=0,
        business=None,
        forward_chain_open_rate=None,
        expected_signal_names=frozenset({"mass_forward_chain_language"}),
        expected_is_blocked=False,
    ),
    SpamFixtureCase(
        name="high_forwarded_count_alone_no_rate",
        message_text="Just checking in on you today.",
        forwarded_count=8,
        business=None,
        forward_chain_open_rate=None,
        expected_signal_names=frozenset({"high_forwarded_count"}),
        expected_is_blocked=False,
    ),
    SpamFixtureCase(
        name="high_forwarded_count_with_high_engagement_rate_no_low_signal",
        message_text="Just checking in on you today.",
        forwarded_count=8,
        business=None,
        forward_chain_open_rate=0.90,
        expected_signal_names=frozenset({"high_forwarded_count"}),
        expected_is_blocked=False,
    ),
    SpamFixtureCase(
        name="chain_language_plus_high_forward_alone_stays_borderline",
        message_text="URGENT share with everyone before midnight for good luck. Do not break the chain.",
        forwarded_count=10,
        business=None,
        forward_chain_open_rate=None,
        expected_signal_names=frozenset({"mass_forward_chain_language", "high_forwarded_count"}),
        expected_is_blocked=False,
    ),
    SpamFixtureCase(
        name="chain_language_plus_high_forward_plus_low_engagement_blocks",
        message_text="URGENT share with everyone before midnight for good luck. Do not break the chain.",
        forwarded_count=10,
        business=None,
        forward_chain_open_rate=0.048,
        expected_signal_names=frozenset(
            {"mass_forward_chain_language", "high_forwarded_count", "low_forward_chain_engagement"}
        ),
        expected_is_blocked=True,
    ),
    SpamFixtureCase(
        name="unverified_repetitive_promotion_alone_stays_borderline",
        message_text="New here? 50% Off Won't Wait! Get 50% off today with code TRY50.",
        forwarded_count=0,
        business=LOW_VOLUME_PROMO_BUSINESS,
        forward_chain_open_rate=None,
        expected_signal_names=frozenset({"repetitive_business_promotion"}),
        expected_is_blocked=False,
    ),
    SpamFixtureCase(
        name="unverified_repetitive_promotion_plus_high_volume_blocks",
        message_text="New here? 50% Off Won't Wait! Get 50% off today with code TRY50.",
        forwarded_count=0,
        business=HIGH_VOLUME_PROMO_BUSINESS,
        forward_chain_open_rate=None,
        expected_signal_names=frozenset({"repetitive_business_promotion", "high_volume_broadcast"}),
        expected_is_blocked=True,
    ),
    SpamFixtureCase(
        name="unverified_high_volume_broadcast_alone_stays_borderline",
        message_text="Your monthly statement is ready to view.",
        forwarded_count=0,
        business=HIGH_VOLUME_PROMO_BUSINESS,
        forward_chain_open_rate=None,
        expected_signal_names=frozenset({"high_volume_broadcast"}),
        expected_is_blocked=False,
    ),
    SpamFixtureCase(
        name="verified_high_volume_promotion_is_not_flagged_as_spam",
        message_text="New here? 50% Off Won't Wait! Get 50% off today with code TRY50.",
        forwarded_count=0,
        business=VERIFIED_HIGH_VOLUME_PROMO_BUSINESS,
        forward_chain_open_rate=None,
        expected_signal_names=frozenset(),
        expected_is_blocked=False,
    ),
)
