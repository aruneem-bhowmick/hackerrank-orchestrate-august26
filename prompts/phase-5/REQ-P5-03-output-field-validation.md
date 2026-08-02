# REQ-P5-03 — Output Field Validation

## Traceability
- Source requirement: REQ-P5-03 (SPEC.md §2, Phase 5)
- Depends on: REQ-P5-01
- Unblocks: REQ-P5-02, REQ-P5-04

## Objective
Add the submission gate that rejects malformed output before disk write. It
must prove required decision values are present, confidence is meaningful, and
the evidence sentinel is intentional rather than a blank or null.

## Context & assumptions
- Read `_PREAMBLE.md` first and use REQ-P5-01's `OUTPUT_COLUMNS`.
- P5 validates P4 values; it must not supply defaults for absent action,
  message type, or confidence.
- Existing `validate_row_count_parity` remains the canonical id/count check;
  this validator composes with it rather than weakening it.

## Files to create or modify
- `code/router/output/validation.py` — create submission-frame validation.
- `code/router/errors.py` — add `OutputValidationError` under `DatasetError`.
- `code/main.py` — modify to validate before writing.
- `tests/unit/test_output_validation.py` — create field/error tests.
- `tests/integration/test_output_pipeline_integration.py` — modify with writer-validator checks.
- `tests/system/test_submission_system.py` — modify with complete-gate checks.

## Interfaces & signatures
```python
import pandas as pd

def validate_output_frame(messages: pd.DataFrame, output: pd.DataFrame) -> None:
    """Raise OutputValidationError unless output is a valid submission frame.

    Checks exact columns/order, one-to-one message-id parity, non-empty action,
    message_type, reason, confidence, and evidence fields, allowed actions,
    finite confidence in [0, 1], and a `none` or semicolon-separated evidence
    representation. Returns None without mutating either frame.
    """
```

## Implementation details
1. Require exact ordered columns before accessing values; produce a concise
   expected-versus-actual error.
2. Reuse `validate_row_count_parity` and convert any parity failure into an
   `OutputValidationError` that preserves the actionable detail.
3. Treat `None`, `NaN`, empty, and whitespace-only required values as invalid.
   For `confidence`, parse defensively, reject booleans/non-finite values, and
   require inclusive `[0, 1]` numeric range.
4. Permit only `notify`, `digest`, or `mute`; validate `message_type` against
   the existing fixed allowed-value set. Require a non-empty reason so P4's
   human explanation cannot disappear in a CSV coercion.
5. Evidence must be exactly `none` or a non-empty semicolon-separated id list with
   no blank segment; reject null, `""`, `"none,"`, and whitespace entries.

## Standards to apply
- Every new function and exception receives a precise docstring.
- Validation is deterministic, pure, and does not silently repair output.
- No secrets, API calls, or changes to action/type selection.

## Test suite (exhaustive)
- **Unit:** parameterize every blank/null/whitespace required field, invalid
  actions/types, confidence boundary/non-numeric/NaN/Infinity cases, bad
  evidence forms, duplicate/missing ids, and exact valid `none`/id-list rows.
- **Integration:** valid writer output passes; mutate one written-frame field
  at a time and assert `OutputValidationError` names the relevant column.
- **System:** full fixture pipeline produces a frame that passes the gate.
- **Acceptance:** each required non-empty clause has a direct failing case;
  `none` passes but blank/null evidence fails.
- **Smoke:** validate a one-row valid frame.
- **Sanity:** parity mismatch still fails through the new gate.
- **Regression:** pin confidence `0.0` and `1.0` as valid numeric endpoints.
- **End-to-end:** final fixture command leaves only a validator-approved CSV.
- **API:** N/A — pure local validation.
- **UI:** N/A — no rendered surface.

Use `pytest`, `tmp_path`, and synthetic rows matching the real schema; tag all
tests `REQ-P5-03` and fully cover branch-specific validation errors.

## Acceptance criteria (derived from SPEC.md, made executable)
- Empty action, type, confidence, or evidence is rejected.
- `none` is accepted only as a non-blank evidence sentinel.
- No invalid output proceeds to CSV writing.

## Definition of Done
- The complete validation gate passes for valid output and rejects every
  listed invalid state without mutating input data.
- Applicable tests pass and untouched test classes are explicitly N/A.

## Out of scope
- Deciding a route, changing sample-reference labels, or documenting the
  runnable command.
