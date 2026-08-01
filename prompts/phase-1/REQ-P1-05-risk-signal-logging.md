# REQ-P1-05 — Per-Message Risk Signal Logging & Batch Entrypoint

## Traceability
- Source requirement: REQ-P1-05 (SPEC.md §2, Phase 1)
- Depends on: REQ-P1-01, REQ-P1-02, REQ-P1-03, REQ-P1-06
- Unblocks: REQ-P1-04

## Objective
Add the batch entrypoint that scores every message in a `DatasetBundle` —
so no message's safety verdict is silently dropped — and make each
verdict's `risk_signals` reliably non-generic, per the requirement's
explicit example: the reason must name *which* signal fired (e.g.
"payment request + unverified new sender"), not a generic "flagged as
suspicious." This is also where `compute_forward_chain_open_rate`
(REQ-P1-03) actually gets called, exactly once per run, and threaded into
every `score_message` call.

## Context & assumptions
- Read `_PREAMBLE.md` first.
- REQ-P1-01/02/03/06 have produced a fully-working `score_message` for one
  message at a time, given `business_accounts` and a precomputed
  `forward_chain_open_rate`. This prompt's job is orchestration across the
  whole bundle, not new signal logic.
- `RiskSignal.detail` (REQ-P1-01) is already the human-readable string
  used directly as each `risk_signals` entry — this prompt does not invent
  a second description layer, it verifies the existing one is
  non-generic and adds the plumbing that makes every message's verdict
  reachable.
- P5 (`reason` string generation) does not exist yet — this prompt does
  not write `reason`, it only guarantees `risk_signals` is good raw
  material for whatever writes `reason` later.

## Files to create or modify
- `code/router/safety/gate.py` — modify: add `run_safety_gate`.
- `code/main.py` — modify: call `run_safety_gate` after `build_user_timelines`
  and report a summary (counts of blocked/borderline/clean).
- `tests/unit/test_risk_signal_wording.py` — new: non-generic wording
  checks.
- `tests/system/test_safety_gate_batch_system.py` — new.
- `tests/system/test_p1_pipeline_system.py` — new (extends the existing
  `tests/system/test_p0_pipeline_system.py` pattern to include P1).

## Interfaces & signatures

```python
# code/router/safety/gate.py addition

def run_safety_gate(bundle: DatasetBundle) -> dict[str, SafetyVerdict]:
    """Score every message in bundle.messages; nothing is silently dropped.

    Computes forward_chain_open_rate once (via
    compute_forward_chain_open_rate on bundle.message_history/
    message_events), then calls score_message once per row of
    bundle.messages, returning a dict keyed by message_id. The returned
    dict has exactly one entry per row of bundle.messages — same
    cardinality guarantee REQ-P0-04/REQ-P5-01 hold for the final output,
    established one phase earlier here so a missing verdict is caught
    immediately rather than surfacing as a mysterious gap in P5.

    Raises no new exception types; any error from score_message on a
    malformed row propagates rather than being swallowed (per the
    project's "fail loudly" convention already established in
    code/router/dataset/loader.py's REQ-P0-01 handling).
    """
```

```python
# code/main.py changes

# After:
#   bundle = load_dataset_bundle(dataset_dir)
#   timelines = build_user_timelines(bundle)
#   validate_row_count_parity(bundle.messages, bundle.output_template)
# add:
#   verdicts = run_safety_gate(bundle)
# and extend the printed summary with counts of
# blocked / borderline (risk_type set, not blocked) / clean messages.
```

## Implementation details
1. Implement `run_safety_gate` in `gate.py`: call
   `compute_forward_chain_open_rate(bundle.message_history,
   bundle.message_events)` once, then iterate
   `bundle.messages.to_dict("records")`, calling `score_message(message,
   bundle.business_accounts, forward_chain_open_rate)` for each and
   collecting into a `dict[str, SafetyVerdict]` keyed by
   `message["message_id"]`.
2. Assert (or let a natural `KeyError`/length-mismatch surface via a
   simple check, matching `validate_row_count_parity`'s style in
   `code/router/dataset/contract.py`) that the returned dict has the same
   length as `bundle.messages` and the same key set as
   `bundle.messages["message_id"]` — this is the "nothing silently
   dropped" guarantee made concrete. Do not add a new exception type for
   this; reuse or raise a plain `AssertionError`/`ValueError` with a clear
   message, since this can only happen from a programming error in this
   function itself (duplicate `message_id` in `bundle.messages` would be
   the one real-world cause, and that is already impossible if P0's
   loader is behaving — this is a belt-and-suspenders internal check, not
   a new user-facing error class).
3. Extend `code/main.py`'s `main()`: after the existing P0 steps, call
   `verdicts = run_safety_gate(bundle)`, then extend the final `print(...)`
   summary to also report, e.g.,
   `f"Safety gate: {blocked} blocked, {borderline} borderline, {clean} clean."`
   where `blocked = sum(v.is_blocked for v in verdicts.values())`,
   `borderline = sum(v.risk_type is not None and not v.is_blocked for v in
   verdicts.values())`, `clean = len(verdicts) - blocked - borderline`.
   Keep `main()`'s existing `try/except DatasetError` structure; this
   prompt's new code does not raise `DatasetError` (it's a different
   package), so no new except clause is needed unless a review of
   `run_safety_gate`'s actual failure modes says otherwise.
4. Write `test_risk_signal_wording.py`: assert every `RiskSignal.detail`
   string defined across `signals.py`'s scam and spam detectors (introspect
   the module's detector table rather than hand-copying each string, so
   this test catches a newly-added generic-sounding detail automatically)
   contains at least one concrete noun/phrase from an explicit denylist of
   generic phrases (`"flagged as suspicious"`, `"looks risky"`, `"seems
   off"`) — i.e. assert none of the denylist phrases appear, and
   separately assert every detail string is non-empty and more than a
   handful of characters (a cheap proxy for "specific enough to be
   useful", not a substitute for the denylist check).

## Standards to apply
- Read all API keys/secrets from environment variables only; never write
  one into a file in this repo. N/A — no external API in this prompt.
- No AI attribution in code comments or docstrings.
- Deterministic; `run_safety_gate`'s only "I/O" is reading already-loaded
  DataFrames from the bundle, no network/file access beyond what P0 did.

## Test suite (exhaustive)
- **Unit:** `tests/unit/test_risk_signal_wording.py` — non-generic wording
  checks as described above.
- **Integration:** `run_safety_gate` invoked against a `DatasetBundle`
  loaded from `tests/fixtures/dataset_valid`, confirming the dict length
  and key set exactly match `bundle.messages`.
- **System:** `tests/system/test_safety_gate_batch_system.py` — a batch of
  synthetic messages spanning clean/borderline/blocked-scam/blocked-spam
  in one `DatasetBundle`-shaped fixture, run through `run_safety_gate`,
  asserting the full set of outcomes together (this is the "assembled
  phase behaving as a whole" test the phase-planner test taxonomy calls
  for). `tests/system/test_p1_pipeline_system.py` — extends P0's existing
  system test to also call `run_safety_gate` after `build_user_timelines`
  and assert it completes without error over the same fixture bundle P0's
  system test already uses.
- **Acceptance:** "Safety gate verdicts... MUST be logged per-message" →
  the integration test's exact-cardinality/key-set assertion is the direct
  proof (every message has a reachable verdict, not just "most" of them).
  "the reason must name which signal fired... not a generic 'flagged as
  suspicious'" → `test_risk_signal_wording.py`'s denylist assertion.
- **Smoke:** `python code/main.py` (or `main()` called directly in-process
  against the real `dataset/` directory) runs to completion and prints the
  new safety-gate summary line without error — add this as a smoke test
  in `tests/system/test_p1_pipeline_system.py` calling `main()` directly
  (matching however `test_p0_pipeline_system.py` already invokes it,
  inspect that file before writing this one so the calling convention
  matches).
- **Sanity:** re-running `run_safety_gate` twice on the same bundle
  produces equal results (no hidden mutable state / ordering dependency
  across calls).
- **Regression:** N/A vs. covered — REQ-P1-04's regression suite is the
  dedicated regression prompt for this phase; this prompt's own tests are
  functional/acceptance, not snapshot locks, to avoid duplicating that
  prompt's scope.
- **End-to-end:** local dry-run over the real `dataset/messages.csv` via
  `code/main.py`'s CLI entrypoint (not mocked, not a gated live-API test —
  there is no external API in this phase) — the smoke test above doubles
  as this; state explicitly here that P1 has no live-API e2e variant
  because ADR-006 chose a rule-based, non-LLM implementation.
- **API:** N/A — no external API interaction.
- **UI:** the `reason`-quality concern touches human-readable output, but
  the actual `reason` field does not exist until P5. For this prompt: the
  `risk_signals` strings that will feed it are checked for non-generic
  wording (above), not a rendered surface — no separate UI test beyond
  that.

Framework: `pytest`. Fixtures: `tests/system/test_safety_gate_batch_system.py`
gets its own small synthetic `DatasetBundle`-shaped fixture (construct
DataFrames directly in the test or add a new `tests/fixtures/
dataset_safety_batch` directory following the existing fixture-directory
convention if a full `load_dataset_bundle` round-trip is preferred —
choose whichever keeps the test readable; either is acceptable as long as
it does not reuse `dataset_valid` for a case that needs specific
blocked/borderline/clean messages `dataset_valid` doesn't already contain).
No externals to mock. Coverage expectation: 100% line coverage on
`run_safety_gate` and the `code/main.py` additions.

## Acceptance criteria (derived from SPEC.md, made executable)
- Every message in a `DatasetBundle` has a reachable `SafetyVerdict` after
  `run_safety_gate` → integration test's cardinality/key-set assertion.
- No `risk_signals` entry across the detector table is a generic
  "flagged as suspicious"-style string → `test_risk_signal_wording.py`.
- `code/main.py` runs end-to-end (P0 + P1) against the real dataset
  without error → the smoke/e2e test in `test_p1_pipeline_system.py`.

## Definition of Done
- All acceptance criteria pass.
- All applicable test types implemented (others marked N/A with reason).
- `run_safety_gate`'s return type is exactly `dict[str, SafetyVerdict]`,
  one entry per `bundle.messages` row.
- `code/main.py`'s existing P0 behavior (exit codes, error messages) is
  unchanged; the new safety-gate summary is additive.

## Out of scope
- Writing `output.csv` or any `reason`/`action`/`message_type` field (P4/P5).
- The override-contract regression suite (REQ-P1-04).
- Any change to `compute_forward_chain_open_rate`'s logic (REQ-P1-03) —
  this prompt only calls it once, at the right place.
