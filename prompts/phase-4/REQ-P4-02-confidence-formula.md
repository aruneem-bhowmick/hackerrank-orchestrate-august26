# REQ-P4-02 — Confidence Formula

## Traceability
- Source requirement: REQ-P4-02 (SPEC.md §2, Phase 4)
- Depends on: REQ-P4-01 (Safety Verdict + personalization signals inputs;
  does not depend on REQ-P4-01's `FusionResult` output directly — see below)
- Unblocks: REQ-P4-04 (reason generation references confidence's components)

## Objective
Deliver a documented, grounded `confidence` formula combining safety-gate
certainty, evidence retrieval strength, and agreement between the safety
gate and personalization's independent assessments — replacing what would
otherwise be an ungrounded, opaque number with a value every component of
which is nameable and testable in isolation.

## Context & assumptions
- Read `_PREAMBLE.md` first; inherit the Safety Verdict (§1.3) and Evidence
  Bundle (§1.4) contracts, and the "no LLM in fusion" / agreement-definition
  assumption it documents.
- This prompt's functions take the same two inputs as REQ-P4-01's
  `fuse_action` (`SafetyVerdict`, `personalization_signals`) rather than
  `FusionResult` — confidence does not depend on the fused `value_score`/
  `urgency_score`, only on the raw signals, so it can be implemented and
  tested independently of `fusion.py`.
- `signals["evidence_strength"]` is bounded to `[0, MAX_EVIDENCE_STRENGTH]`
  today as an inline `min(0.25, ...)` literal in
  `router.personalization.signals`; this prompt names that bound as a
  module constant (`MAX_EVIDENCE_STRENGTH = 0.25`) in
  `router.personalization.signals` and reuses it here rather than
  duplicating the magic number — this is the one small modification to P3
  code this prompt makes, and it changes no behavior/contract, only names
  an existing bound for reuse.
- The exact weights below are a documented pre-calibration assumption per
  `_PREAMBLE.md`'s ADR-004 note; calibration happens once all four prompts
  in this phase are implemented.

## Files to create or modify
- `code/router/personalization/signals.py` — modify: extract the inline
  `0.25` bound into a named `MAX_EVIDENCE_STRENGTH: float = 0.25` module
  constant, used where `evidence_strength` is computed.
- `code/router/decision/thresholds.py` — modify: add
  `CONFIDENCE_WEIGHT_SAFETY`, `CONFIDENCE_WEIGHT_EVIDENCE`,
  `CONFIDENCE_WEIGHT_AGREEMENT` documented constants.
- `code/router/decision/confidence.py` — new: `compute_signal_agreement`,
  `compute_confidence`.
- `tests/unit/test_confidence_formula.py` — new.

## Interfaces & signatures

```python
# code/router/decision/confidence.py
from collections.abc import Mapping

from router.safety.verdict import SafetyVerdict


def compute_signal_agreement(verdict: SafetyVerdict, signals: Mapping[str, object]) -> float:
    """Return, in [0, 1], whether the safety gate and personalization
    signals point the same direction.

    Returns 1.0 whenever verdict.risk_type is None — the safety gate found
    no risk at all, so there is nothing for personalization to agree or
    disagree with (see _PREAMBLE.md's documented assumption). Otherwise,
    degrades from 1.0 toward 0.0 as personalization's combined
    value/urgency adjustment increasingly favors engagement despite a
    found risk signal (blocked or borderline) — the more personalization
    contradicts the risk signal, the less certain the overall decision is.
    """


def compute_confidence(verdict: SafetyVerdict, signals: Mapping[str, object]) -> float:
    """Return confidence in [0, 1] as a documented weighted sum of safety
    certainty, normalized evidence strength, and signal agreement.

    Never returns a raw, ungrounded number — every summand is independently
    nameable and testable (see the module's three private helpers).
    """
```

## Implementation details
1. Add `MAX_EVIDENCE_STRENGTH: float = 0.25` to
   `router.personalization.signals`, replacing the inline `0.25` in
   `apply_score_adjustments`'s `evidence_strength = min(0.25, ...)` line
   with the named constant. No other behavior changes.
2. Add to `decision/thresholds.py`:
   - `CONFIDENCE_WEIGHT_SAFETY: float = 0.5`
   - `CONFIDENCE_WEIGHT_EVIDENCE: float = 0.2`
   - `CONFIDENCE_WEIGHT_AGREEMENT: float = 0.3`
   (sum to 1.0; each documented as a pre-calibration assumption per
   `_PREAMBLE.md`).
3. `_safety_certainty(verdict) -> float` (private helper in `confidence.py`):
   - `risk_type is None` → `1.0` (fully certain nothing was found).
   - `is_blocked` → `verdict.risk_confidence` directly (a barely-over-
     threshold block is less certain than one built from many corroborating
     signals well above it — this is already what `risk_confidence`
     measures, so no separate rescaling is needed).
   - borderline (`risk_type` set, not blocked) → `1.0 - verdict.risk_confidence`
     (the closer `risk_confidence` sits to the blocking threshold, the less
     certain the "not blocked" default is; the closer to 0, the more it
     resembles a confidently clean message).
4. `compute_signal_agreement`:
   - `risk_type is None` → return `1.0`.
   - Else: `lean = clamp((signals["value_score_adjustment"] +
     signals["urgency_score_adjustment"]) / 2, -1, 1)`. If `lean <= 0`
     (personalization does not favor engagement, i.e. does not contradict
     the risk signal) → return `1.0`. Else → return
     `round(max(0.0, 1.0 - lean), 6)`.
5. `compute_confidence`:
   ```python
   evidence_ratio = clamp(signals["evidence_strength"] / MAX_EVIDENCE_STRENGTH, 0, 1)
   confidence = (
       CONFIDENCE_WEIGHT_SAFETY * _safety_certainty(verdict)
       + CONFIDENCE_WEIGHT_EVIDENCE * evidence_ratio
       + CONFIDENCE_WEIGHT_AGREEMENT * compute_signal_agreement(verdict, signals)
   )
   return round(clamp(confidence, 0.0, 1.0), 6)
   ```
6. Never let a `ZeroDivisionError` or missing-key `KeyError` escape for a
   well-formed `signals` mapping (every key referenced here is always
   present per `build_personalization_signals`'s contract) — do not add
   defensive handling for a condition that cannot occur per that contract
   (matches this project's stated style: no validation for scenarios that
   cannot happen).

## Standards to apply
- Read all API keys/secrets from environment variables only — moot here (no
  external call), restated because it is non-negotiable project-wide.
- No AI attribution in code comments or docstrings.
- Deterministic, pure-function implementation; no I/O.
- Every weight and bound named as a module constant, never an inline magic
  number duplicated across files.

## Test suite (exhaustive)
- **Unit:** `compute_signal_agreement` — risk_type=None → 1.0 regardless of
  signals; borderline/blocked with non-positive personalization lean → 1.0;
  borderline/blocked with maximally positive lean (both adjustments at
  +1.0) → 0.0; a partial-lean case → the exact expected intermediate value.
  `compute_confidence` — clean message with zero evidence → exactly
  `CONFIDENCE_WEIGHT_SAFETY + CONFIDENCE_WEIGHT_AGREEMENT` (since
  evidence_ratio=0 and both other terms are 1.0); clean message with
  `evidence_strength == MAX_EVIDENCE_STRENGTH` → confidence increases by
  exactly `CONFIDENCE_WEIGHT_EVIDENCE` relative to the zero-evidence case;
  blocked scam at `risk_confidence == T_SCAM` (boundary) vs. `risk_confidence
  == 1.0` → the higher-confidence signal yields strictly higher
  `confidence`; output is always within `[0, 1]` across a sweep of
  boundary inputs. Target: `tests/unit/test_confidence_formula.py`.
- **Integration:** N/A beyond what REQ-P4-01's fixtures already cover —
  this module takes the same two inputs as `fuse_action` and introduces no
  new component boundary; a shared-fixture consistency check (same
  verdict/signals fixture produces a stable confidence across repeated
  calls) is included in the unit file above rather than a separate
  integration file.
- **System:** covered by `tests/system/test_p4_pipeline_system.py` once
  REQ-P4-04 assembles the full Decision Record — not duplicated here.
- **Acceptance:** "confidence MUST be computed from a documented formula
  combining safety-gate certainty, evidence retrieval strength, and
  agreement between independent signals" → one test per named component
  proving it moves `confidence` in the expected direction in isolation
  (holding the other two fixed); "raw LLM-emitted confidence numbers with
  no grounding are not acceptable as the sole source" → satisfied by
  construction (no LLM call exists in this module) and asserted via a
  smoke check that `compute_confidence`'s signature takes no model/LLM
  client parameter.
- **Smoke:** `compute_confidence` runs on one synthetic clean message and
  one synthetic blocked message without error, returning a float in
  `[0, 1]`.
- **Sanity:** a known clean/no-evidence fixture's confidence value stays
  fixed after unrelated changes elsewhere in the module.
- **Regression:** a small fixture table (clean+no-evidence, clean+full-
  evidence, borderline+agreeing, borderline+disagreeing, blocked-scam,
  blocked-spam) pinned to their exact computed confidence values, so a
  future weight change is a visible, intentional diff rather than a silent
  drift.
- **End-to-end:** N/A for this prompt — covered by the full-pipeline
  end-to-end prompt in a later phase (P5).
- **API:** N/A — no external API interaction.
- **UI:** N/A — `confidence` is a numeric output field; its
  human-readability is not a rendered-surface concern (`SPEC.md` §3).

Framework: `pytest`. Fixtures: reuses `tests/fixtures/decision_signals.py`
from REQ-P4-01. No externals to mock. Expect at or near 100% line/branch
coverage on `confidence.py` given its small, fully-tested surface.

## Acceptance criteria (derived from SPEC.md, made executable)
- `confidence` is a weighted sum of three independently nameable,
  independently testable components → proven by the per-component
  direction tests.
- Safety-gate certainty scales with `risk_confidence`'s distance from the
  ambiguous middle rather than collapsing to a flat blocked/not-blocked
  value → proven by the boundary-vs-extreme blocked-confidence test.
- Evidence retrieval strength (count + relevance) measurably raises
  confidence → proven by the zero-vs-full evidence test.
- Agreement between the safety gate and personalization measurably lowers
  confidence exactly when they conflict → proven by the agreeing-vs-
  disagreeing borderline test.

## Definition of Done
- All acceptance criteria pass.
- All applicable test types implemented (others marked N/A with reason).
- `confidence` always falls within `[0, 1]`.
- No change to a shared data contract; the one P3 modification (naming
  `MAX_EVIDENCE_STRENGTH`) changes no existing behavior, verified by
  `tests/unit/test_personalization_signals.py` and
  `tests/unit/test_score_adjustments.py`-equivalent tests continuing to
  pass unmodified.

## Out of scope
- Computing `action` (REQ-P4-01), `message_type` (REQ-P4-03), or `reason`
  (REQ-P4-04).
- Calibrating the three confidence weights or `MAX_EVIDENCE_STRENGTH`
  against `dataset/sample_messages.csv` — noted as a documented assumption
  here; actual calibration happens once all four prompts in this phase are
  implemented, per `_PREAMBLE.md`'s ADR-004 instruction.
