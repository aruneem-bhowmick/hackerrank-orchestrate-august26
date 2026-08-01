# Traceability Matrix

| Requirement | Prompt | Primary implementation | Primary tests |
| --- | --- | --- | --- |
| REQ-P3-01 | `REQ-P3-01-user-scoped-evidence-contract.md` | `personalization/evidence.py`, `pipeline.py` | `test_evidence_bundle.py`, `test_personalization_batch_system.py` |
| REQ-P3-02 | `REQ-P3-02-dual-signal-retrieval.md` | `similarity.py`, `retrieval.py` | `test_tfidf_similarity.py`, `test_evidence_retrieval.py` |
| REQ-P3-03 | `REQ-P3-03-causal-score-adjustments.md` | `signals.py` | `test_score_adjustments.py`, `test_personalization_pipeline.py` |
| REQ-P3-04 | `REQ-P3-04-empty-evidence-handling.md` | `evidence.py`, `retrieval.py` | `test_empty_evidence.py` |
| REQ-P3-05 | `REQ-P3-05-personalization-signals.md` | `signals.py` | `test_personalization_signals.py`, `test_personalization_pipeline.py` |
| REQ-P3-06 | `REQ-P3-06-muted-mention-override.md` | `signals.py` | `test_mention_override.py`, `test_personalization_pipeline.py` |

Every named test is marked with its corresponding requirement id. API tests
are N/A for every row because the stage deliberately makes no external API
call; UI tests are N/A because the deliverable has no rendered surface.
