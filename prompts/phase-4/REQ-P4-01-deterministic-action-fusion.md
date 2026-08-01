# REQ-P4-01 — Deterministic Action Fusion

## Traceability
- Source requirement: REQ-P4-01 (SPEC.md §2, Phase 4)
- Depends on: none (first prompt of this phase; consumes P1/P2/P3 contracts only)
- Unblocks: REQ-P4-02, REQ-P4-03, REQ-P4-04

## Objective
Deliver the deterministic function that turns one message's `SafetyVerdict`
(P1) and `EvidenceBundle.personalization_signals` (P3) into a final `action`
(`notify` | `digest` | `mute`), plus a loggable intermediate `FusionResult`
that later prompts in this phase (confidence, message_type, reason) and any
future debugging/eval pass can read without recomputing anything. This is
the point in the pipeline (SPEC.md §0) where the user-independent safety
gate and the personalized value/urgency score are combined into the first
half of the final routing decision.

## Context & assumptions
- Read `_PREAMBLE.md` first; inherit the Safety Verdict (§1.3), Evidence
  Bundle (§1.4), and Decision Record (§1.5) contracts it carries, and the
  safety-override contract binding this whole phase.
- Assumes P1 (`router.safety.gate.run_safety_gate`), P2
  (`router.ingestion.pipeline.run_media_ingestion`), and P3
  (`router.personalization.pipeline.run_personalization`) already produce
  one `SafetyVerdict`/`NormalizedMessage`/`EvidenceBundle` per message, keyed
  by `message_id`, exactly as wired in `code/main.py` today.
- `EvidenceBundle.personalization_signals["value_score_adjustment"]` and
  `["urgency_score_adjustment"]` are each bounded to `[-1, 1]`
  (`router.personalization.signals.apply_score_adjustments`). This prompt
  treats them as the "personalization score" and "urgency signals" inputs
  REQ-P4-01's text names — no separate content-based urgency detector is
  introduced here; `_PREAMBLE.md`'s "no LLM in fusion" assumption already
  covers why no additional signal source is added.
- Action thresholds (`T_NOTIFY`, `T_DIGEST`) and the borderline-risk penalty
  weight are documented assumptions per `_PREAMBLE.md`'s ADR-004 note; they
  will be calibrated against `dataset/sample_messages.csv` once this and the
  following three prompts are all implemented, and `SPEC.md` ADR-004 updated
  accordingly. Do not hand-tune per-message special cases here — only the
  named constants below.

## Files to create or modify
- `code/router/decision/__init__.py` — new empty package marker.
- `code/router/decision/trace.py` — new: `FusionResult` and `DecisionRecord`
  dataclasses (the latter's other fields are populated by later prompts;
  define its full shape now so downstream prompts do not redefine it).
- `code/router/decision/thresholds.py` — new: `BASE_SCORE`, `T_NOTIFY`,
  `T_DIGEST`, `BORDERLINE_RISK_PENALTY_WEIGHT` documented constants.
- `code/router/decision/fusion.py` — new: `fuse_action`.
- `code/router/decision/pipeline.py` — new: `run_action_fusion` (batch
  entrypoint over this prompt's scope only; extended by REQ-P4-04 into the
  full Decision Record batch runner).
- `code/router/errors.py` — modify: add `DecisionFusionError(DatasetError)`.
- `tests/fixtures/decision_signals.py` — new: shared synthetic
  `SafetyVerdict`/`personalization_signals` fixtures reused by every prompt
  in this phase.
- `tests/unit/test_action_fusion.py` — new.
- `tests/unit/test_decision_trace_contract.py` — new.
- `tests/integration/test_safety_override_fusion_regression.py` — new.
- `tests/system/test_p4_pipeline_system.py` — new (extended by later
  prompts).

## Interfaces & signatures

```python
# code/router/decision/trace.py
from dataclasses import dataclass


@dataclass(frozen=True)
class FusionResult:
    """The loggable intermediate state behind one message's `action`.

    message_id matches the source message. action is "notify", "digest",
    or "mute". value_score/urgency_score are the fused [0, 1] scores after
    applying personalization adjustments and any borderline-risk penalty.
    safety_confidence is SafetyVerdict.risk_confidence carried through
    (0.0 when risk_type is None). decision_basis is an immutable tuple of
    short, named component identifiers this action was built from — never
    empty; at minimum contains a "no_signals" marker when nothing else
    fired.
    """

    message_id: str
    action: str
    value_score: float
    urgency_score: float
    safety_confidence: float
    decision_basis: tuple[str, ...]

    def __post_init__(self) -> None:
        """Normalize decision_basis to the immutable contract representation."""
        object.__setattr__(self, "decision_basis", tuple(self.decision_basis))


@dataclass(frozen=True)
class DecisionRecord:
    """The Decision Record contract from SPEC.md §1.5 (P4's full output).

    action/message_type/reason/confidence/evidence_message_ids are exactly
    what P5 serializes into output.csv for this message_id. The remaining
    fields are loggable intermediate state, never written to output.csv.
    evidence_message_ids is empty when there is no evidence — serializing
    that to the "none" sentinel is P5's job, not this dataclass's.
    """

    message_id: str
    action: str
    message_type: str
    reason: str
    confidence: float
    evidence_message_ids: tuple[str, ...]
    safety_confidence: float
    value_score: float
    urgency_score: float
    signal_agreement: float
    decision_basis: tuple[str, ...]

    def __post_init__(self) -> None:
        """Normalize both tuple fields to this immutable contract's representation."""
        object.__setattr__(self, "evidence_message_ids", tuple(self.evidence_message_ids))
        object.__setattr__(self, "decision_basis", tuple(self.decision_basis))
```

```python
# code/router/decision/fusion.py
from collections.abc import Mapping

from router.decision.trace import FusionResult
from router.safety.verdict import SafetyVerdict


def fuse_action(
    message_id: str, verdict: SafetyVerdict, signals: Mapping[str, object]
) -> FusionResult:
    """Deterministically fuse a safety verdict and personalization signals
    into one FusionResult.

    signals is one EvidenceBundle's personalization_signals mapping (see
    _PREAMBLE.md). Raises nothing for well-formed input; a missing key in
    signals is a programming error in the caller, not a data condition this
    function should mask.
    """
```

```python
# code/router/decision/pipeline.py
from collections.abc import Mapping

from router.decision.trace import FusionResult
from router.personalization.evidence import EvidenceBundle
from router.safety.verdict import SafetyVerdict


def run_action_fusion(
    verdicts: Mapping[str, SafetyVerdict], evidence: Mapping[str, EvidenceBundle]
) -> dict[str, FusionResult]:
    """Fuse every message's verdict and evidence bundle into one FusionResult
    each. Raises DecisionFusionError if verdicts and evidence do not share
    the exact same message_id key set, or if the produced count does not
    match — a missing entry here would otherwise surface only as a
    mysterious gap much later, in the final output.
    """
```

## Implementation details
1. `FusionResult`/`DecisionRecord` in `trace.py` mirror the dataclass style
   used by `SafetyVerdict`/`EvidenceBundle`: `frozen=True`, tuple fields
   normalized in `__post_init__`.
2. `thresholds.py` constants, each with a doc comment stating it is a
   documented pre-calibration assumption per `_PREAMBLE.md`:
   - `BASE_SCORE: float = 0.5` — the neutral starting point before any
     personalization adjustment is applied.
   - `T_NOTIFY: float = 0.62` — fused priority score at/above which
     `action` is `"notify"`.
   - `T_DIGEST: float = 0.35` — fused priority score at/above which
     `action` is `"digest"` (below this, `"mute"`).
   - `BORDERLINE_RISK_PENALTY_WEIGHT: float = 0.5` — multiplies
     `risk_confidence` to compute the penalty applied to both
     `value_score` and `urgency_score` when the verdict is borderline
     (`risk_type` set, `is_blocked=False`).
3. `fuse_action` steps, in order:
   a. `value_score = clamp(BASE_SCORE + signals["value_score_adjustment"], 0, 1)`.
   b. `urgency_score = clamp(BASE_SCORE + signals["urgency_score_adjustment"], 0, 1)`.
   c. If `verdict.risk_type is not None and not verdict.is_blocked` (the
      REQ-P1-06 borderline case): compute
      `penalty = BORDERLINE_RISK_PENALTY_WEIGHT * verdict.risk_confidence`
      and subtract it from both scores (clamp again after). This is what
      makes a borderline risk signal "visibly lower the value/urgency
      score, not just appear decoratively" — the same causal principle
      REQ-P3-03 states for evidence, applied here to safety context.
   d. Build `decision_basis` from named, non-zero/true fields already
      present on `signals` and `verdict` (do not re-derive new heuristics
      here): `"safety_block:scam"`/`"safety_block:spam"` when
      `verdict.is_blocked`; `"borderline_safety_risk:scam"`/`"...spam"` when
      borderline; `"muted_group_mention_override"` when
      `signals["mention_override"]`; `"group_muted_suppressed"` when
      `signals["group_muted"]` and not `signals["mention_override"]`;
      `"quiet_hours_suppressed"` when `signals["quiet_hours"]`;
      `"sender_dismissal_history"` when `signals["dismissal_penalty"] < 0`;
      `"sender_engagement_history"` when `signals["engagement_lift"] > 0`;
      `"evidence_corroboration"` when `signals["evidence_strength"] > 0`.
      If none of these apply, `decision_basis = ("no_signals",)` — never an
      empty tuple (an empty tuple would be indistinguishable from "not yet
      computed" when logged).
   e. If `verdict.is_blocked`: `action = "mute"` unconditionally — this is
      the REQ-P1-04 hard override. `value_score`/`urgency_score` are still
      computed and returned (for logging/eval — REQ-P4-01 requires
      intermediate scores to be loggable even when they did not decide the
      action), never used to pick a different action.
   f. Else: `priority = 0.5 * value_score + 0.5 * urgency_score`; `action =
      "notify"` if `priority >= T_NOTIFY`, else `"digest"` if `priority >=
      T_DIGEST`, else `"mute"`.
   g. Return `FusionResult(message_id, action, value_score, urgency_score,
      verdict.risk_confidence, decision_basis)`.
4. `run_action_fusion` validates `set(verdicts) == set(evidence)` before
   fusing (raise `DecisionFusionError` naming any mismatched ids), calls
   `fuse_action` once per shared message_id, and raises
   `DecisionFusionError` if the output count does not match the input
   count — the same defensive shape as `run_safety_gate`/
   `run_personalization`.
5. Add `DecisionFusionError(DatasetError)` to `router/errors.py` with a
   docstring matching the style of the other phase-specific error classes
   there (e.g. `PersonalizationError`).

## Standards to apply
- Read all API keys/secrets from environment variables only; never write
  one into a file in this repo — moot for this prompt (no external call),
  restated because it is non-negotiable project-wide.
- No AI attribution in code comments or docstrings.
- Deterministic behavior throughout; pure logic, no I/O, fully unit-testable
  without network access.
- No new caching concern here — this stage does no expensive/external call.

## Test suite (exhaustive)
- **Unit:** `fuse_action` — is_blocked=True (scam) forces action="mute"
  regardless of maximally positive signals; is_blocked=True (spam) same;
  borderline risk_type set lowers both scores by the documented penalty and
  is reflected in decision_basis; clean verdict (risk_type=None) with
  neutral signals yields value_score=urgency_score=BASE_SCORE and
  decision_basis=("no_signals",); muted_group + mention_override present
  together yields "muted_group_mention_override" in decision_basis, not
  "group_muted_suppressed"; each threshold boundary (`T_NOTIFY`, `T_DIGEST`)
  exactly at, just above, and just below. Target: `tests/unit/test_action_fusion.py`.
- **Unit:** `FusionResult`/`DecisionRecord` tuple normalization — construct
  with a list for `decision_basis`/`evidence_message_ids` and assert the
  stored value is a tuple. Target: `tests/unit/test_decision_trace_contract.py`.
- **Integration:** `run_action_fusion` given a mocked verdicts+evidence pair
  spanning several synthetic messages, including a mismatched-key-set case
  (raises `DecisionFusionError` naming the offending id(s)). Target:
  `tests/integration/test_safety_override_fusion_regression.py`.
- **System:** N/A for this prompt alone — a dedicated P4 system test exists
  but is populated fully once REQ-P4-04 assembles the complete pipeline;
  this prompt adds a fusion-only smoke case to
  `tests/system/test_p4_pipeline_system.py` and later prompts extend the
  same file rather than duplicating it.
- **Acceptance:** "action is a deterministic function of (safety verdict,
  personalization score, urgency signals)" → calling `fuse_action` twice
  with identical inputs yields identical output (no hidden state/randomness);
  "intermediate scores must be loggable" → `FusionResult` exposes
  `value_score`/`urgency_score`/`safety_confidence`/`decision_basis` as
  plain, serializable fields; "a high safety-gate confidence MUST NOT be
  overridden by personalization signals" (REQ-P1-04, cross-referenced) →
  the is_blocked-forces-mute unit tests above, plus the dedicated
  regression test below.
- **Smoke:** `fuse_action` runs on one synthetic clean message and one
  synthetic blocked-scam message without error.
- **Sanity:** a known-blocked fixture still yields action="mute" after
  unrelated changes elsewhere in this module.
- **Regression:** `tests/integration/test_safety_override_fusion_regression.py`
  pins a blocked verdict + maximally-favorable personalization signals
  (perfect engagement history, no quiet hours, admin role) to action="mute"
  — this must never regress, mirroring `SPEC.md` §4's existing table row for
  REQ-P1-04.
- **End-to-end:** N/A for this prompt — covered by the full-pipeline
  end-to-end prompt in a later phase (P5), not duplicated here.
- **API:** N/A — no external API interaction (see `_PREAMBLE.md`'s no-LLM
  assumption).
- **UI:** N/A — no rendered surface (`SPEC.md` §3 Non-Goals); `FusionResult`
  is an internal, not human-read, structure.

Framework: `pytest`. Fixtures: `tests/fixtures/decision_signals.py` provides
factory functions for a clean/borderline/blocked `SafetyVerdict` and a
neutral/positive/negative `personalization_signals` mapping, reused by every
prompt in this phase rather than redefined per test file. No externals to
mock. Pure-logic modules (`fusion.py`, `trace.py`) are expected at or near
100% line coverage given the module's small size and full branch coverage
from the unit tests above.

## Acceptance criteria (derived from SPEC.md, made executable)
- `action` is computed by a pure function of `(verdict, signals)` with no
  hidden state → proven by the deterministic-repeat unit test.
- `is_blocked=True` always yields `action="mute"`, irrespective of
  `signals` → proven by the override unit tests and the regression test.
- `FusionResult` exposes every documented intermediate field → proven by
  the trace-contract unit test.
- A borderline verdict measurably changes `value_score`/`urgency_score`
  rather than being dropped → proven by the borderline-penalty unit test.

## Definition of Done
- All acceptance criteria pass.
- All applicable test types implemented (others marked N/A with reason).
- Output/interface matches the SPEC.md §1.5 Decision Record contract's
  `FusionResult`-relevant subset exactly.
- No change to a shared data contract beyond the new §1.5 addition already
  made to SPEC.md (see `_PREAMBLE.md`); `DecisionRecord`'s remaining fields
  (`message_type`, `reason`, `confidence`, `signal_agreement`) are defined
  now but populated only by later prompts in this phase.

## Out of scope
- Computing `confidence` (REQ-P4-02), `message_type` (REQ-P4-03), or
  `reason` (REQ-P4-04) — this prompt only produces `action` and the
  intermediate `FusionResult`.
- Wiring `code/main.py` — deferred to REQ-P4-04, once the full Decision
  Record can be assembled end to end.
- Calibrating `T_NOTIFY`/`T_DIGEST`/`BORDERLINE_RISK_PENALTY_WEIGHT` against
  `dataset/sample_messages.csv` — noted as a documented assumption here;
  actual calibration happens once all four prompts in this phase are
  implemented, per `_PREAMBLE.md`'s ADR-004 instruction.
