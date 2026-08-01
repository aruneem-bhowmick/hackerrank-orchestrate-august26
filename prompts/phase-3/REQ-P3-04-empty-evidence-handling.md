# REQ-P3-04 — Empty Evidence Handling

## Traceability
- Source requirement: REQ-P3-04 (SPEC.md §2, Phase 3)
- Depends on: REQ-P3-01, REQ-P3-02
- Unblocks: REQ-P3-03

## Objective
Represent a genuine no-match outcome without manufacturing history ids and
provide one serialization helper that renders it as `none`.

## Context & assumptions
- Read `_PREAMBLE.md` first.
- P5 will write the final CSV; this prompt only establishes the safe Evidence
  Bundle representation it consumes.

## Files to create or modify
- `code/router/personalization/evidence.py` — add no-evidence factory and serializer.
- `code/router/personalization/retrieval.py` — return the factory for every no-match path.
- `tests/unit/test_empty_evidence.py` — create.
- `tests/integration/test_retrieval_scope_integration.py` — extend.

## Interfaces & signatures
```python
def no_evidence_bundle(message_id: str, signals: Mapping[str, object]) -> EvidenceBundle:
    """Create the canonical empty-evidence result for a message."""

def evidence_ids_for_output(bundle: EvidenceBundle) -> str:
    """Return comma-separated ids or exactly 'none' when evidence is empty."""
```

## Implementation details
1. Use an empty tuple, `evidence_basis="no relevant historical evidence"`,
   and a deterministic retrieval-method marker internally.
2. Never derive an id from an incoming id, sender, or placeholder text.
3. Preserve the caller's complete personalization-signal mapping even when
   no evidence is retrieved.

## Standards to apply
- Pure deterministic functions, docstrings, and no secret/API use.

## Test suite (exhaustive)
- **Unit:** new sender, source-only irrelevant row, blank query, exact `none` serialization.
- **Integration:** a loaded user's unrelated history returns empty evidence.
- **System:** N/A — batch completeness is REQ-P3-01.
- **Acceptance:** all no-relevant-evidence paths serialize precisely as `none`.
- **Smoke:** factory runs for one incoming id.
- **Sanity:** qualifying evidence remains nonempty and serializes its real id.
- **Regression:** pin no fabricated-id fixtures.
- **End-to-end:** N/A — P5 owns CSV e2e.
- **API:** N/A — no external API interaction.
- **UI:** N/A — no rendered user-facing surface.

## Acceptance criteria (derived from SPEC.md, made executable)
- A user/sender pair with no relevant evidence has empty internal ids and
  public `none`, never a fabricated id.

## Definition of Done
- All empty paths are covered and preserving real qualifying ids is proven.

## Out of scope
Final CSV writing and score fusion.

