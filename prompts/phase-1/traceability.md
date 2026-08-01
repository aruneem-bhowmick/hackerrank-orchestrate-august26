# Phase 1 — Requirement → Prompt → Test File Traceability

| Requirement | Prompt | Production files | Test files |
|---|---|---|---|
| REQ-P1-01 | `REQ-P1-01-safety-verdict-contract.md` | `code/router/safety/__init__.py`, `code/router/safety/verdict.py`, `code/router/safety/gate.py` | `tests/unit/test_safety_verdict.py`, `tests/unit/test_safety_gate_signature.py` |
| REQ-P1-02 | `REQ-P1-02-scam-signal-detection.md` | `code/router/safety/thresholds.py`, `code/router/safety/signals.py`, `code/router/safety/gate.py` | `tests/unit/test_scam_signals.py`, `tests/integration/test_scam_gate_integration.py`, `tests/fixtures/safety_scam_messages.py` |
| REQ-P1-03 | `REQ-P1-03-spam-signal-detection.md` | `code/router/safety/thresholds.py`, `code/router/safety/signals.py`, `code/router/safety/gate.py` | `tests/unit/test_spam_signals.py`, `tests/unit/test_forward_chain_engagement.py`, `tests/integration/test_spam_gate_integration.py`, `tests/fixtures/safety_spam_messages.py` |
| REQ-P1-06 | `REQ-P1-06-borderline-passthrough.md` | `code/router/safety/gate.py` (docstring; fix only if a gap is found) | `tests/unit/test_borderline_passthrough.py`, `tests/integration/test_borderline_passthrough_integration.py` |
| REQ-P1-05 | `REQ-P1-05-risk-signal-logging.md` | `code/router/safety/gate.py`, `code/main.py` | `tests/unit/test_risk_signal_wording.py`, `tests/system/test_safety_gate_batch_system.py`, `tests/system/test_p1_pipeline_system.py` |
| REQ-P1-04 | `REQ-P1-04-override-contract.md` | `code/router/safety/gate.py` (docstring; fix only if a gap is found) | `tests/unit/test_safety_override_contract.py`, `tests/integration/test_safety_override_regression.py` |

## Requirement → SPEC.md §4 test-taxonomy row cross-reference

`SPEC.md` §4 pins two Phase-1 rows explicitly; both are satisfied here:

- "REQ-P1-01 | Unit | Same message, two synthetic users with different
  engagement history → identical safety verdict" → satisfied by
  `test_safety_gate_signature.py` (signature excludes user-scoped
  parameters entirely, the strongest form of this guarantee) and
  `test_safety_override_contract.py` (REQ-P1-04's identical-verdict test).
- "REQ-P1-04 | Integration | High-risk message + high-engagement sender
  history → still muted" → satisfied by
  `test_safety_override_regression.py::
  test_high_risk_sample_rows_stay_blocked_regardless_of_engagement_shape`.

## Test-type coverage summary

Every prompt's Test suite section populates all ten taxonomy types
(Unit, Integration, System, Acceptance, Smoke, Sanity, Regression,
End-to-end, API, UI), marking N/A with an explicit reason where a type
does not apply. Notable N/A patterns across this phase:

- **API**: N/A for every REQ-P1-* prompt — ADR-006 chose a rule-based
  scorer with no external OCR/ASR/LLM/embedding call in this phase.
- **UI**: N/A for every REQ-P1-* prompt — no rendered surface exists until
  P5's `output.csv`/`reason` field; REQ-P1-05 checks `risk_signals`
  wording quality as the closest analogue, explicitly framed as a
  formatting/wording check rather than a UI test.
- **End-to-end**: concentrated in REQ-P1-05 (the batch entrypoint and
  `code/main.py` wiring), rather than duplicated across every prompt.
