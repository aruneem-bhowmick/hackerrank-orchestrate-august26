# Phase 5 — Output Generation & Validation — Shared Preamble

Read `SPEC.md` in full if this extract is incomplete; it is a convenience,
not a replacement for the canonical specification.

## Role in the pipeline

This final stage consumes the complete `DecisionRecord` mapping produced by
P4 and is deliberately forbidden to recompute its action, type, reason,
confidence, or evidence. It turns those records into the submission artifact,
validates that artifact, measures the solved-example calibration result, and
makes the complete batch run reproducible from one documented command.

## Requirements (verbatim from SPEC.md §2)

- **REQ-P5-01**: `output.csv` MUST contain exactly one row per `message_id`
  in `dataset/messages.csv`, in the required column order.
- **REQ-P5-02**: System MUST self-validate against `dataset/sample_messages.csv`
  before final submission — report action/message_type agreement rate in the
  README as a calibration sanity check (not scored directly, but demonstrates
  self-verification).
- **REQ-P5-03**: No row may have empty `action`, `message_type`, or
  `confidence`. `evidence_message_ids` may be `none` but not blank/null.
- **REQ-P5-04**: Full run MUST be reproducible from a documented single
  command per README instructions, reading secrets only from environment
  variables (no hardcoded keys).

## Contracts inherited from SPEC.md §1

Decision Record (§1.5):
```json
{
  message_id, action, message_type, reason, confidence,
  evidence_message_ids: tuple[str, ...],
  safety_confidence: float, value_score: float, urgency_score: float,
  signal_agreement: float, decision_basis: tuple[str, ...],
}
```
`action`, `message_type`, `reason`, `confidence`, and
`evidence_message_ids` are exactly the fields P5 serializes into `output.csv`
(§1.6) for this `message_id` — P4 is the last phase to set their values; P5
only validates and writes them, it does not recompute them.

Output (§1.6):
```csv
message_id, action, message_type, reason, confidence, evidence_message_ids
```

## Binding decisions and non-goals

- P5 preserves input-message order, writes UTF-8 CSV with a header, and uses
  the literal `none` only for an empty evidence tuple. It must not invent an
  evidence id, mutate a decision, or fill a missing decision value.
- The sample CSV is a calibration reference only. Its solved action/type
  columns must never be read while producing `dataset/output.csv`.
- ADR-001/002 remain binding: OCR and ASR secrets are obtained only from the
  environment. A no-key run must use the existing media-fallback behavior,
  never a secret embedded in code, docs, or tests.
- No UI/dashboard, model training, new external service, or post-hoc action
  tuning belongs here.

## Prompt order

1. `REQ-P5-01-output-serialization.md`
2. `REQ-P5-03-output-field-validation.md`
3. `REQ-P5-02-sample-calibration.md`
4. `REQ-P5-04-reproducible-submission-command.md`
