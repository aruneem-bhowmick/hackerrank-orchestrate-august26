# REQ-P5-04 — Reproducible Submission Command

## Traceability
- Source requirement: REQ-P5-04 (SPEC.md §2, Phase 5)
- Depends on: REQ-P5-01, REQ-P5-02, REQ-P5-03
- Unblocks: none

## Objective
Finish the batch application so a contributor can run one documented command
from a clean checkout, generate a fully validated production CSV, and see the
calibration result. The command must be explicit about optional environment
keys and must succeed without keys through existing media fallback behavior.

## Context & assumptions
- Read `_PREAMBLE.md` first; all production decision fields have already been
  decided by P4 and must be serialized unchanged.
- Existing `code/main.py` is the command entrypoint; extend it instead of
  adding a competing runner.
- Dataset paths should be configurable by a command-line argument for tests,
  while defaulting to the repository `dataset/` directory.

## Files to create or modify
- `code/main.py` — modify CLI parsing, orchestration, error handling, and output reporting.
- `README.md` — modify setup, one-command run, artifact location, and validation instructions.
- `tests/system/test_submission_command.py` — create command tests.
- `tests/system/test_submission_system.py` — modify real/fixture end-to-end checks.

## Interfaces & signatures
```python
from pathlib import Path

def main(dataset_dir: Path = DEFAULT_DATASET_DIR, output_path: Path | None = None) -> int:
    """Run validation, routing, calibration, submission validation, and CSV write.

    Returns zero only after a complete output CSV has passed all validation
    gates. Catches project DatasetError subclasses, reports an actionable
    message to stderr, and never writes a partial artifact on failure.
    """

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse optional dataset and output paths for the single batch command."""
```

## Implementation details
1. Make `python code/main.py` the single documented default command. Add
   `--dataset-dir` and `--output` only as optional test/operations overrides;
   defaults remain `dataset/` and `dataset/output.csv`.
2. In one orchestration path: load/validate bundle, build timelines, normalize
   media, safety-score, personalize, fuse, build output frame, validate frame,
   run sample calibration, write only after successful validation, then print
   row count/output path/action summary/calibration metrics.
3. Catch every relevant project error (including the new output error), write
   a concise stderr message, return nonzero, and ensure no new/overwritten
   partial output is left when failure occurs. Prefer a temporary sibling file
   and atomic replace for material output durability if supported portably.
4. README must give prerequisites, install command, optional `ANTHROPIC_API_KEY`
   and `OPENAI_API_KEY` environment-variable examples without values, the one
   run command, expected artifact, and a pre-submission checklist covering
   exact columns, row parity, and calibration output. Never claim keys are
   required for a fallback-capable run.
5. Run the documented command from the repo root in a clean environment with
   keys removed, inspect the resulting CSV, and record the measured calibration
   baseline in README. Keep generated production CSV content uncommitted unless
   this repository's existing policy explicitly expects it.

## Standards to apply
- Every new function has a docstring and type annotations sufficient for the
  100% documentation gate.
- Secrets are read only from environment variables by existing clients; docs
  never contain a key. No new network call is required for tests.
- Preserve Windows-compatible paths and avoid shell-specific instructions.

## Test suite (exhaustive)
- **Unit:** argument defaults and explicit path overrides; orchestration helper
  propagates a typed failure without writing output.
- **Integration:** fixture dataset with fake media clients runs all stages and
  writes a parser-valid CSV plus calibration report.
- **System:** subprocess `python code/main.py --dataset-dir <fixture> --output
  <tmp>` from repo root with media keys absent; assert zero exit, output exists,
  stdout reports calibration, and CSV passes validator.
- **Acceptance:** documented default command writes all required columns and
  one row per production message; only environment variables are consulted for
  optional secrets.
- **Smoke:** `python code/main.py --help` succeeds; default fixture run exits 0.
- **Sanity:** prior safety/media/personalization summaries still appear.
- **Regression:** invalid output path or validation failure returns nonzero and
  leaves no partial destination file.
- **End-to-end:** run the actual repository dataset keyless, parse the output,
  check 110 rows and all fields, then clean only the generated artifact if it
  was not pre-existing.
- **API:** existing OCR/ASR boundary only: subprocess clears both key variables
  and proves the fallback path needs no secret or live request.
- **UI:** N/A — CLI/CSV are batch interfaces, not a rendered UI.

Use `pytest`, `subprocess`, `tmp_path`, fixture datasets, and no live network;
tag all tests `REQ-P5-04`. Cover every new CLI/error branch.

## Acceptance criteria (derived from SPEC.md, made executable)
- One documented command reproduces a validated artifact from a clean checkout.
- The command reads no secret from source files and succeeds keyless via fallback.
- README documents the command and calibration sanity check.

## Definition of Done
- Full command and end-to-end checks pass on fixture and real data.
- README is sufficient for another contributor to reproduce the submission.
- The final output contract remains unchanged.

## Out of scope
- A web UI, custom model training, changing upstream routing rules, or
  embedding credentials in any source, configuration, or documentation.
