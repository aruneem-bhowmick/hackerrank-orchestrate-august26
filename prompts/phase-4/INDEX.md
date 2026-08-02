# Decision Fusion & Confidence Calibration

## Objective

Fuse P1's safety verdict with P3's personalization signals into one final,
deterministic, loggable routing decision per message: `action`,
`message_type`, `confidence`, and `reason`. The stage is complete when all
four requirements are satisfied, one Decision Record (`SPEC.md` §1.5) is
produced for every message in a small real or synthetic batch, the
safety-override rule (REQ-P1-04) never regresses, and the confidence formula
and message_type classifier have been calibrated against
`dataset/sample_messages.csv`.

## Execution order

Read `_PREAMBLE.md`, then execute each prompt in order. Run the complete test
suite specified by a prompt before starting the next one.

1. `REQ-P4-01-deterministic-action-fusion.md` — fuse the safety verdict and
   personalization scores into a deterministic `action` plus loggable
   intermediate state (`FusionResult`), batched over every message.
2. `REQ-P4-02-confidence-formula.md` — compute `confidence` from safety
   certainty, evidence retrieval strength, and cross-signal agreement.
3. `REQ-P4-03-message-type-selection.md` — select `message_type` from the
   fixed allowed-value list using safety, content, and personalization
   context.
4. `REQ-P4-04-reason-generation.md` — assemble a short, non-templated
   `reason` string from the named decision basis, assemble the full
   Decision Record, and wire it into `code/main.py`.

## Definition of Done

All acceptance criteria in every prompt pass; each test type is implemented
or explicitly marked N/A; the Decision Record contract (`SPEC.md` §1.5)
holds for every message in a batch; the safety-override contract
(REQ-P1-04) has a regression test that never regresses; and
`dataset/sample_messages.csv` calibration results are documented in
`SPEC.md` ADR-004.
