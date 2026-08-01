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

FORWARD_CHAIN_COUNT_THRESHOLD: int = 7
"""forwarded_count at/above this is "high" for spam scoring purposes.

Chosen from the observed distribution in dataset/messages.csv, where
forwarded_count values cluster at 0-3 for ordinary messages and jump to
6-11 for forward-chain content (blessings, chain letters, forwarded
"urgent" broadcasts).
"""

LOW_ENGAGEMENT_OPEN_RATE_CUTOFF: float = 0.30
"""A forward_chain_open_rate at/below this counts as the low-engagement signal.

The real dataset's actual rate (4.8%) sits far below this cutoff, so the
cutoff has headroom.
"""

HIGH_VOLUME_BUSINESS_THRESHOLD: int = 4500
"""messages_sent_30d at/above this counts as very-high-volume broadcasting.

Approximately the 75th percentile of dataset/business_accounts.csv's
messages_sent_30d distribution (observed: 25%=1469, 50%=2469, 75%=4586,
max=5930).
"""
