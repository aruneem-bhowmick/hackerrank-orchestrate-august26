# Personalization and Evidence Retrieval

## Objective

Deliver deterministic, receiver-scoped historical evidence and explicit
personalization signals for every normalized incoming message. The stage is
complete when all six requirements are satisfied, one Evidence Bundle is
returned for every message in a small real or synthetic batch, and no bundle
can contain evidence from another user.

## Execution order

Read `_PREAMBLE.md`, then execute each prompt in order. Run the complete test
suite specified by a prompt before starting the next one.

1. `REQ-P3-01-user-scoped-evidence-contract.md` — define the public bundle,
   receiver-scoped index, and batch cardinality guard.
2. `REQ-P3-02-dual-signal-retrieval.md` — add same-source filtering and
   deterministic TF-IDF ranking.
3. `REQ-P3-04-empty-evidence-handling.md` — make the no-match result explicit
   and safe to serialize as `none`.
4. `REQ-P3-05-personalization-signals.md` — derive group, quiet-hours,
   engagement, and business-relationship signals from loaded data only.
5. `REQ-P3-03-causal-score-adjustments.md` — turn engagement and dismissals
   into visible score adjustments for later decision fusion.
6. `REQ-P3-06-muted-mention-override.md` — detect direct mentions and expose
   their muted-group override effect.

## Definition of Done

All acceptance criteria in every prompt pass; each test type is implemented
or explicitly marked N/A; the Evidence Bundle contract holds; and the batch
runner is deterministic, complete, and testable without a network call.

