"""Named threshold constants the safety gate scores messages against.

Calibrated against dataset/sample_messages.csv and dataset/business_accounts.csv
— see SPEC.md ADR-006 for the full rationale behind each value.
"""

T_SCAM: float = 0.55
"""Minimum combined scam-signal weight for is_blocked=True, risk_type="scam".

dataset/sample_messages.csv's four scam-typed rows each combine at least
two independent signals and land well clear of this threshold under the
weights in signals.py.
"""

T_SPAM: float = 0.55
"""Minimum combined spam-signal weight for is_blocked=True, risk_type="spam".

Calibrated deliberately high: mass-forward "chain" messages in
sample_messages.csv are muted via personalization (message_type
greeting/forward), not the safety gate, so forward-chain language plus a
high forwarded_count alone must stay in the borderline band and only cross
this threshold when corroborated by the low-engagement aggregate signal.
"""
