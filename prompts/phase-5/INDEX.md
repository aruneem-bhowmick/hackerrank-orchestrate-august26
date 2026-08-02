# Output Generation & Validation

## Objective

Produce a valid, reproducible submission CSV from complete decision records,
prove the artifact is structurally sound, and report solved-example action and
message-type agreement as a calibration sanity check.

## Execution order

Read `_PREAMBLE.md`, then execute each prompt in order. Run the prompt's full
test suite before moving to the next prompt.

1. `REQ-P5-01-output-serialization.md` — serialize exactly one ordered row
   per incoming message using the six-column submission contract.
2. `REQ-P5-03-output-field-validation.md` — reject missing, blank, invalid,
   duplicated, and mismatched output data before it reaches disk.
3. `REQ-P5-02-sample-calibration.md` — route solved examples through the
   same pipeline and report action/type agreement without using labels for
   production decisions.
4. `REQ-P5-04-reproducible-submission-command.md` — connect the final writer
   and calibration report to one documented command and verify a clean run.

## Definition of Done

Every requirement has passing acceptance coverage, every test type is either
implemented or explicitly N/A with a reason, the output contract holds for a
small synthetic batch and the real dataset, the calibration report is present
in the README, and the documented command produces a valid `output.csv`
without hardcoded secrets.
