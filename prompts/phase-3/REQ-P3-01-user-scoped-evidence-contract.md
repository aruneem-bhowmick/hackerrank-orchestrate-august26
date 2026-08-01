# REQ-P3-01 — User-Scoped Evidence Contract

## Traceability
- Source requirement: REQ-P3-01 (SPEC.md §2, Phase 3)
- Depends on: none
- Unblocks: REQ-P3-02, REQ-P3-04, REQ-P3-05, REQ-P3-03, REQ-P3-06

## Objective
Define a complete Evidence Bundle and a batch runner whose only history input
for an incoming message is `timelines[normalized.user_id]`.

## Context & assumptions
- Read `_PREAMBLE.md` first; inherit its contracts and ADR-003.
- P0 already builds trusted, time-ordered `UserTimeline`; P2 yields exactly
  one `NormalizedMessage` per incoming row.
- An absent timeline is normal and must behave as an empty timeline.

## Files to create or modify
- `code/router/errors.py` — add `PersonalizationError`.
- `code/router/personalization/__init__.py` — create package.
- `code/router/personalization/evidence.py` — create contract types.
- `code/router/personalization/pipeline.py` — create batch boundary.
- `tests/unit/test_evidence_bundle.py` — create.
- `tests/system/test_personalization_batch_system.py` — create.

## Interfaces & signatures
```python
@dataclass(frozen=True)
class EvidenceBundle:
    """One message's evidence and score-ready personalization signals."""
    message_id: str
    evidence_ids: tuple[str, ...]
    evidence_basis: str
    retrieval_method: str
    personalization_signals: Mapping[str, object]

def run_personalization(
    normalized: Mapping[str, NormalizedMessage], bundle: DatasetBundle,
    timelines: UserTimeline,
) -> dict[str, EvidenceBundle]:
    """Return exactly one receiver-scoped EvidenceBundle per normalized message."""
```

## Implementation details
1. Make `EvidenceBundle` immutable and normalize `evidence_ids` to a tuple.
2. Pass only the selected user's timeline into the per-message retrieval
   function; never pass a flattened all-user timeline.
3. Reject duplicate normalized ids or a cardinality mismatch with
   `PersonalizationError`.
4. Begin with an empty, explicitly named no-evidence bundle; later prompts
   replace it only with qualifying evidence.

## Standards to apply
- Secrets are environment-only; this prompt needs none.
- No AI attribution in comments or docstrings.
- Keep the runner deterministic and pure apart from its supplied data.

## Test suite (exhaustive)
- **Unit:** frozen contract, tuple normalization, missing timeline; `test_evidence_bundle.py`.
- **Integration:** N/A — retrieval composition lands in REQ-P3-02.
- **System:** batch of two users proves ids/count and isolated timelines.
- **Acceptance:** inject a second user's tempting history and assert it cannot enter the result.
- **Smoke:** run one text `NormalizedMessage` with an empty timeline.
- **Sanity:** existing P0/P2 bundle remains accepted unchanged.
- **Regression:** fixture locks a cross-user leakage attempt to no evidence.
- **End-to-end:** N/A — full pipeline belongs to P5.
- **API:** N/A — no external API interaction.
- **UI:** N/A — no rendered user-facing surface.

## Acceptance criteria (derived from SPEC.md, made executable)
- Every retrieval call receives only the receiving user's timeline.
- No other user's historical id can occur in that user's Evidence Bundle.

## Definition of Done
- Acceptance tests pass, the output has one bundle per normalized message,
  and all excluded test types are justified above.

## Out of scope
Similarity ranking, behavior-derived adjustments, and all decision fusion.

