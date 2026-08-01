"""Pure text/structural detectors that produce named RiskSignals for the safety gate."""

import re

from router.safety.thresholds import (
    FORWARD_CHAIN_COUNT_THRESHOLD,
    HIGH_VOLUME_BUSINESS_THRESHOLD,
    LOW_ENGAGEMENT_OPEN_RATE_CUTOFF,
)
from router.safety.verdict import RiskSignal

_DOMAIN_TOKEN_PATTERN = re.compile(
    r"\b[a-z0-9][a-z0-9-]*\.(?:com|in|net|org|co|io|xyz|info|ae)\b", re.IGNORECASE
)

_PAYMENT_REQUEST_NEGATION_PATTERN = re.compile(
    r"no (?:payment or )?otp|otp is not (?:required|needed)|"
    r"no otp (?:is )?required|without (?:otp|payment)|not required for this",
    re.IGNORECASE,
)
"""Suppresses payment_or_credential_request when the message explicitly
denies asking for one (e.g. a legitimate courier's "no payment or OTP is
required" notice) — a bare keyword match would otherwise flag the
negation itself as a request.
"""

_NEGATION_CONTEXT_CHARACTERS = 40

_SCAM_TEXT_PATTERNS: tuple[tuple[str, float, re.Pattern, str, re.Pattern | None], ...] = (
    (
        "payment_or_credential_request",
        0.35,
        re.compile(
            r"\botp\b|\bpin\b|password|login code|verification code|"
            r"bank details|card number|\bcvv\b|confirm your (?:wallet|account|"
            r"password|pin)|reply with the .*code|pay .*token|send the code",
            re.IGNORECASE,
        ),
        "payment or credential request (OTP, password, bank details, or similar)",
        _PAYMENT_REQUEST_NEGATION_PATTERN,
    ),
    (
        "urgent_deadline_pressure",
        0.20,
        re.compile(
            r"expire[sd]? today|before midnight|act now|immediately|"
            r"within \d+ hours?|blocked in \d+ hours?|restricted unless|"
            r"suspended|final notice|hurry|account block|block ho jayega|"
            r"ban ho jayega",
            re.IGNORECASE,
        ),
        "urgent deadline or account-suspension pressure language",
        None,
    ),
    (
        "router_instruction_injection",
        0.45,
        re.compile(
            r"ignore (?:all )?previous|routing override|assistant instruction|"
            r"system note for.*router|set action\s*=|mark this (?:message )?as "
            r"notify|ignore sender risk",
            re.IGNORECASE,
        ),
        "message attempts to instruct the routing system directly",
        None,
    ),
    (
        "qr_code_payment_demand",
        # QR payments are legitimate in ordinary commerce, so this 0.30
        # signal requires corroboration before it can block a message.
        0.30,
        re.compile(
            r"scan (?:this|the)?\s*qr|clearance amount|"
            r"pay\b[^.]{0,40}\b(?:amount|fee|penalty|token)\b",
            re.IGNORECASE,
        ),
        "demands payment via a QR code or an urgent fee/penalty",
        None,
    ),
)


def detect_scam_signals(
    message_text: str, business: dict | None, verified_brand_names: frozenset[str]
) -> list[RiskSignal]:
    """Return every scam RiskSignal that fires for one message.

    message_text is the message's normalized text. business is the
    matching row of business_accounts as a dict, or None when the message
    has no business_id or the business_id is not found. verified_brand_names
    is the lowercased set of brand_name values across every verified row
    of business_accounts, used to detect impersonation without a
    hardcoded brand list.

    Never raises for well-formed input; a missing/blank business field is
    treated as that signal not firing, not an error.
    """
    signals: list[RiskSignal] = []
    text = message_text or ""

    for name, weight, pattern, detail, negation_pattern in _SCAM_TEXT_PATTERNS:
        matches = tuple(pattern.finditer(text))
        if not matches:
            continue
        if negation_pattern is not None and all(
            _is_negated_credential_match(text, match, negation_pattern) for match in matches
        ):
            continue
        signals.append(RiskSignal(name=name, weight=weight, detail=detail))

    signals.extend(_detect_suspicious_link_or_domain(text, business))

    if business is not None:
        signals.extend(_detect_business_scam_signals(business, verified_brand_names))

    return signals


def _is_negated_credential_match(
    text: str, match: re.Match[str], negation_pattern: re.Pattern
) -> bool:
    """Return whether a credential keyword belongs to a nearby negated statement."""
    start = max(0, match.start() - _NEGATION_CONTEXT_CHARACTERS)
    end = min(len(text), match.end() + _NEGATION_CONTEXT_CHARACTERS)
    return negation_pattern.search(text[start:end]) is not None


def _detect_suspicious_link_or_domain(text: str, business: dict | None) -> list[RiskSignal]:
    """Flag a bare domain-like token that doesn't match the business's official domain."""
    tokens = _DOMAIN_TOKEN_PATTERN.findall(text)
    if not tokens:
        return []

    official_domain = (business or {}).get("official_domain", "").strip().lower()
    if official_domain and all(token.lower() == official_domain for token in tokens):
        return []

    if business is not None and official_domain:
        detail = "message contains a link/domain that does not match the business's official domain"
    else:
        detail = "message contains an unfamiliar link/domain"
    return [RiskSignal(name="suspicious_link_or_domain", weight=0.20, detail=detail)]


def _detect_business_scam_signals(
    business: dict, verified_brand_names: frozenset[str]
) -> list[RiskSignal]:
    """Flag unverified/impersonating/newly-registered business sender identity."""
    signals: list[RiskSignal] = []
    verified = business.get("verified", "").strip()
    brand_name = business.get("brand_name", "").strip()
    official_domain = business.get("official_domain", "").strip()
    domain_used = business.get("domain_used_by_sender", "").strip()
    domain_age_raw = business.get("domain_used_by_sender_age_days", "").strip()

    if verified == "0":
        signals.append(
            RiskSignal(
                name="unverified_business_sender",
                weight=0.10,
                detail="sender is an unverified business account",
            )
        )
        if brand_name.lower() in verified_brand_names:
            signals.append(
                RiskSignal(
                    name="brand_impersonation",
                    weight=0.40,
                    detail=(
                        f"business name '{brand_name}' matches a verified brand "
                        "but this account is not verified"
                    ),
                )
            )

    if official_domain and domain_used and official_domain.lower() != domain_used.lower():
        signals.append(
            RiskSignal(
                name="business_domain_mismatch",
                weight=0.25,
                detail=(
                    f"sender domain '{domain_used}' does not match the business's "
                    f"official domain '{official_domain}'"
                ),
            )
        )

    if domain_age_raw.isdigit() and int(domain_age_raw) < 30:
        signals.append(
            RiskSignal(
                name="young_sender_domain",
                weight=0.20,
                detail=f"sender's domain is only {int(domain_age_raw)} day(s) old",
            )
        )

    return signals


_MASS_FORWARD_CHAIN_PATTERN = re.compile(
    r"forward this to|share with \d+ people|share this (?:with|blessing)|"
    r"break the chain|forward to at least|fwd as received|forwarded:|"
    r"forwarded health",
    re.IGNORECASE,
)

_REPETITIVE_PROMOTION_PATTERN = re.compile(
    r"\d+% off|\bsale\b|\boffer\b|\bpromo\b|shopping offer|limited time|"
    r"won'?t wait|hurry, it may",
    re.IGNORECASE,
)


def detect_spam_signals(
    message_text: str,
    forwarded_count: int,
    business: dict | None,
    forward_chain_open_rate: float | None,
) -> list[RiskSignal]:
    """Return every spam RiskSignal that fires for one message.

    message_text is the message's normalized text. forwarded_count is the
    message's forwarded_count field, as an int. business is the matching
    row of business_accounts as a dict, or None. forward_chain_open_rate
    is the precomputed aggregate open rate for historical high-
    forwarded_count messages across the whole user base (see
    compute_forward_chain_open_rate), or None if unavailable.

    low_forward_chain_engagement only fires alongside high_forwarded_count
    — it is a corroborator for an already-high forwarded_count, not
    independent evidence on its own. Never raises for well-formed input.
    """
    signals: list[RiskSignal] = []
    text = message_text or ""
    is_high_forward = forwarded_count >= FORWARD_CHAIN_COUNT_THRESHOLD

    if _MASS_FORWARD_CHAIN_PATTERN.search(text):
        signals.append(
            RiskSignal(
                name="mass_forward_chain_language",
                weight=0.25,
                detail="message uses mass-forward chain-letter language",
            )
        )

    if is_high_forward:
        signals.append(
            RiskSignal(
                name="high_forwarded_count",
                weight=0.15,
                detail=f"forwarded_count is {forwarded_count}, a mass-forward level",
            )
        )
        if (
            forward_chain_open_rate is not None
            and forward_chain_open_rate <= LOW_ENGAGEMENT_OPEN_RATE_CUTOFF
        ):
            signals.append(
                RiskSignal(
                    name="low_forward_chain_engagement",
                    weight=0.20,
                    detail=(
                        "historically, messages forwarded this many times are "
                        f"opened only {forward_chain_open_rate:.0%} of the time "
                        "across the user base"
                    ),
                )
            )

    if business is not None:
        if _REPETITIVE_PROMOTION_PATTERN.search(text):
            signals.append(
                RiskSignal(
                    name="repetitive_business_promotion",
                    weight=0.35,
                    detail="message uses generic repetitive promotional phrasing",
                )
            )
        messages_sent_raw = business.get("messages_sent_30d", "").strip()
        if messages_sent_raw.isdigit() and int(messages_sent_raw) >= HIGH_VOLUME_BUSINESS_THRESHOLD:
            signals.append(
                RiskSignal(
                    name="high_volume_broadcast",
                    weight=0.25,
                    detail=(
                        f"business sends {messages_sent_raw} messages/30d, a "
                        "very high broadcast volume"
                    ),
                )
            )

    return signals
