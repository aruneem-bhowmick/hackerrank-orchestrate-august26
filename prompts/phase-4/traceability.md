# Traceability Matrix

| Requirement | Prompt | Primary implementation | Primary tests |
| --- | --- | --- | --- |
| REQ-P4-01 | `REQ-P4-01-deterministic-action-fusion.md` | `decision/trace.py`, `decision/fusion.py`, `decision/thresholds.py`, `decision/pipeline.py` | `test_action_fusion.py`, `test_safety_override_fusion_regression.py`, `test_p4_pipeline_system.py` |
| REQ-P4-02 | `REQ-P4-02-confidence-formula.md` | `decision/confidence.py`, `decision/thresholds.py` | `test_confidence_formula.py` |
| REQ-P4-03 | `REQ-P4-03-message-type-selection.md` | `decision/message_type.py` | `test_message_type_selection.py` |
| REQ-P4-04 | `REQ-P4-04-reason-generation.md` | `decision/reason.py`, `decision/pipeline.py`, `main.py` | `test_reason_generation.py`, `test_decision_pipeline_integration.py` |

Every named test is marked with its corresponding requirement id. API tests
are N/A for every row because this stage deliberately makes no external API
call (see the preamble's "no LLM in fusion" assumption); UI tests are N/A
because the deliverable has no rendered surface beyond the `reason` string's
own human-readability, which is covered as an acceptance check rather than a
rendered-surface test.
