# REQ-P1-06 — Borderline Risk Passthrough

## Traceability
- Source requirement: REQ-P1-06 (SPEC.md §2, Phase 1)
- Depends on: REQ-P1-01, REQ-P1-02, REQ-P1-03
- Unblocks: REQ-P1-05, REQ-P1-04

## Objective
Make explicit, and lock with tests, the contract that a message whose
combined risk weight is nonzero but below the blocking threshold still
carries its `risk_type`, `risk_confidence`, and `risk_signals` in the
returned `SafetyVerdict` — never silently cleared back to `None`/`0.0`/`[]`
just because `is_blocked` ended up `False`. This is what lets P3/P4 (once
built) use partial risk context as one input among several, instead of
losing it the moment it fails to clear the safety gate's own bar.

## Context & assumptions
- Read `_PREAMBLE.md` first.
- REQ-P1-01/02/03 already produce this behavior as a side effect of how
  `score_message` is written (risk fields are always set from the winning
  category's confidence/signals, independent of the `is_blocked` compare).
  This prompt does not need to change `gate.py`'s scoring logic — it adds
  the tests and documentation that make the contract a verified, named
  requirement rather than an implicit accident of the current
  implementation, and it is the natural place to catch a regression if a
  future change (e.g. an early return added by mistake) breaks it.
- If, when writing this prompt's tests, you find a case where the current
  implementation *does* clear risk fields on a borderline verdict, that is
  a real bug against REQ-P1-06 — fix `gate.py` as part of this prompt
  rather than weakening the test to match the bug.

## Files to create or modify
- `code/router/safety/gate.py` — modify only if a gap is found per above;
  otherwise, add/confirm a docstring note on `score_message` stating the
  passthrough contract explicitly.
- `tests/unit/test_borderline_passthrough.py` — new.
- `tests/integration/test_borderline_passthrough_integration.py` — new.

## Interfaces & signatures
No new public interface. This prompt adds a docstring clause to the
existing `score_message` (from REQ-P1-01, extended by REQ-P1-02/03):

```python
    """...(existing docstring)...

    Borderline contract (REQ-P1-06): whenever the winning category's
    combined signal weight is > 0, risk_type/risk_confidence/risk_signals
    are populated from it regardless of whether that weight reaches its
    blocking threshold. is_blocked=False with risk_type set and
    risk_confidence > 0 is a valid, expected verdict shape — callers must
    not treat it as equivalent to "no risk detected" (that is
    risk_type=None, risk_confidence=0.0, risk_signals=[]).
    """
```

## Implementation details
1. Add the docstring clause above to `score_message`.
2. Write a unit test that constructs a message text known (from
   REQ-P1-02/03's fixtures) to trigger exactly one weak signal — e.g. only
   `urgent_deadline_pressure` (weight 0.20, well below `T_SCAM=0.55`) —
   and asserts: `is_blocked is False`, `risk_type == "scam"`,
   `risk_confidence == pytest.approx(0.20)`, `risk_signals == [<that
   signal's detail string>]`. This is the core of the requirement: prove
   the fields are *not* zeroed out.
3. Write the mirror case for spam (one weak spam-only signal).
4. Write a true-zero-signal case for contrast: a wholly benign message
   (no detector fires) produces `risk_type=None, risk_confidence=0.0,
   risk_signals=[]` — this is REQ-P3-04's "don't fabricate" sibling
   concern for the safety gate's own contract, and distinguishing it from
   the borderline case is the whole point of this requirement.
5. Write an integration test using `score_message` through a loaded
   `DatasetBundle` fixture (`tests/fixtures/dataset_valid`) confirming at
   least one real fixture row lands in the borderline band end-to-end
   (adjust/add a fixture row if the existing P0 fixture doesn't happen to
   contain one — coordinate with `tests/fixtures/dataset_valid`'s existing
   rows rather than creating a parallel fixture directory for this).

## Standards to apply
- Read all API keys/secrets from environment variables only; never write
  one into a file in this repo. N/A — no external API in this prompt.
- No AI attribution in code comments or docstrings.
- Deterministic; no I/O beyond the existing fixture loading pattern.

## Test suite (exhaustive)
- **Unit:** `tests/unit/test_borderline_passthrough.py` —
  weak-scam-only-signal case, weak-spam-only-signal case, true-zero-signal
  case (all three above), and a case at exactly one weight-unit below each
  threshold to confirm the boundary itself is `is_blocked=False` (the
  `>=` boundary itself is REQ-P1-02/03's test, this one is the field just
  under it).
- **Integration:** `tests/integration/test_borderline_passthrough_integration.py`
  — a real `DatasetBundle`-sourced message lands in the borderline band
  and its `SafetyVerdict` fields are all populated per the contract.
- **System:** N/A vs. covered — the full-batch system test in REQ-P1-05
  will include at least one borderline-band message in its assertions
  rather than duplicating a separate system test here.
- **Acceptance:** "Borderline safety cases... MUST pass through to P3/P4
  with the risk context attached, not be silently cleared" →
  `test_borderline_passthrough.py::
  test_weak_signal_populates_risk_fields_without_blocking` (and its spam
  mirror) directly verify the "not silently cleared" clause; the
  true-zero-signal contrast test proves the distinction is real, not
  coincidental (i.e. fields aren't just *always* nonzero regardless of
  input).
- **Smoke:** `score_message` on one weak-signal message runs without error
  and returns a `SafetyVerdict` with non-default `risk_type`.
- **Sanity:** re-run the weak-signal fixture from REQ-P1-02/03's
  regression set (whichever fixture entry has non-firing status below
  threshold) and confirm it is still borderline, not accidentally promoted
  to blocked by an unrelated later change.
- **Regression:** the weak-signal fixture cases added in this prompt are
  themselves added to `tests/fixtures/safety_scam_messages.py` /
  `safety_spam_messages.py` (extend, don't duplicate) with an explicit
  `expected_is_blocked=False` alongside `expected_signal_names`, so
  REQ-P1-04's broader regression run also locks this behavior.
- **End-to-end:** N/A for this prompt — covered by REQ-P1-05's batch
  entrypoint test, which must include a borderline case in its assertions.
- **API:** N/A — no external API interaction.
- **UI:** N/A — no rendered surface; see SPEC.md §3 Non-Goals.

Framework: `pytest`. Fixtures: extend the existing
`safety_scam_messages.py`/`safety_spam_messages.py` fixture modules from
REQ-P1-02/03 rather than creating new ones; reuse `tests/fixtures/
dataset_valid` for the integration test via `load_fixture_bundle`. No
externals to mock. Coverage expectation: any new branch this prompt's fix
(if one was needed) introduces in `gate.py` must be fully covered; if no
`gate.py` change was needed, this prompt's coverage contribution is 100%
on the new test files themselves (trivially true — they're tests).

## Acceptance criteria (derived from SPEC.md, made executable)
- A message with `risk_confidence` in the ambiguous band (nonzero, below
  its category's threshold) is not blocked but still carries `risk_type`,
  `risk_confidence`, and `risk_signals` → `test_borderline_passthrough.py::
  test_weak_signal_populates_risk_fields_without_blocking`.
- A message with zero matched signals is distinguishable from a borderline
  one (`risk_type=None`, not merely `is_blocked=False`) →
  `test_borderline_passthrough.py::test_true_zero_signal_case`.

## Definition of Done
- All acceptance criteria pass.
- All applicable test types implemented (others marked N/A with reason).
- No change to the `SafetyVerdict` contract's field set or types.
- If a `gate.py` bug was found and fixed to satisfy this contract, the fix
  is isolated to the minimum change needed and does not alter
  REQ-P1-02/03's already-passing tests.

## Out of scope
- Any new signal detectors.
- The batch entrypoint (REQ-P1-05).
- Anything about how P3/P4 actually *use* a borderline verdict once
  received — this phase only guarantees the verdict is not silently
  cleared; consuming it personalization-aware is out of scope until P3/P4
  are built.
