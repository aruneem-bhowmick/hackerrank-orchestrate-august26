# Phase 4 — Decision Fusion & Confidence Calibration — Shared Preamble

Read `SPEC.md` in full if this extract is incomplete; it is a convenience,
not a replacement for the canonical specification.

## Role in the pipeline

This stage consumes P1's `SafetyVerdict` (§1.3, one per message, computed
independently of any receiving user), P3's `EvidenceBundle` (§1.4, one per
message, receiver-scoped, carrying `personalization_signals` with numeric
`value_score_adjustment`/`urgency_score_adjustment` plus the named
components they were built from), and P2's `NormalizedMessage` (§1.2, for
`media_category`/`media_failure`/`normalized_text`). It also needs, from the
loaded `DatasetBundle` (§1.0): the message's own `forwarded_count` (present
on `bundle.messages`, not carried on `NormalizedMessage`) and the matching
`business_accounts` row for a message's `business_id` (for its `verified`
flag) — the safety gate already looks this same row up for its own signals
(`router.safety.gate.build_business_index`), so this phase reuses that same
lookup rather than inventing a second one.

Fusion is the point where the "two coupled decisions" framed in `SPEC.md` §0
— the user-independent safety gate and the personalized value/urgency score
— are combined into one final decision, and where that decision earns a
documented, non-opaque confidence number. Its output is the Decision Record
defined in `SPEC.md` §1.5, one per message, which P5 validates and
serializes into `output.csv` (§1.6) unchanged — P4 is the last phase to set
`action`, `message_type`, `reason`, `confidence`, and `evidence_message_ids`.

## Requirements (verbatim from SPEC.md §2)

- **REQ-P4-01**: Final `action` MUST be a deterministic function of
  (safety verdict, personalization score, urgency signals) — not a single
  opaque LLM call with no visible intermediate state. Intermediate scores
  must be loggable for debugging/eval.
- **REQ-P4-02**: `confidence` MUST be computed from a documented formula
  combining: safety-gate certainty, evidence retrieval strength (count +
  relevance of matched evidence), and agreement between independent signals
  (e.g. rule-based heuristic vs. model judgment). Raw LLM-emitted confidence
  numbers with no grounding are not acceptable as the sole source.
- **REQ-P4-03**: `message_type` MUST be selected from the fixed allowed-value
  list in the problem statement; no invented categories.
- **REQ-P4-04**: `reason` MUST reference the specific signal(s) that drove the
  decision (sender history, safety signal, quiet hours, group mute + mention
  override, etc.) in one short human-readable sentence — not a templated
  restatement of the action.

## Contracts inherited from SPEC.md §1

Safety Verdict (§1.3, P1 output):
```
{ message_id, is_blocked: bool, risk_type: str | null, risk_confidence: float,
  risk_signals: tuple[str, ...] }
```
`risk_signals` is immutable; a verdict can have `risk_type` set and
`risk_confidence > 0` while `is_blocked` is `False` — the borderline case.

Normalized Message (§1.2, P2 output):
```
{
  message_id, user_id, conversation_type, group_id, business_id,
  sender_user_id, created_at, media_type,
  normalized_text: str, media_confidence: float, media_failure: bool,
  media_category: str | null, media_failure_reason: str | null,
}
```

Evidence Bundle (§1.4, P3 output):
```
{ message_id, evidence_ids: [str], evidence_basis: str,
  retrieval_method: str, personalization_signals: {...} }
```
`personalization_signals` includes, among others: `group_role`,
`group_muted`, `quiet_hours`, `direct_mention`, `mention_override`,
`open_rate`, `reply_rate`, `dismiss_rate`, `source_history_count`,
`business_relationship`, `allows_promotions`, `promotions_opted_out`,
`business_activity_count`, `value_score_adjustment`,
`urgency_score_adjustment`, and the named components those two adjustments
were built from (`evidence_strength`, `dismissal_penalty`,
`engagement_lift`, `quiet_hours_penalty`, `group_muted_penalty`,
`mention_override_lift`). Both adjustments are bounded to `[-1, 1]`;
`evidence_strength` is bounded to `[0, MAX_EVIDENCE_STRENGTH]` (see
`router.personalization.signals`).

Decision Record (§1.5, this phase's output):
```
{
  message_id, action, message_type, reason, confidence,
  evidence_message_ids: tuple[str, ...],
  safety_confidence: float, value_score: float, urgency_score: float,
  signal_agreement: float, decision_basis: tuple[str, ...],
}
```
`evidence_message_ids` on the Decision Record is `EvidenceBundle.evidence_ids`
carried through unchanged — this phase never edits which historical messages
were retrieved, only how they affect the score. `decision_basis` is an
immutable tuple of short, named component identifiers (e.g.
`"safety_block:scam"`, `"muted_group_mention_override"`,
`"sender_dismissal_history"`) that REQ-P4-04's `reason` string is built
from — never a free-text blob assembled ad hoc at reason-generation time.

## Binding decisions and ADR status

- ADR-003/006/007 (resolved): this phase never re-runs OCR/ASR, never
  re-runs TF-IDF retrieval, and never recomputes a safety verdict — it only
  consumes what P1/P2/P3 already produced.
- **The safety-override contract is binding on every prompt in this phase**:
  per REQ-P1-04, once `SafetyVerdict.is_blocked` is `True`, `action` MUST be
  `"mute"` unconditionally. No personalization signal (engagement history,
  group role, evidence strength) may change that. A borderline verdict
  (`risk_type` set, `is_blocked=False`) is not an override — it is one input
  among several that must visibly affect `value_score`/`urgency_score`
  (mirroring REQ-P3-03's causal-evidence rule, extended here to safety
  context) rather than being silently dropped once it fails to block
  (REQ-P1-06).
- **ADR-004 (resolved in SPEC.md)**: confidence formula weights. The final
  0.5/0.2/0.3 weights and their calibration evidence are recorded there. ADR-009
  records the separate action-threshold, borderline-risk, and content-urgency
  calibration. Keep both records aligned with the runtime constants.
- **Documented assumption (no LLM in fusion)**: consistent with REQ-P4-01's
  "not a single opaque LLM call" language and this project's existing
  rule-based ethos (ADR-006), decision fusion, confidence, message_type
  selection, and reason generation are implemented as deterministic
  functions over already-computed signals — no LLM call is introduced at
  this stage, and REQ-P4-02's "agreement between independent signals"
  parenthetical (which offers "rule-based heuristic vs. model judgment" only
  as an example) is resolved as agreement between the safety gate's
  independent, user-agnostic rule-based verdict and P3's independent,
  receiver-scoped personalization signals — the two coupled decisions
  `SPEC.md` §0 already frames as this system's real architecture. If a
  future phase introduces a model judgment call, update `SPEC.md` first and
  revisit this assumption.

## Non-goals (relevant subset of SPEC.md §3)

- No custom model training or fine-tuning.
- No UI/dashboard; this remains a batch pipeline.
- No hosted LLM/embedding call introduced at this stage (see the documented
  assumption above).

## Prompt order

1. `REQ-P4-01-deterministic-action-fusion.md`
2. `REQ-P4-02-confidence-formula.md`
3. `REQ-P4-03-message-type-selection.md`
4. `REQ-P4-04-reason-generation.md`
