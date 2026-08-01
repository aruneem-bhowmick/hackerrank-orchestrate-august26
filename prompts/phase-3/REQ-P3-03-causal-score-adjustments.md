# REQ-P3-03 — Causal Score Adjustments

## Traceability
- Source requirement: REQ-P3-03 (SPEC.md §2, Phase 3)
- Depends on: REQ-P3-02, REQ-P3-04, REQ-P3-05
- Unblocks: later decision fusion

## Objective
Turn qualifying evidence and source engagement history into transparent value
and urgency adjustments that later fusion must consume, rather than treating
evidence ids as decorative output.

## Context & assumptions
- Read `_PREAMBLE.md` first.
- P4 is not implemented yet; this prompt supplies its stable, inspectable
  inputs and does not choose an action.

## Files to create or modify
- `code/router/personalization/signals.py` — add adjustment formulas.
- `code/router/personalization/retrieval.py` — attach selected-match relevance summary.
- `code/router/personalization/pipeline.py` — merge adjustments into bundle signals.
- `tests/unit/test_score_adjustments.py` — create.
- `tests/integration/test_personalization_pipeline.py` — extend.

## Interfaces & signatures
```python
def score_adjustments(
    *, evidence_count: int, mean_relevance: float, open_rate: float,
    reply_rate: float, dismiss_rate: float, quiet_hours: bool,
) -> tuple[float, float]:
    """Return bounded value and urgency adjustments from named evidence signals."""
```

## Implementation details
1. Use a documented, deterministic bounded formula; store the component
   values (`evidence_strength`, `dismissal_penalty`, `quiet_hours_penalty`)
   alongside final adjustments.
2. Repeated dismissals from a matched source must produce a negative value
   adjustment large enough to be observable and monotonic as dismiss rate
   rises.
3. Relevant opened/replied evidence may raise value; quiet hours lower urgency
   unless a later override prompt applies.
4. Empty evidence has zero evidence strength and may not invent engagement.

## Standards to apply
- Formula constants are named, documented, bounded, and unit-testable.
- No action labels, network calls, or hidden model output.

## Test suite (exhaustive)
- **Unit:** high/low dismissal monotonicity, engagement lift, quiet penalty, bounds, empty evidence.
- **Integration:** retrieved dismissed evidence changes the emitted signal mapping.
- **System:** batch exposes debug-ready numeric fields for every bundle.
- **Acceptance:** repeated dismissals visibly lower value adjustment, not merely ids.
- **Smoke:** one relevant evidence row produces finite adjustments.
- **Sanity:** no-match keeps evidence strength at zero.
- **Regression:** pin known high-dismissal source penalty.
- **End-to-end:** N/A — action fusion/P5 e2e is later work.
- **API:** N/A — no external API interaction.
- **UI:** N/A — no rendered user-facing surface.

## Acceptance criteria (derived from SPEC.md, made executable)
- Evidence-derived dismissals affect a numeric score input P4 can consume.
- The reason for every adjustment is retained in named signal components.

## Definition of Done
- Formula and its causal connection are observable, bounded, and fully tested.

## Out of scope
Final action thresholds and confidence calibration.

