# REQ-P1-03 — Spam Signal Detection

## Traceability
- Source requirement: REQ-P1-03 (SPEC.md §2, Phase 1)
- Depends on: REQ-P1-01, REQ-P1-02
- Unblocks: REQ-P1-06, REQ-P1-05, REQ-P1-04

## Objective
Detect spam patterns — "mass-forward, repetitive promotional content, high
`forwarded_count` with low engagement history across the user base" per the
requirement text — and wire them into `score_message` alongside REQ-P1-02's
scam scoring, so the two categories compete and the dominant one (if any)
sets `risk_type`. Per ADR-006's calibration finding, mass-forward "chain"
messages in this dataset are muted via personalization rather than the
safety gate in the ground-truth examples available — so this detector is
deliberately calibrated to require corroboration (chain language plus low
aggregate engagement, not chain language alone) before it blocks, leaving
single-signal cases to REQ-P1-06's borderline passthrough.

## Context & assumptions
- Read `_PREAMBLE.md` first; inherit ADR-006's calibration finding: historical
  messages with `forwarded_count >= 7` have a 4.8% open rate vs. 67.5%
  overall (computed by joining `message_history.csv` + `message_events.csv`).
- REQ-P1-01 produced the `SafetyVerdict`/`score_message` scaffold.
  REQ-P1-02 produced `code/router/safety/signals.py` (scam detectors),
  `code/router/safety/thresholds.py` (`T_SCAM`, `T_SPAM`), and wired scam
  scoring into `gate.py`'s `score_message`.
- This prompt does not read `DatasetBundle.message_history`/
  `message_events` per-message inside `score_message` — that would risk
  coupling the per-message scorer to receiver-scoped history data (REQ-P1-01
  concern). Instead, the forward-chain open rate is computed **once**,
  system-wide, before scoring any message, and passed into `score_message`
  as the plain float `forward_chain_open_rate` parameter REQ-P1-01 already
  reserved in the signature.

## Files to create or modify
- `code/router/safety/signals.py` — modify: add spam signal detectors.
- `code/router/safety/gate.py` — modify: add
  `compute_forward_chain_open_rate` (the one-time aggregate) and wire spam
  scoring + scam-vs-spam category selection into `score_message`.
- `code/router/safety/thresholds.py` — modify: document the
  `forwarded_count` cutoff and the "low engagement" cutoff as named
  constants (`FORWARD_CHAIN_COUNT_THRESHOLD`,
  `LOW_ENGAGEMENT_OPEN_RATE_CUTOFF`, `HIGH_VOLUME_BUSINESS_THRESHOLD`).
- `tests/fixtures/safety_spam_messages.py` — new: synthetic spam/benign
  message fixtures, mirroring `safety_scam_messages.py`'s shape.
- `tests/unit/test_spam_signals.py` — new.
- `tests/unit/test_forward_chain_engagement.py` — new.
- `tests/integration/test_spam_gate_integration.py` — new.

## Interfaces & signatures

```python
# code/router/safety/thresholds.py additions

FORWARD_CHAIN_COUNT_THRESHOLD: int = 7
"""forwarded_count at/above this is "high" for spam scoring purposes.

Chosen from the observed distribution in dataset/messages.csv, where
forwarded_count values cluster at 0-3 for ordinary messages and jump to
6-11 for forward-chain content (blessings, chain letters, forwarded
"urgent" broadcasts) — see ADR-006.
"""

LOW_ENGAGEMENT_OPEN_RATE_CUTOFF: float = 0.30
"""A forward_chain_open_rate at/below this counts as the low-engagement signal.

The real dataset's actual rate (4.8%) sits far below this cutoff, so the
cutoff has headroom; see ADR-006.
"""

HIGH_VOLUME_BUSINESS_THRESHOLD: int = 4500
"""messages_sent_30d at/above this counts as very-high-volume broadcasting.

Approximately the 75th percentile of dataset/business_accounts.csv's
messages_sent_30d distribution (observed: 25%=1469, 50%=2469, 75%=4586,
max=5930).
"""
```

```python
# code/router/safety/gate.py additions

def compute_forward_chain_open_rate(
    message_history: pd.DataFrame, message_events: pd.DataFrame
) -> float | None:
    """Aggregate historical open rate for high-forwarded_count messages.

    Joins message_history and message_events on message_id (inner join —
    rows without a matching event are excluded from the rate, they don't
    contribute a known open/not-open outcome), filters to
    forwarded_count >= FORWARD_CHAIN_COUNT_THRESHOLD, and returns the mean
    of message_opened == "1" among those rows. Returns None if no rows
    meet the forwarded_count filter (undefined rate, not zero — the caller
    must treat None as "signal unavailable", not "zero engagement").
    This is user-independent: it aggregates across every user and sender
    in the historical data, not any one receiving user's own history.
    Called once per run, not once per message.
    """
```

```python
# code/router/safety/signals.py addition

def detect_spam_signals(
    message_text: str,
    forwarded_count: int,
    business: dict | None,
    forward_chain_open_rate: float | None,
) -> list[RiskSignal]:
    """Return every spam RiskSignal that fires for one message.

    Detectors:

    - mass_forward_chain_language (weight 0.25): message_text matches a
      chain-forward pattern (e.g. "forward this to", "share with N
      people", "don't break the chain", generic "good morning"/blessing
      broadcast phrasing combined with an explicit forward request).
    - high_forwarded_count (weight 0.15): forwarded_count >=
      FORWARD_CHAIN_COUNT_THRESHOLD.
    - low_forward_chain_engagement (weight 0.20): forward_chain_open_rate
      is not None, forwarded_count >= FORWARD_CHAIN_COUNT_THRESHOLD, and
      forward_chain_open_rate <= LOW_ENGAGEMENT_OPEN_RATE_CUTOFF. This
      signal only fires alongside high_forwarded_count (it is a
      corroborator, not independent evidence for a message with a low
      forwarded_count).
    - repetitive_business_promotion (weight 0.35): business is not None
      and message_text matches generic promotional phrasing (e.g. "% off",
      "offer", " sale", "reminder: your account has").
    - high_volume_broadcast (weight 0.25): business is not None and
      int(business["messages_sent_30d"]) >= HIGH_VOLUME_BUSINESS_THRESHOLD.

    Returns an empty list if nothing fires. Never raises for well-formed
    input.
    """
```

## Implementation details
1. Implement `compute_forward_chain_open_rate` in `gate.py` (it needs
   `message_history`/`message_events`, which `score_message` itself must
   never see — keeping the aggregate computation in a separate function
   with its own explicit signature makes that boundary visible in code,
   not just in a comment).
2. Implement `detect_spam_signals` in `signals.py` following the pattern
   established by `detect_scam_signals` (pattern/weight table for text
   detectors, direct field reads for business-scoped detectors).
   `low_forward_chain_engagement` must check `forwarded_count >=
   FORWARD_CHAIN_COUNT_THRESHOLD` itself (not assume the caller only calls
   it when true) so the function is correct when unit-tested in isolation.
3. In `gate.py`'s `score_message`: compute `scam_matches =
   detect_scam_signals(...)`, `spam_matches = detect_spam_signals(...)`
   (passing `int(message["forwarded_count"])`, defaulting to `0` if blank
   — mirror the `dtype=str, keep_default_na=False` loading convention from
   `code/router/dataset/loader.py`, so blank means empty string, and this
   function is responsible for its own `int(...)` conversion with a blank
   guard). Compute `scam_confidence = min(1.0, sum(s.weight for s in
   scam_matches))` and `spam_confidence = min(1.0, sum(s.weight for s in
   spam_matches))`.
4. Category selection: if both are `0`, `risk_type=None`. Otherwise pick
   whichever of `scam_confidence`/`spam_confidence` is strictly greater;
   on an exact tie, prefer `"scam"` (document why: scam is the more
   safety-critical category per `SPEC.md` §0's framing of risk, so a tie
   should not silently prefer the less severe label). `risk_confidence` is
   the winning category's confidence; `risk_signals` is that category's
   matched `.detail` strings only (not the union of both, so REQ-P1-05's
   "name which signal fired" stays specific to the reported category).
   `is_blocked = risk_confidence >= (T_SCAM if risk_type == "scam" else
   T_SPAM)`.
5. `compute_forward_chain_open_rate` is called once by REQ-P1-05's batch
   entrypoint (added in that prompt) and threaded into every
   `score_message` call for that run — this prompt only needs to make
   `score_message` correctly *use* the value it's given; do not call
   `compute_forward_chain_open_rate` from inside `score_message` itself
   (that would silently reintroduce a `DatasetBundle`-wide dependency into
   a function meant to take a single precomputed float).

## Standards to apply
- Read all API keys/secrets from environment variables only; never write
  one into a file in this repo. N/A — no external API in this prompt.
- No AI attribution in code comments or docstrings.
- Deterministic, no I/O in `detect_spam_signals`/`score_message`;
  `compute_forward_chain_open_rate` is the one place in this phase that
  touches the wider bundle, and it does so once, not per-message.

## Test suite (exhaustive)
- **Unit:** `tests/unit/test_spam_signals.py` — one test per detector
  (chain language alone, high forwarded_count alone, low engagement only
  fires combined with high forwarded_count and not otherwise, repetitive
  promotion alone, high-volume broadcast alone); a case with
  `business=None` confirms business-scoped detectors no-op.
  `tests/unit/test_forward_chain_engagement.py` — synthetic
  `message_history`/`message_events` fixtures: normal case (mixed
  forwarded_count, computes correct mean), no rows meet the threshold
  (returns `None`, not `0.0` or `NaN`), all matching rows opened (rate
  `1.0`), none opened (rate `0.0`).
- **Integration:** `tests/integration/test_spam_gate_integration.py` —
  `score_message` invoked with real-shaped `business_accounts` rows and a
  precomputed `forward_chain_open_rate` matching the real dataset's
  observed ~0.048, confirming a chain-language + high-forwarded_count
  message combined with that low rate reaches `is_blocked=True`, while the
  same message with `forward_chain_open_rate=None` (or a high rate) stays
  below `T_SPAM`.
- **System:** scam-vs-spam category selection exercised over a batch
  including a message that fires both a (weak) scam signal and a
  (stronger) spam signal, confirming the higher-weighted category wins and
  the loser's signals are absent from `risk_signals` —
  `tests/integration/test_spam_gate_integration.py::test_category_selection_picks_dominant_type`.
- **Acceptance:** "mass-forward, repetitive promotional content, high
  forwarded_count with low engagement history across the user base" → one
  test per clause: mass-forward language contributing to spam confidence;
  repetitive promotional content contributing; the exact
  high-forwarded-count-plus-low-aggregate-engagement combination reaching
  `is_blocked=True` with `risk_type="spam"`.
- **Smoke:** `detect_spam_signals` runs on one synthetic chain-forward
  message without error.
- **Sanity:** a message transcribed from a real high-forward chain-style
  row in `dataset/messages.csv` (e.g. `msg_038`'s "URGENT share with
  everyone before midnight... Do not break the chain", `forwarded_count`
  10), scored with the real computed `forward_chain_open_rate` (~0.048),
  still lands at `is_blocked=True, risk_type="spam"` after this prompt.
- **Regression:** `tests/fixtures/safety_spam_messages.py` fixes a named
  set of spam/benign texts and expected matched signal names, referenced
  again by REQ-P1-04.
- **End-to-end:** N/A for this prompt — covered by REQ-P1-05's batch
  entrypoint test.
- **API:** N/A — no external API interaction.
- **UI:** N/A — no rendered surface; see SPEC.md §3 Non-Goals.

Framework: `pytest`. Fixtures: new `tests/fixtures/safety_spam_messages.py`
plus small inline `message_history`/`message_events` DataFrames built in
`test_forward_chain_engagement.py` (not full CSV fixtures — a handful of
rows is enough to exercise the aggregation logic). No externals to mock.
Coverage expectation: 100% line coverage on `signals.py`'s spam detectors
and `gate.py`'s `compute_forward_chain_open_rate` plus category-selection
branch.

## Acceptance criteria (derived from SPEC.md, made executable)
- Mass-forward chain language is detected → `test_spam_signals.py::
  test_mass_forward_chain_language_detected`.
- Repetitive promotional content is detected → `test_spam_signals.py::
  test_repetitive_business_promotion_detected`.
- High `forwarded_count` combined with low aggregate engagement reaches
  `mute`/`spam` territory (`is_blocked=True, risk_type="spam"`) →
  `test_spam_gate_integration.py::
  test_high_forward_count_with_low_engagement_blocks`.
- A high `forwarded_count` alone (no low-engagement corroboration, no
  chain language) does *not* reach `is_blocked=True` — it is left for
  REQ-P1-06's borderline passthrough → `test_spam_gate_integration.py::
  test_high_forward_count_alone_stays_borderline`.

## Definition of Done
- All acceptance criteria pass.
- All applicable test types implemented (others marked N/A with reason).
- `score_message`'s output still matches SPEC.md §1.3 exactly; category
  selection never sets `risk_type` to anything outside `{"scam", "spam",
  None}`.
- `forward_chain_open_rate` is computed exactly once per run by the
  caller, never inside `score_message`.

## Out of scope
- The borderline-band contract tests specifically (REQ-P1-06 — though this
  prompt's `test_high_forward_count_alone_stays_borderline` already proves
  the underlying behavior works; REQ-P1-06 documents and further tests the
  contract as a first-class requirement rather than a side effect).
- The batch entrypoint that calls `compute_forward_chain_open_rate` once
  and threads it through every message (REQ-P1-05).
- Wiring into `code/main.py`.
