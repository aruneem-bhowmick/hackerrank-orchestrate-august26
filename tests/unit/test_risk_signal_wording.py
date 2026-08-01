"""Unit tests that every risk_signals string is specific, not a generic placeholder."""

from fixtures.safety_scam_messages import SCAM_FIXTURES
from fixtures.safety_spam_messages import SPAM_FIXTURES
from router.safety.signals import detect_scam_signals, detect_spam_signals

_GENERIC_PHRASE_DENYLIST = (
    "flagged as suspicious",
    "looks risky",
    "seems off",
    "suspicious activity",
)

_MINIMUM_DETAIL_LENGTH = 15


def _all_scam_detail_strings() -> list[str]:
    details: list[str] = []
    for case in SCAM_FIXTURES:
        matches = detect_scam_signals(case.message_text, case.business, case.verified_brand_names)
        details.extend(signal.detail for signal in matches)
    return details


def _all_spam_detail_strings() -> list[str]:
    details: list[str] = []
    for case in SPAM_FIXTURES:
        matches = detect_spam_signals(
            case.message_text, case.forwarded_count, case.business, case.forward_chain_open_rate
        )
        details.extend(signal.detail for signal in matches)
    return details


def test_no_scam_signal_detail_uses_a_generic_placeholder_phrase():
    """Every scam RiskSignal.detail avoids the generic-phrase denylist."""
    details = _all_scam_detail_strings()
    assert details, "expected at least one scam signal to fire across the fixture set"
    for detail in details:
        lowered = detail.lower()
        for generic_phrase in _GENERIC_PHRASE_DENYLIST:
            assert generic_phrase not in lowered, f"'{detail}' uses a generic placeholder phrase"


def test_no_spam_signal_detail_uses_a_generic_placeholder_phrase():
    """Every spam RiskSignal.detail avoids the generic-phrase denylist."""
    details = _all_spam_detail_strings()
    assert details, "expected at least one spam signal to fire across the fixture set"
    for detail in details:
        lowered = detail.lower()
        for generic_phrase in _GENERIC_PHRASE_DENYLIST:
            assert generic_phrase not in lowered, f"'{detail}' uses a generic placeholder phrase"


def test_every_signal_detail_is_non_empty_and_reasonably_specific():
    """Every detail string clears a minimum length as a cheap specificity proxy."""
    for detail in _all_scam_detail_strings() + _all_spam_detail_strings():
        assert detail
        assert len(detail) >= _MINIMUM_DETAIL_LENGTH, f"'{detail}' looks too generic/short"
