"""Pure text/structural detectors that produce named RiskSignals for the safety gate."""

import re

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
        if not pattern.search(text):
            continue
        if negation_pattern is not None and negation_pattern.search(text):
            continue
        signals.append(RiskSignal(name=name, weight=weight, detail=detail))

    signals.extend(_detect_suspicious_link_or_domain(text, business))

    if business is not None:
        signals.extend(_detect_business_scam_signals(business, verified_brand_names))

    return signals


def _detect_suspicious_link_or_domain(text: str, business: dict | None) -> list[RiskSignal]:
    """Flag a bare domain-like token that doesn't match the business's official domain."""
    tokens = _DOMAIN_TOKEN_PATTERN.findall(text)
    if not tokens:
        return []

    official_domain = (business or {}).get("official_domain", "").strip().lower()
    if official_domain and any(token.lower() == official_domain for token in tokens):
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
