# REQ-P5-01 — Output Serialization

## Traceability
- Source requirement: REQ-P5-01 (SPEC.md §2, Phase 5)
- Depends on: none; consumes the completed P4 Decision Record contract
- Unblocks: REQ-P5-03, REQ-P5-02, REQ-P5-04

## Objective
Create the deterministic writer that converts exactly one complete Decision
Record per incoming message into the required submission CSV. The writer is
the only point that converts an empty evidence tuple to the `none` sentinel;
it preserves the source message order and never re-decides routing fields.

## Context & assumptions
- Read `_PREAMBLE.md` first; inherit the exact P4 and output contracts.
- P4 has already returned a mapping keyed by every `messages.csv.message_id`.
- The existing blank output template is a shape reference, not a source of
  predictions; output order comes from `bundle.messages`.

## Files to create or modify
- `code/router/output/__init__.py` — create package marker.
- `code/router/output/writer.py` — create ordered frame/CSV serialization.
- `code/main.py` — modify only to call the writer after decision fusion.
- `tests/unit/test_output_writer.py` — create writer tests.
- `tests/integration/test_output_pipeline_integration.py` — create pipeline-boundary tests.
- `tests/system/test_submission_system.py` — create final artifact system checks.

## Interfaces & signatures
```python
from collections.abc import Mapping, Sequence
from pathlib import Path
import pandas as pd
from router.decision.trace import DecisionRecord

OUTPUT_COLUMNS: tuple[str, ...]

def build_output_frame(
    message_ids: Sequence[str], decisions: Mapping[str, DecisionRecord]
) -> pd.DataFrame:
    """Return one ordered submission row per message id without writing I/O.

    The returned frame has exactly OUTPUT_COLUMNS. Empty evidence ids become
    the string "none"; non-empty ids are joined deterministically with semicolons.
    Raises OutputValidationError when identifiers cannot form a one-to-one
    mapping, leaving semantic field validation to validate_output_frame.
    """

def write_output_csv(frame: pd.DataFrame, path: str | Path) -> Path:
    """Write an already validated submission frame as UTF-8 CSV and return path."""
```

## Implementation details
1. Define `OUTPUT_COLUMNS` in the exact contract order and derive every row
   only from a `DecisionRecord` plus its source `message_id`.
2. Reject duplicate source ids, missing decisions, extra decision ids, and a
   mapping key that differs from `DecisionRecord.message_id`; error messages
   name offending ids.
3. Iterate the supplied source sequence, not a set or mapping iteration.
   Serialize `confidence` as its numeric value; serialize evidence as `none`
   for an empty tuple or semicolon-joined ids otherwise.
4. Write with `index=False`, UTF-8, an explicit column order, and create only
   the requested output parent directory when necessary. Do not write a
   partial CSV: validate the complete in-memory frame before `to_csv`.
5. Keep `main.py` orchestration thin: build the frame from
   `bundle.messages["message_id"].tolist()`, validate it through the next
   prompt's public validator, and write `dataset/output.csv` by default.

## Standards to apply
- Add complete docstrings and type annotations to every new function.
- No model/API call, nondeterministic ordering, hardcoded labels, or secret.
- Keep CSV conversion pure and testable; filesystem writing remains isolated.

## Test suite (exhaustive)
- **Unit:** construct records with empty and populated evidence; assert exact
  columns/order, source ordering, semicolon serialization, `none`, key/id parity,
  duplicate/missing/extra-id errors. `tests/unit/test_output_writer.py`.
- **Integration:** feed real `run_decision_fusion` output from a fixture into
  the writer, then parse its CSV and compare all six values per id.
- **System:** assemble the full pipeline over `dataset_valid`, write a CSV,
  and assert one row per input.
- **Acceptance:** assert exact required column order and exactly one row per
  input id, including a non-source-order decision mapping.
- **Smoke:** write one synthetic decision to a temporary CSV and read it back.
- **Sanity:** a blocked record remains `mute` after serialization.
- **Regression:** pin empty evidence to literal lowercase `none`.
- **End-to-end:** use the final command on a small local fixture; no live API.
- **API:** N/A — CSV writing uses no external API.
- **UI:** N/A — output is a batch file, not a rendered surface.

Framework: `pytest`; use `tmp_path`, existing `dataset_valid`, and fake OCR/
ASR clients. Tag every test `REQ-P5-01`; target complete line coverage for
the new pure writer.

## Acceptance criteria (derived from SPEC.md, made executable)
- One row exists for every and only every source `message_id`.
- Header is exactly `message_id,action,message_type,reason,confidence,evidence_message_ids`.
- Rows preserve source order and evidence is never blank.

## Definition of Done
- All acceptance criteria and applicable tests pass.
- Frame and on-disk CSV match the output contract exactly.
- No shared contract or routing decision is modified.

## Out of scope
- Field-value semantic validation (REQ-P5-03), sample scoring (REQ-P5-02),
  and README command documentation (REQ-P5-04).
