# REQ-P1-01 — Safety Verdict Contract & User-Independent Entrypoint

## Traceability
- Source requirement: REQ-P1-01 (SPEC.md §2, Phase 1)
- Depends on: none (this is the foundational prompt for the phase)
- Unblocks: REQ-P1-02, REQ-P1-03, REQ-P1-06, REQ-P1-05, REQ-P1-04

## Objective
Establish the `SafetyVerdict` output contract and the `score_message`
entrypoint that every later scam/spam signal detector plugs into. The
requirement's guarantee — "a message's safety verdict must not depend on
`user_id`, group role, or the user's typical engagement pattern" — is
enforced here structurally, by giving `score_message` a signature that has
no parameter through which personalization data could even be passed in.
This is the phase's foundation: P1 is the first of the two coupled
decisions in `SPEC.md` §0, and it must be safe to run before P3/P4 exist at
all, using only `DatasetBundle` fields that are not scoped to any one
receiving user.

## Context & assumptions
- Read `_PREAMBLE.md` first; inherit the `SafetyVerdict` contract (§1.3) and
  ADR-006 (rule-based scoring, not an LLM call) it carries.
- Assumes P0 is complete and merged: `code/router/dataset/loader.py`
  provides `DatasetBundle` and `code/router/dataset/schema.py` provides the
  per-file required-columns registry. This prompt does not modify P0 code.
- No prior prompt in this phase exists yet; this prompt creates the
  `code/router/safety/` package from scratch.
- ADR-006 is resolved (not pending) — proceed with rule-based scoring
  without re-litigating LLM vs. rules.

## Files to create or modify
- `code/router/safety/__init__.py` — new package, module docstring only.
- `code/router/safety/verdict.py` — new: `RiskSignal` and `SafetyVerdict`
  dataclasses.
- `code/router/safety/gate.py` — new: `score_message` entrypoint (returns a
  "clean" verdict for now — no signal detection wired in yet, that is
  REQ-P1-02/03's job. This prompt's job is the signature and the
  always-populated-verdict behavior for a message with zero signals).
- `tests/unit/test_safety_verdict.py` — new: contract-shape tests.
- `tests/unit/test_safety_gate_signature.py` — new: signature/independence
  tests.

## Interfaces & signatures

```python
# code/router/safety/verdict.py

@dataclass(frozen=True)
class RiskSignal:
    """One named, weighted heuristic that fired while scoring a message.

    name is a short stable identifier (e.g. "payment_or_credential_request"),
    used in tests and for traceability back to the detector that produced
    it. weight is that signal's contribution toward risk_confidence, in
    [0, 1]. detail is the human-readable string surfaced in
    SafetyVerdict.risk_signals and, eventually, P5's reason field.
    """

    name: str
    weight: float
    detail: str


@dataclass(frozen=True)
class SafetyVerdict:
    """The Safety Verdict contract from SPEC.md §1.3, exactly.

    risk_type is "scam", "spam", or None — never any other string.
    risk_confidence is in [0, 1]. risk_signals is always an immutable tuple
    (never None); empty when no signal fired. is_blocked is True only when
    risk_confidence reaches the threshold for risk_type (T_scam/T_spam);
    a verdict can have risk_type set and is_blocked False (the REQ-P1-06
    borderline case) — that wiring is added in a later prompt, but the
    dataclass shape must support it from the start.
    """

    message_id: str
    is_blocked: bool
    risk_type: str | None
    risk_confidence: float
    risk_signals: tuple[str, ...]
```

```python
# code/router/safety/gate.py

def score_message(
    message: dict,
    business_accounts: pd.DataFrame,
    forward_chain_open_rate: float | None,
) -> SafetyVerdict:
    """Score one message for safety risk, independent of any receiving user.

    message is one row of DatasetBundle.messages as a dict (e.g. from
    `bundle.messages.to_dict("records")`), keyed by the messages.csv column
    names. business_accounts is DatasetBundle.business_accounts verbatim —
    sender-side, global business metadata, not scoped to any receiving
    user. forward_chain_open_rate is a single precomputed float (or None if
    it cannot be computed, e.g. an empty message_history) representing the
    aggregate historical open rate for high-forwarded_count messages across
    the entire user base — see REQ-P1-03 for how it's computed; this prompt
    only needs to accept and thread the parameter through.

    Deliberately excluded from the signature: user_id, UserTimeline,
    DatasetBundle.users, DatasetBundle.message_history,
    DatasetBundle.message_events, DatasetBundle.user_business_history,
    DatasetBundle.groups, DatasetBundle.group_members. Their absence is
    what makes REQ-P1-01/REQ-P1-04 compliance structural rather than a
    convention someone could accidentally violate later. Do not widen this
    signature in a later prompt to accept any of them.

    Raises no exceptions for well-formed input (missing/blank optional
    fields like business_id or message_text are valid and handled, not
    errors). This prompt returns a "clean" SafetyVerdict
    (is_blocked=False, risk_type=None, risk_confidence=0.0,
    risk_signals=[]) unconditionally — REQ-P1-02/03 wire in real scoring.
    """
```

`score_message` immediately converts the loaded row to a `SafetyMessage`
allowlist containing only `message_id`, `business_id`, `message_text`, and
`forwarded_count`. Detector code receives that DTO, never a receiver-scoped
field from the original row.

## Implementation details
1. Create `code/router/safety/__init__.py` with a one-line module docstring
   describing the package ("Deterministic, user-independent scam/spam risk
   scoring — the safety gate ahead of personalization.").
2. Implement `RiskSignal` and `SafetyVerdict` exactly as specified above.
   Use `@dataclass(frozen=True)` to match the immutable-value-object style
   already used in `code/router/dataset/schema.py`'s `DatasetFileSpec`.
3. Implement `score_message` with the signature above. For this prompt,
   hardcode the return to the "clean" verdict — `message_id` taken from
   `message["message_id"]`, everything else defaulted as documented. Do not
   pre-emptively add scam/spam logic here; that belongs to REQ-P1-02/03 and
   splitting it out keeps this prompt's diff reviewable in isolation.
4. Do not read `business_accounts` or `forward_chain_open_rate` yet beyond
   accepting them as parameters — unused-parameter warnings are expected
   and fine at this stage; downstream prompts consume them.
5. Do not wire `score_message` into `code/main.py` yet — that happens once
   REQ-P1-05's batch entrypoint exists, so the CLI has something meaningful
   to report.

## Standards to apply
- Read all API keys/secrets from environment variables only; never write
  one into a file in this repo. (N/A here — no external API — but restated
  per project standard.)
- No AI attribution in code comments or docstrings.
- Deterministic behavior throughout; no I/O, no randomness, no network
  calls in this module.
- `score_message` is pure given its inputs — no caching needed for this
  prompt (REQ-P2-05's caching requirement applies to media ingestion, not
  this phase).

## Test suite (exhaustive)
- **Unit:** `tests/unit/test_safety_verdict.py` — `SafetyVerdict` and
  `RiskSignal` construct with the exact field set and types from §1.3;
  `SafetyVerdict` is frozen (attempting to mutate a field raises
  `FrozenInstanceError`); `risk_signals` defaults are never `None` when
  constructed via `score_message`. `tests/unit/test_safety_gate_signature.py`
  — `score_message` called with a minimal well-formed message dict (all
  required `messages.csv` columns, blank `message_text`) returns
  `is_blocked=False, risk_type=None, risk_confidence=0.0, risk_signals=[]`;
  `message_id` in the returned verdict equals the input's.
- **Integration:** `score_message` called with a real row pulled from
  `bundle.messages` (loaded via `load_dataset_bundle` against
  `tests/fixtures/dataset_valid`) and the real `bundle.business_accounts` —
  confirms the dict shape produced by `DataFrame.to_dict("records")` is
  compatible with `score_message`'s expected keys.
- **System:** N/A for this prompt — no assembled multi-signal behavior
  exists yet; covered once REQ-P1-02/03 land (see REQ-P1-02's system test).
- **Acceptance:** "a message's safety verdict must not depend on user_id,
  group role, or the user's typical engagement pattern" (REQ-P1-01) →
  `inspect.signature(score_message).parameters` contains no parameter named
  `user_id`, `users`, `group_members`, `groups`, `message_history`,
  `message_events`, or `user_business_history` — asserted directly via
  `inspect.signature`, not just by eyeballing the source.
- **Smoke:** `score_message` importable and callable on one synthetic
  message dict without raising.
- **Sanity:** re-running `score_message` twice on the identical input
  returns equal `SafetyVerdict` instances (dataclass equality).
- **Regression:** N/A for this prompt — nothing to regress yet; the
  override-contract regression fixture is REQ-P1-04's job once real
  scoring exists.
- **End-to-end:** N/A for this prompt — the full P0→P1 local dry-run is
  covered once REQ-P1-05's batch entrypoint exists.
- **API:** N/A — no external API interaction; pure dataclasses and a pure
  function.
- **UI:** N/A — no rendered user-facing surface; see SPEC.md §3 Non-Goals.

Framework: `pytest`, matching `pytest.ini`'s `testpaths = tests`. Fixtures:
reuse `tests/conftest.py`'s `load_fixture_bundle`/`fixtures_dir`; add no new
fixture directories for this prompt (a `tests/fixtures/dataset_valid`
already exists from P0). No externals to mock. Coverage expectation:
100% line coverage on `verdict.py` and the code added to `gate.py` in this
prompt — both are pure, small, and fully exercised by the tests above.

## Acceptance criteria (derived from SPEC.md, made executable)
- `SafetyVerdict` has exactly the fields `message_id, is_blocked, risk_type,
  risk_confidence, risk_signals` with the types from §1.3 →
  `test_safety_verdict.py::test_safety_verdict_field_shape`.
- Safety verdict computation cannot read `user_id` or any
  personalization-scoped `DatasetBundle` field, by construction →
  `test_safety_gate_signature.py::test_score_message_signature_excludes_personalization_inputs`.
- Calling `score_message` never raises on a well-formed message row →
  `test_safety_gate_signature.py::test_score_message_smoke`.

## Definition of Done
- All acceptance criteria pass.
- All applicable test types implemented (others marked N/A with reason).
- `SafetyVerdict` matches SPEC.md §1.3 exactly.
- The SafetyMessage allowlist excludes `user_id`, group fields, history, and
  business-relationship fields before detector code runs.
- No change to a shared data contract beyond adding the new §1.3
  implementation itself — `DatasetBundle` (§1.0) is untouched.

## Out of scope
- Any actual scam or spam signal detection (REQ-P1-02, REQ-P1-03).
- The borderline-band threshold logic (REQ-P1-06).
- The batch entrypoint over the whole `DatasetBundle` (REQ-P1-05).
- Wiring into `code/main.py`.
- OCR/ASR or any P2 concern.
