# REQ-P3-02 — Dual-Signal Evidence Retrieval

## Traceability
- Source requirement: REQ-P3-02 (SPEC.md §2, Phase 3)
- Depends on: REQ-P3-01
- Unblocks: REQ-P3-04, REQ-P3-03

## Objective
Retrieve only historical records that match the incoming sender, business, or
group and also clear a deterministic TF-IDF text-similarity threshold.

## Context & assumptions
- Read `_PREAMBLE.md` first; ADR-003 mandates in-process TF-IDF cosine.
- The query is `NormalizedMessage.normalized_text`; history text is the
  user's historical `message_text`.

## Files to create or modify
- `code/router/personalization/similarity.py` — create tokenizer and scorer.
- `code/router/personalization/retrieval.py` — create candidate/ranking logic.
- `tests/unit/test_tfidf_similarity.py` — create.
- `tests/unit/test_evidence_retrieval.py` — create.
- `tests/integration/test_retrieval_scope_integration.py` — create.

## Interfaces & signatures
```python
def tfidf_cosine_similarity(query: str, documents: Sequence[str]) -> list[float]:
    """Return deterministic per-document cosine scores in [0, 1]."""

def retrieve_evidence(message: NormalizedMessage, timeline: Sequence[Mapping[str, object]]) -> EvidenceBundle:
    """Return source-matched, text-relevant evidence from one user timeline."""
```

## Implementation details
1. Lowercase and tokenize alphanumeric terms with a stable regex; blank query
   or blank document scores zero.
2. Fit document-frequency weights only on the supplied timeline plus query.
3. A candidate source-matches when a nonblank sender, business, or group id
   equals its counterpart. Record the matching basis.
4. Require both source match and `similarity >= MIN_TEXT_SIMILARITY`; rank by
   similarity descending then created_at/message_id deterministically; keep
   a documented small maximum.
5. Put selected ids, score/basis text, and `retrieval_method="source_and_tfidf"`
   in the returned bundle.

## Standards to apply
- No hosted embeddings, model calls, keys, randomness, or cross-user corpus.
- Every public/helper function has an explanatory docstring.

## Test suite (exhaustive)
- **Unit:** punctuation/case normalization, blank query, IDF weighting, source-only rejection, tie order.
- **Integration:** loaded timeline + normalized message crosses the module boundary with synthetic data.
- **System:** N/A — batch orchestration is REQ-P3-01.
- **Acceptance:** same source with zero relevance yields no evidence; same source plus relevance yields ids.
- **Smoke:** one same-sender relevant pair returns without error.
- **Sanity:** unrelated source never outranks a relevant matching source.
- **Regression:** pinned lexical fixtures lock score threshold/tie behavior.
- **End-to-end:** N/A — full router e2e belongs to P5.
- **API:** N/A — deterministic local computation only.
- **UI:** N/A — no rendered user-facing surface.

## Acceptance criteria (derived from SPEC.md, made executable)
- Selected evidence satisfies both identity and text relevance.
- Identity alone is insufficient, and similarity is receiver-scoped.

## Definition of Done
- Tests prove both-signal selection and deterministic rankings; the bundle
  matches the inherited contract.

## Out of scope
No action selection, quiet-hours policy, or external embedding service.

