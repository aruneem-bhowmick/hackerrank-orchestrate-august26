# REQ-P5-02 — Sample Calibration

## Traceability
- Source requirement: REQ-P5-02 (SPEC.md §2, Phase 5)
- Depends on: REQ-P5-01, REQ-P5-03
- Unblocks: REQ-P5-04

## Objective
Route the solved sample messages through the same production pipeline and
compute action and message-type agreement rates. The calibration report is an
observable self-check, not a training input or a mechanism for special-casing
individual production rows.

## Context & assumptions
- Read `_PREAMBLE.md` first; the sample file is calibration-only.
- `sample_messages.csv` contains the input columns plus expected `action` and
  `message_type`; context files continue to come from the loaded dataset.
- The same decision modules must score sample and production messages, with
  fake media clients in tests and existing no-key fallback in local runs.

## Files to create or modify
- `code/router/output/calibration.py` — create metrics and sample-bundle helpers.
- `code/main.py` — modify to run and print calibration before final write.
- `README.md` — modify with recorded action/type agreement and explanation.
- `tests/unit/test_calibration.py` — create metric tests.
- `tests/integration/test_calibration_integration.py` — create sample-pipeline tests.
- `tests/system/test_submission_system.py` — modify with calibration reporting check.

## Interfaces & signatures
```python
from collections.abc import Mapping
from dataclasses import dataclass
import pandas as pd
from router.decision.trace import DecisionRecord

@dataclass(frozen=True)
class CalibrationReport:
    """Action and message-type agreement counts and rates for solved examples."""
    total: int
    action_matches: int
    message_type_matches: int
    action_agreement: float
    message_type_agreement: float

def measure_calibration(
    decisions: Mapping[str, DecisionRecord], sample_messages: pd.DataFrame
) -> CalibrationReport:
    """Compare production-style decisions to reference labels without mutation.

    Raises OutputValidationError for empty samples or unequal id sets. Rates
    are matches divided by total and are rounded only for presentation.
    """
```

## Implementation details
1. Provide a small helper that derives a `DatasetBundle` view with `messages`
   replaced by input-only sample columns; remove solved labels before any
   routing function sees records. Never edit the original loaded bundle.
2. Reuse P0→P4 entrypoints for the sample view: timeline, ingestion, safety,
   personalization, and decision fusion. The calibration module owns only
   comparison and report formatting, not decision logic.
3. Enforce exact sample decision/id parity, nonzero total, and independently
   count action and type matches. Return full-precision rates; presentation is
   percentage with one decimal point and numerator/denominator.
4. Print a clearly labeled calibration line before writing production output.
   Update README with the measured keyless-run result, command, dataset date,
   and a concise explanation that it is a sanity check rather than a score.
5. If a current run's rate differs from the documented baseline because live
   OCR/ASR credentials change media transcription, print the actual run value;
   do not fake a fixed percentage. Document the keyless baseline separately.

## Standards to apply
- Add docstrings/type annotations to every new public and helper function.
- Do not use solved labels to influence decision generation or production CSV.
- No external API is introduced; API keys remain environment-only.

## Test suite (exhaustive)
- **Unit:** exact all-match, partial-match, zero-match, independent action/type
  denominators, id mismatch, empty sample, and immutable report assertions.
- **Integration:** replace bundle messages with a small labeled sample view,
  run P0→P4 with fake clients, and verify the report equals direct comparisons.
- **System:** run the real solved sample through the local keyless pipeline;
  assert a report with total equal to sample rows and rates in `[0, 1]`.
- **Acceptance:** prove both action and message-type agreement appear in report
  and README; prove production writer is never passed sample reference labels.
- **Smoke:** one solved synthetic row produces a report.
- **Sanity:** an unchanged all-match fixture reports 100% for both metrics.
- **Regression:** pin a deliberately divergent type with matching action so
  metrics cannot accidentally collapse into one value.
- **End-to-end:** documented command runs calibration then produces production
  output; default locally with no keys.
- **API:** N/A — comparison calls no external API; media calls use existing
  fakes/fallback behavior.
- **UI:** N/A — README text and stdout are documentation, not a UI.

Use `pytest`, fake media clients, and synthetic fixture rows; tag all tests
`REQ-P5-02`, and target full coverage of metric branches.

## Acceptance criteria (derived from SPEC.md, made executable)
- The solved sample is self-validated before production submission.
- README reports action and message-type agreement rates as calibration.
- Solved labels are excluded from production decisions and output rows.

## Definition of Done
- A reproducible report exists for a synthetic and the real solved sample.
- README baseline is backed by a passing local command and tests.
- No calibration path modifies routing logic or production data.

## Out of scope
- Retuning rules to improve a particular sample row, fitting a model, or
  changing the production output schema.
