# REQ-P4-03 — Message Type Selection

## Traceability
- Source requirement: REQ-P4-03 (SPEC.md §2, Phase 4)
- Depends on: REQ-P4-01 (`action`, and the safety verdict it was fused from)
- Unblocks: REQ-P4-04 (reason generation references the selected message_type)

## Objective
Deliver the deterministic selector that assigns every message exactly one
`message_type` from the fixed allowed-value list (`personal`, `urgent`,
`event`, `payment`, `business_update`, `promotion`, `greeting`, `forward`,
`spam`, `scam`, `unknown`) — never an invented category, and never a naive
pass-through of P1's internal `risk_type`, which `SPEC.md` ADR-006 already
documents as an intermediate signal rather than a guaranteed final label.

## Context & assumptions
- Read `_PREAMBLE.md` first; inherit the contracts and the safety-override
  contract it carries.
- Assumes REQ-P4-01's `action` (already fused) and the source
  `SafetyVerdict` are available. Also needs, from the loaded
  `DatasetBundle`: the message's own `forwarded_count` (from
  `bundle.messages`, not on `NormalizedMessage`) and the `business_accounts`
  row for the message's `business_id`, if any — reuse
  `router.safety.gate.build_business_index` for this lookup rather than
  writing a second one.
- Grounded in `dataset/sample_messages.csv` (calibration file, 30 rows) and
  `dataset/business_accounts.csv`: `business_098` (referenced by
  `sample_msg_043`) has `verified="0"`, `brand_name="Unknown"` — its
  ground-truth `message_type` is `spam`, muted for reasons P1 cannot see
  (voice message, no recovered transcript, so `risk_type is None`) — a
  purely personalization-driven mute. `business_094` (referenced by
  `sample_msg_015`) has `verified="1"` — its ground-truth `message_type` is
  `promotion` despite spammy-looking copy, per ADR-006's note that a
  verified business's muted promotion is always `promotion`, never `spam`.
  `sample_msg_014` (`forwarded_count=11`, mass-forward chain language) is
  blocked by P1 as `risk_type="spam"` but its ground-truth `message_type` is
  `forward` — this is the documented, expected P1-scope disagreement in
  ADR-006 ("P1's risk_type is an intermediate signal into P4, not a
  guaranteed final message_type"). This prompt's selector must reproduce all
  three outcomes; do not special-case individual sample_msg ids — derive the
  general rules below and let them apply to the dataset broadly.
- The content-classification keyword sets below are a documented,
  dataset-grounded assumption, calibrated further once all four prompts in
  this phase are implemented (per `_PREAMBLE.md`'s ADR-004 note) and
  documented in a new ADR at that point, not just ADR-004 (which is scoped
  to the confidence formula).

## Files to create or modify
- `code/router/decision/message_type.py` — new: `select_message_type` and
  its private content-classification helpers.
- `tests/fixtures/message_type_samples.py` — new: synthetic messages
  covering each allowed value and each override path.
- `tests/unit/test_message_type_selection.py` — new.

## Interfaces & signatures

```python
# code/router/decision/message_type.py
from collections.abc import Mapping

from router.ingestion.message import NormalizedMessage
from router.safety.verdict import SafetyVerdict

ALLOWED_MESSAGE_TYPES: frozenset[str] = frozenset({
    "personal", "urgent", "event", "payment", "business_update",
    "promotion", "greeting", "forward", "spam", "scam", "unknown",
})
"""The fixed allowed-value list from problem_statement.md — never extended
or invented from; see validate_message_type."""


def select_message_type(
    verdict: SafetyVerdict,
    action: str,
    message: NormalizedMessage,
    signals: Mapping[str, object],
    business: Mapping[str, object] | None,
    forwarded_count: int,
) -> str:
    """Deterministically select one member of ALLOWED_MESSAGE_TYPES.

    Priority order: a safety-forced label (is_blocked scam/spam) first, then
    a personalization-driven business-mute label, then content-based
    classification of message.normalized_text. Always returns a member of
    ALLOWED_MESSAGE_TYPES — never raises for well-formed input, and never
    invents a value outside that set.
    """


def validate_message_type(raw: str) -> str:
    """Return raw if it is a member of ALLOWED_MESSAGE_TYPES, else raise
    DecisionFusionError.

    A defense against a future code path returning an off-taxonomy value —
    mirrors router.ingestion.categories.validate_image_category's role for
    P2, adapted to raise rather than fall back, since every message_type
    branch in this module is a fixed literal the module itself controls
    (unlike an external model's free-text category output).
    """
```

## Implementation details
1. Priority-ordered decision, evaluated top to bottom, first match wins:
   a. `verdict.is_blocked and verdict.risk_type == "scam"` → `"scam"`.
   b. `verdict.is_blocked and verdict.risk_type == "spam"`:
      - `forwarded_count >= router.safety.thresholds.FORWARD_CHAIN_COUNT_THRESHOLD`
        (import and reuse this constant; do not redefine it) → `"forward"`.
      - else → `"spam"`.
   c. `action == "mute" and message.conversation_type == "business"`:
      - `business is not None and str(business.get("verified", "")).strip()
        == "0"` → `"spam"`.
      - else → `"promotion"`.
   d. Content-based classification of `message.normalized_text` (case-
      insensitive), in this order — first pattern match wins:
      - **greeting**: blessing/well-wish language with no request for
        action (e.g. "good morning", "stay positive", "keep smiling",
        "no need to respond", "forwarding because it felt nice").
      - **event**: schedule/logistics/appointment language (e.g. "circular",
        "schedule", "timing", "pickup", "form", "cultural night",
        "appointment", "booking", "consent note", "registration").
      - **urgent**: deadline/escalation language (e.g. "asap", "urgent",
        "immediately", "before EOD", "in \d+ min(ute)?s?", "escalat",
        "expire[sd]? today") OR a direct `@user_id` mention
        (`signals`-independent — reuse
        `router.personalization.signals.has_direct_mention`) combined with
        an explicit request-for-response phrase.
      - **payment**: billing/transaction language (e.g. "invoice", "bill",
        "due", "emi", "refund", "amount debited", "amount credited",
        "payment reminder", "subscription renewal") — note this is
        distinct from the safety gate's `payment_or_credential_request`
        signal, which is about credential/OTP requests, not ordinary
        billing notices.
      - **promotion**: discount/offer language (e.g. `\d+% off`, "sale",
        "offer", "promo", "discount", "selling", "shopping offer",
        "unsubscribe", "reply stop").
      - **personal**: default when `message.conversation_type` is
        `personal` or `group` and `signals["source_history_count"] > 0`
        (a known relationship) and none of the above matched.
      - **unknown**: default when `message.conversation_type == "personal"`
        and `signals["source_history_count"] == 0` (first contact, no
        history) and none of the above matched.
      - **business_update**: default when `message.conversation_type ==
        "business"` and none of the above matched (including step c, i.e.
        `action != "mute"`).
      - Final fallback if truly nothing above applies (should not occur for
        `personal`/`group`/`business` conversation types, but keep this as
        an explicit last resort rather than raising): `"personal"`.
   e. Pass the selected value through `validate_message_type` before
      returning — this is a self-check, not a second decision.
2. `validate_message_type` raises `DecisionFusionError` (from
   `router.errors`, added in REQ-P4-01) naming the invalid value — this
   should be unreachable given step 1's exhaustive branches, but exists so
   a future edit to this module fails loudly rather than silently emitting
   an off-taxonomy string, mirroring this project's "never guess" ethos
   (`router.ingestion.categories.validate_image_category`'s sibling rule).
3. Never raise for a well-formed `NormalizedMessage`/`signals`/`business`
   input outside of the `validate_message_type` self-check — a missing
   `business` (None) or empty `normalized_text` are normal conditions
   handled by the branches above, not errors.

## Standards to apply
- Read all API keys/secrets from environment variables only — moot here (no
  external call).
- No AI attribution in code comments or docstrings.
- Deterministic, regex/keyword-based classification; no I/O, no model call.
- Reuse existing named constants (`FORWARD_CHAIN_COUNT_THRESHOLD`,
  `has_direct_mention`) instead of duplicating them.

## Test suite (exhaustive)
- **Unit:** one test per priority-order branch in isolation, each on a
  minimal synthetic `NormalizedMessage`/`signals`/`business`/`verdict`
  fixture: blocked-scam → `"scam"`; blocked-spam with high forwarded_count
  → `"forward"`; blocked-spam with low forwarded_count → `"spam"`;
  mute+business+unverified → `"spam"`; mute+business+verified → `"promotion"`;
  each content-classification keyword bucket (greeting, event, urgent,
  payment, promotion) on representative synthetic text; personal
  vs. unknown default split on `source_history_count`; business_update
  default; `validate_message_type` raises `DecisionFusionError` on a
  synthetic invalid value. Target: `tests/unit/test_message_type_selection.py`.
- **Integration:** N/A beyond REQ-P4-01's fixtures — this module's only
  boundary is the `business_accounts` lookup, already covered by
  `router.safety.gate.build_business_index`'s own tests; no new boundary is
  introduced here.
- **System:** N/A for this prompt alone — covered cumulatively by
  `tests/system/test_p4_pipeline_system.py` once REQ-P4-04 assembles the
  full pipeline.
- **Acceptance:** "message_type MUST be selected from the fixed allowed-
  value list; no invented categories" → `validate_message_type`'s raise
  test plus a property-style test asserting every branch's return value is
  a member of `ALLOWED_MESSAGE_TYPES`.
- **Smoke:** `select_message_type` runs on one synthetic message per
  conversation_type (`personal`, `group`, `business`) without error.
- **Sanity:** a known blocked-scam fixture still returns `"scam"` after
  unrelated changes elsewhere in this module.
- **Regression:** a fixture table reproducing the three grounded dataset
  outcomes named in "Context & assumptions" above (unverified-business
  spam mute, verified-business promotion mute, high-forward spam-blocked
  forward) pinned to their expected `message_type`, so recalibration of the
  content classifier cannot silently break them.
- **End-to-end:** N/A for this prompt — covered by the full-pipeline
  end-to-end prompt in a later phase (P5).
- **API:** N/A — no external API interaction.
- **UI:** N/A — `message_type` is a categorical output field with no
  rendered surface of its own (`SPEC.md` §3); its role in the human-
  readable `reason` string is covered under REQ-P4-04, not here.

Framework: `pytest`. Fixtures: `tests/fixtures/message_type_samples.py`
provides one minimal synthetic case per branch above, built from the same
`NormalizedMessage`/`SafetyVerdict` fixture style as
`tests/fixtures/decision_signals.py`. No externals to mock. Expect at or
near 100% branch coverage on `message_type.py` given the one-test-per-
branch design above.

## Acceptance criteria (derived from SPEC.md, made executable)
- Every return value is a member of `ALLOWED_MESSAGE_TYPES` → proven by the
  property-style test and `validate_message_type`'s raise test.
- A safety-blocked scam message is always labeled `"scam"` → proven by the
  blocked-scam unit test.
- `risk_type` is not blindly copied into `message_type` for a blocked spam
  verdict — content (forward pattern) decides between `"spam"` and
  `"forward"` → proven by the two blocked-spam unit tests and the
  regression fixture.
- A personalization-driven business mute distinguishes `"spam"` from
  `"promotion"` by the business's verification status → proven by the two
  mute+business unit tests and the regression fixture.

## Definition of Done
- All acceptance criteria pass.
- All applicable test types implemented (others marked N/A with reason).
- Every code path returns a member of `ALLOWED_MESSAGE_TYPES`; no path can
  return an off-taxonomy string undetected.
- No change to a shared data contract.

## Out of scope
- Computing `action` (REQ-P4-01) or `confidence` (REQ-P4-02) — this prompt
  consumes `action`, it does not compute it.
- Generating `reason` (REQ-P4-04).
- Final calibration of the keyword lists against the full
  `dataset/messages.csv` batch (110 rows, no ground truth) — this prompt's
  regression fixtures lock behavior against the grounded
  `dataset/sample_messages.csv` cases only; broader tuning, if needed, is
  noted as a follow-up in the ADR this phase adds once implemented.
