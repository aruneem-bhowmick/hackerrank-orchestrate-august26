# REQ-P1-04 — Safety-Override Regression Contract

## Traceability
- Source requirement: REQ-P1-04 (SPEC.md §2, Phase 1)
- Depends on: REQ-P1-01, REQ-P1-02, REQ-P1-03, REQ-P1-06, REQ-P1-05
- Unblocks: none (closes out the phase)

## Objective
Lock in, with regression fixtures that must keep passing through every
later phase's changes, the explicit override rule from the problem
statement: "a high safety-gate confidence MUST NOT be overridden by
personalization signals in P3/P4." P3/P4 do not exist yet, so this prompt
proves the guarantee the only way it can be proven before they do — by
showing that varying personalization-shaped data (rich vs. absent sender
engagement history) while holding the message itself fixed produces an
identical `SafetyVerdict`, and by documenting the contract so a future
phase that *does* touch P3/P4 has a clear, testable line it must not
cross.

## Context & assumptions
- Read `_PREAMBLE.md` first.
- This is the last prompt in the phase; every other REQ-P1-* prompt is
  assumed complete: `score_message`, `run_safety_gate`, both signal
  detector families, the borderline contract, and the batch entrypoint
  wired into `code/main.py`.
- Because `score_message`'s signature (fixed since REQ-P1-01) structurally
  excludes `user_id`/`UserTimeline`/`message_history`/`message_events`/
  `users`/`user_business_history`/`groups`/`group_members`, the override
  guarantee is largely already enforced by construction. This prompt's job
  is to make that guarantee an explicit, named, regression-tested
  contract — not to add new production logic (no `gate.py` change is
  expected; if this prompt finds one is needed, that is itself the bug
  this requirement exists to catch).

## Files to create or modify
- `tests/unit/test_safety_override_contract.py` — new.
- `tests/integration/test_safety_override_regression.py` — new.
- `code/router/safety/gate.py` — modify only if a real gap is found (see
  above); otherwise add a top-of-file module docstring paragraph stating
  the override contract explicitly, for future readers/agents.

## Interfaces & signatures
No new public interface. If `gate.py` needs a docstring addition:

```python
"""Deterministic, user-independent scam/spam risk scoring.

Override contract (REQ-P1-04): once run_safety_gate/score_message assigns
is_blocked=True to a message, no later phase may recompute or override
that verdict using personalization signals (sender engagement history,
group role, quiet hours, etc.). A later phase MAY use a *borderline*
verdict (is_blocked=False, risk_type set — see REQ-P1-06) as one input
among several; it may never downgrade a blocked verdict to unblocked, and
it may never upgrade risk_confidence past what this module computed using
personalization data this module never saw in the first place.
"""
```

## Implementation details
1. Write a unit test that calls `score_message` twice with the *identical*
   message dict but two different `business_accounts` inputs that differ
   only in a field a naive implementation might be tempted to read as a
   trust signal (e.g. `messages_sent_30d`, a stand-in for "this sender is
   prolific/established") while holding `verified`/`official_domain`/
   `domain_used_by_sender`/`domain_used_by_sender_age_days`/`brand_name`
   fixed — confirms the resulting `SafetyVerdict`s are equal. This targets
   REQ-P1-01's "must not depend on... engagement pattern" via the one
   piece of business-side data that could plausibly leak a popularity
   signal.
2. Write the signature-level test (if not already covered sufficiently by
   REQ-P1-01's `test_safety_gate_signature.py` — check before duplicating;
   extend that file instead of re-adding the same assertion if it already
   exists) confirming `score_message`'s parameters are unchanged from
   REQ-P1-01's original list after all of REQ-P1-02/03/05/06 landed —
   i.e. no later prompt widened the signature to sneak in a
   personalization-shaped parameter.
3. Write the core regression test: for each of the four real scam-typed
   rows from `dataset/sample_messages.csv` (`sample_msg_019`, `020`,
   `052`, `053` — reuse the exact text already transcribed into
   `tests/fixtures/safety_scam_messages.py` by REQ-P1-02, do not
   retranscribe), call `score_message` twice — once with a
   `business_accounts`/context representing "this sender has a long,
   positive relationship with the user" (high `messages_sent_30d`, and for
   the personal-conversation rows, no business context at all since
   `business=None` either way is the realistic shape — the point being
   demonstrated is that whatever *could* vary along a
   personalization-adjacent axis does not change the outcome) and once
   with a "brand-new sender, no history" shape — assert `is_blocked=True`
   in both, with equal `risk_confidence` and `risk_signals`. This is the
   REQ-P1-04 acceptance test named directly in `SPEC.md` §4's test
   taxonomy table ("High-risk message + high-engagement sender history →
   still muted").
4. If any of the above reveals a real coupling bug, fix `gate.py` minimally
   and re-run every prior prompt's test file to confirm no regression —
   do not weaken this prompt's assertions to accommodate a bug.
5. Add the module docstring paragraph to `gate.py` regardless of whether a
   bug was found, since the contract should be documented either way.

## Standards to apply
- Read all API keys/secrets from environment variables only; never write
  one into a file in this repo. N/A — no external API in this prompt.
- No AI attribution in code comments or docstrings.
- Deterministic; these are pure regression tests over already-implemented
  pure functions.

## Test suite (exhaustive)
- **Unit:** `tests/unit/test_safety_override_contract.py` —
  identical-verdict-across-varying-business-popularity-field test;
  signature-stability test (extends REQ-P1-01's file if present).
- **Integration:** `tests/integration/test_safety_override_regression.py`
  — the four-real-scam-row regression test described in step 3, run
  through the full `score_message` path with real-shaped
  `business_accounts`/None contexts.
- **System:** N/A vs. covered — REQ-P1-05's system test already exercises
  the full batch path; this prompt's regression fixtures are specifically
  about the override guarantee, not new assembled-behavior coverage, so no
  separate system test is added to avoid duplicating REQ-P1-05's.
- **Acceptance:** "A high safety-gate confidence MUST NOT be overridden by
  personalization signals in P3/P4 (e.g. 'user usually engages with this
  sender' cannot rescue a message flagged as scam above threshold)" →
  `test_safety_override_regression.py`'s four-row regression test is the
  direct, literal proof — each row stays blocked regardless of the
  engagement-shaped context variation.
- **Smoke:** N/A vs. covered — every test in this prompt is itself a
  smoke-level call of already-smoke-tested functions; no new entrypoint is
  introduced.
- **Sanity:** re-running the four-row regression test is, by design, the
  sanity check this and every future phase should run before considering
  any change to `code/router/safety/` complete — call this out in the test
  file's module docstring so future prompts/phases know to run it.
- **Regression:** this whole prompt *is* the regression suite for REQ-P1-04
  — the four-row fixture set is the permanent lock; a future change that
  breaks any of these four rows' `is_blocked=True` outcome is a REQ-P1-04
  violation by definition, not a judgment call.
- **End-to-end:** N/A for this prompt — REQ-P1-05 already covers the local
  dry-run; this prompt is regression-focused, not a new e2e path.
- **API:** N/A — no external API interaction.
- **UI:** N/A — no rendered surface; see SPEC.md §3 Non-Goals.

Framework: `pytest`. Fixtures: reuse `tests/fixtures/safety_scam_messages.py`
from REQ-P1-02 (do not fork a duplicate copy of the four transcribed scam
rows). No externals to mock. Coverage expectation: this prompt adds no new
production code paths (unless a bug fix was required), so its coverage
contribution is about test presence, not line coverage of new code; if a
`gate.py` fix was needed, that fix must reach 100% line coverage via this
prompt's own tests.

## Acceptance criteria (derived from SPEC.md, made executable)
- Each of the four real scam-typed sample rows remains `is_blocked=True`
  regardless of a varied "engagement history"-shaped business context →
  `test_safety_override_regression.py::
  test_high_risk_sample_rows_stay_blocked_regardless_of_engagement_shape`.
- `score_message`'s signature contains no personalization-shaped parameter
  after every REQ-P1-* prompt in this phase has landed →
  `test_safety_override_contract.py::test_signature_still_excludes_personalization_after_full_phase`.

## Definition of Done
- All acceptance criteria pass.
- All applicable test types implemented (others marked N/A with reason).
- Every prior prompt's test file in this phase still passes (run the full
  `tests/unit`, `tests/integration`, `tests/system` suite, not just this
  prompt's new files).
- `code/router/safety/gate.py` carries the override-contract docstring
  paragraph.

## Out of scope
- Anything involving an actual P3/P4 implementation — those phases do not
  exist yet; this prompt only guarantees P1's own contract is sound and
  documented ahead of them.
- New signal detectors or threshold changes.
