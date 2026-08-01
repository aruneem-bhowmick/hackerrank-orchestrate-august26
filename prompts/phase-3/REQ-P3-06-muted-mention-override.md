# REQ-P3-06 — Muted-Group Mention Override

## Traceability
- Source requirement: REQ-P3-06 (SPEC.md §2, Phase 3)
- Depends on: REQ-P3-05, REQ-P3-03
- Unblocks: later decision fusion

## Objective
Detect an explicit receiver mention in a muted group and emit a transparent
override signal that can lift the group’s baseline muted treatment.

## Context & assumptions
- Read `_PREAMBLE.md` first.
- A direct mention is the literal token `@<user_id>` in normalized text; it
  must not match a longer identifier such as `@u_0100` for user `u_010`.

## Files to create or modify
- `code/router/personalization/signals.py` — add mention detection/override.
- `code/router/personalization/pipeline.py` — apply it after group signals.
- `tests/unit/test_mention_override.py` — create.
- `tests/integration/test_personalization_pipeline.py` — extend.

## Interfaces & signatures
```python
def has_direct_mention(text: str, user_id: str) -> bool:
    """Return whether text contains the exact WhatsApp-style @user_id token."""

def apply_mention_override(signals: dict[str, object]) -> dict[str, object]:
    """Return signals with a muted-group direct-mention urgency lift when applicable."""
```

## Implementation details
1. Use an escaped, boundary-aware case-insensitive regex for the target token.
2. Emit `direct_mention`; when both it and `group_muted` are true, emit
   `mention_override=true`, a named positive urgency component, and a positive
   urgency-score delta that offsets the mute baseline.
3. A mention in an unmuted group is recorded but does not claim a mute override.
4. Never decide the final action here; P4 must consume the signal.

## Standards to apply
- Pure local text logic, deterministic ordering, documented helpers, no APIs.

## Test suite (exhaustive)
- **Unit:** exact token, case, absent target, longer-token false positive, muted/unmuted combinations.
- **Integration:** muted group member plus @mention receives override fields.
- **System:** assembled P3 batch returns override only for the intended user.
- **Acceptance:** muted group plus direct mention has a positive action-raising signal.
- **Smoke:** one muted mentioned message processes without error.
- **Sanity:** nonmentioned muted group retains its baseline penalty.
- **Regression:** pin `@u_010` versus `@u_0100` boundary behavior.
- **End-to-end:** N/A — final action escalation belongs to P4/P5.
- **API:** N/A — no external API interaction.
- **UI:** N/A — no rendered user-facing surface.

## Acceptance criteria (derived from SPEC.md, made executable)
- Exact direct mention plus muted group yields an override available to fusion.
- Similar text and another recipient’s mention do not trigger the override.

## Definition of Done
- The override is exact, receiver-specific, score-visible, and test-covered.

## Out of scope
Final action assignment and reason-string formatting.
