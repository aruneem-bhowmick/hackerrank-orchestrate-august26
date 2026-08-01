# REQ-P3-05 — Personalization Signals

## Traceability
- Source requirement: REQ-P3-05 (SPEC.md §2, Phase 3)
- Depends on: REQ-P3-01
- Unblocks: REQ-P3-03, REQ-P3-06

## Objective
Derive all available per-recipient group, quiet-hours, engagement, and
business-relationship facts from the already loaded bundle and surface them
in the Evidence Bundle.

## Context & assumptions
- Read `_PREAMBLE.md` first.
- `group_members`, `users`, `user_business_history`, and the receiver's
  timeline are authoritative; missing relation rows are normal.

## Files to create or modify
- `code/router/personalization/signals.py` — create signal derivation.
- `code/router/personalization/pipeline.py` — add bundle lookups.
- `tests/unit/test_personalization_signals.py` — create.
- `tests/integration/test_personalization_pipeline.py` — create.

## Interfaces & signatures
```python
def build_personalization_signals(
    message: NormalizedMessage, bundle: DatasetBundle,
    timeline: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Return deterministic receiver-specific context and score adjustments."""

def is_quiet_hours(created_at: str, window: str) -> bool:
    """Return whether a local message time falls in an inclusive overnight-safe window."""
```

## Implementation details
1. For group rows, find the exact `(user_id, group_id)` member record and
   expose `group_role` and boolean `group_muted`.
2. Parse `HH:MM-HH:MM`, including windows that cross midnight, against
   `created_at`; malformed/missing windows safely yield false.
3. Filter the supplied user timeline to the most specific source identity
   available (sender, then business, then group) and compute recent
   open/reply/dismiss rates with zero-safe denominators.
4. Look up exact `(user_id, business_id)` and expose relationship, promotion
   permission/opt-out, activity, and historical business engagement fields.
5. Include stable defaults for unavailable fields and initial numeric
   `value_score_adjustment`/`urgency_score_adjustment` values.

## Standards to apply
- Use loaded frames only; do not re-read CSVs.
- Keep every calculation deterministic and document every helper.

## Test suite (exhaustive)
- **Unit:** admin/member, muted/unmuted, normal/overnight quiet windows, each rate, relationship and absent-row defaults.
- **Integration:** full bundle lookup joined with one receiver timeline.
- **System:** N/A — composition is covered by the P3 runner.
- **Acceptance:** each required signal is present when its source data exists.
- **Smoke:** one text message returns a mapping with numeric adjustments.
- **Sanity:** missing optional rows neither crash nor leak another user’s facts.
- **Regression:** fixtures pin midnight and zero-denominator behavior.
- **End-to-end:** N/A — full router belongs to P5.
- **API:** N/A — no external API interaction.
- **UI:** N/A — no rendered user-facing surface.

## Acceptance criteria (derived from SPEC.md, made executable)
- Group role/mute, quiet hours, recent engagement rates, and business
  relationship are derived whenever their matching data is available.

## Definition of Done
- Required context is explicit, safe for missing data, and entirely receiver-scoped.

## Out of scope
Choosing `notify`, `digest`, or `mute`; that is decision fusion work.

