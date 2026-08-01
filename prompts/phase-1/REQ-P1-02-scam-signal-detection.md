# REQ-P1-02 — Scam/Phishing Signal Detection

## Traceability
- Source requirement: REQ-P1-02 (SPEC.md §2, Phase 1)
- Depends on: REQ-P1-01
- Unblocks: REQ-P1-06, REQ-P1-05, REQ-P1-04

## Objective
Detect scam/phishing patterns — "urgency + payment request + unverified
sender; suspicious links/domains; impersonation of known contacts or
businesses" per the requirement text — and wire them into `score_message`
so a message whose combined scam signal weight reaches `T_scam` is flagged
`risk_type="scam"`. This is the highest-precision, highest-stakes detector
in the phase: per `SPEC.md` §0, the safety gate "overrides everything
downstream," so false positives here (blocking a legitimate message) are
worse than a missed borderline case, which REQ-P1-06 still surfaces to
P3/P4 rather than dropping.

## Context & assumptions
- Read `_PREAMBLE.md` first; inherit the `SafetyVerdict` contract and
  ADR-006's ban on hardcoded brand lists and unweighted signal counts.
- REQ-P1-01 has produced `code/router/safety/verdict.py`
  (`RiskSignal`, `SafetyVerdict`) and `code/router/safety/gate.py`
  (`score_message(message, business_accounts, forward_chain_open_rate)`,
  currently returning a hardcoded clean verdict).
- Assumption from ADR-006, stated explicitly per this prompt's dependency
  on a resolved ADR: signal weights below were calibrated against
  `dataset/sample_messages.csv`'s four `scam`-typed rows
  (`sample_msg_019`, `020`, `052`, `053`) and the known-benign personal
  messages in `dataset/messages.csv` sent by the same sender IDs used in
  scam rows (`u_049`, `u_050` send both benign and scam messages — sender
  identity alone is not usable as a trust signal, which is why no
  "known/trusted sender" allowlist signal exists here).
- `T_scam = 0.55`, defined in `code/router/safety/thresholds.py` (new file,
  created by this prompt since REQ-P1-01 did not need it).

## Files to create or modify
- `code/router/safety/thresholds.py` — new: `T_SCAM`, `T_SPAM` constants
  (only `T_SCAM` used by this prompt; `T_SPAM` added here too since both
  belong in one small constants module, but left unused until
  REQ-P1-03 — document both in the same docstring for a single source of
  threshold truth).
- `code/router/safety/signals.py` — new: scam signal detectors.
- `code/router/safety/gate.py` — modify: wire `detect_scam_signals` into
  `score_message`.
- `tests/fixtures/safety_scam_messages.py` — new: synthetic scam/benign
  message fixtures used across this phase's tests.
- `tests/unit/test_scam_signals.py` — new.
- `tests/integration/test_scam_gate_integration.py` — new.

## Interfaces & signatures

```python
# code/router/safety/thresholds.py

T_SCAM: float = 0.55
"""Minimum combined scam-signal weight for is_blocked=True, risk_type="scam".

Calibrated against dataset/sample_messages.csv's four scam-typed rows,
which each combine at least two independent signals (e.g. urgency +
credential request, or router-instruction-injection + credential request)
and land at or above 0.7 combined weight under this module's weights, well
clear of this threshold; see ADR-006 for the full calibration rationale.
"""

T_SPAM: float = 0.55
"""Minimum combined spam-signal weight for is_blocked=True, risk_type="spam".

See code/router/safety/signals.py's spam detectors (REQ-P1-03) for the
signals this applies to.
"""
```

```python
# code/router/safety/signals.py

def detect_scam_signals(message_text: str, business: dict | None) -> list[RiskSignal]:
    """Return every scam RiskSignal that fires for one message.

    message_text is the message's normalized text (message_text as-is in
    this phase; P2's OCR/ASR transcript once that phase exists — this
    function does not care which, it only sees text). business is the
    matching row of business_accounts as a dict (via
    `business_accounts.set_index("business_id").to_dict("index")[business_id]`
    or equivalent), or None when the message has no business_id (personal/
    group conversation_type) or the business_id is not found.

    Detectors, each independently checked (a message can trigger any
    subset, weights sum and are capped at 1.0 by the caller):

    - payment_or_credential_request (weight 0.35): message_text matches an
      OTP/PIN/password/bank-details/login-code request pattern.
    - urgent_deadline_pressure (weight 0.20): message_text matches an
      urgency/deadline/account-suspension pattern (e.g. "expire today",
      "blocked in", "before midnight", "act now").
    - router_instruction_injection (weight 0.45): message_text contains an
      explicit attempt to instruct the routing system itself (e.g.
      "ignore previous", "routing override", "assistant instruction",
      "set action=", "mark this as notify"). See ADR-006 — this is a
       real, deliberate pattern present in the dataset, not a hypothetical.
    - qr_code_payment_demand (weight 0.30): message_text demands payment by
      QR code or uses clearance/fee/penalty wording. Legitimate merchants
      may use QR payments, so this signal requires corroboration to block.
    - suspicious_link_or_domain (weight 0.20): message_text contains a
      bare domain-like token (regex, e.g. `[\\w-]+\\.(com|in|net|org|co|io|
      xyz|info)`) that does not match business["official_domain"] when a
      business context exists, or any such token at all in a personal/
      group context.
    - unverified_business_sender (weight 0.10): business is not None and
      business["verified"] == "0".
    - business_domain_mismatch (weight 0.25): business is not None,
      business["official_domain"] is non-empty, and it differs from
      business["domain_used_by_sender"].
    - young_sender_domain (weight 0.20): business is not None and
      int(business["domain_used_by_sender_age_days"]) < 30.
    - brand_impersonation (weight 0.40): business is not None, business is
      unverified, and business["brand_name"] (case-insensitive) matches
      the brand_name of some *other*, verified business row. This
      detector needs the full business_accounts table, not just one row —
      see Implementation details step 4 for how the verified-brand set is
      threaded in without widening this function's own signature.

    Returns an empty list if nothing fires. Never raises for well-formed
    input; a missing/blank business field is treated as that signal not
    firing, not an error.
    """
```

## Implementation details
1. Define the text-pattern detectors (`payment_or_credential_request`,
   `urgent_deadline_pressure`, `router_instruction_injection`,
   `qr_code_payment_demand`,
   `suspicious_link_or_domain`) as module-level compiled `re.Pattern`
   lists or a small ordered mapping of `signal_name -> (compiled_pattern,
   weight, detail_template)`, checked case-insensitively against
   `message_text`. Keep patterns as data (a tuple/list), not a long
   if/elif chain, so REQ-P1-05's "name which signal fired" requirement is
   satisfiable by iterating the same structure.
2. Build the domain-token regex once at module scope; reuse it for both
   `suspicious_link_or_domain` and (in `business_domain_mismatch`) parsing
   `business["domain_used_by_sender"]` is not needed — that field is
   already a plain domain string from `business_accounts.csv`, not
   extracted from free text.
3. `unverified_business_sender`, `business_domain_mismatch`,
   `young_sender_domain` read directly off the `business` dict when it is
   not `None`; skip (do not fire, do not error) when `business is None` or
   the relevant field is blank.
4. `brand_impersonation` needs the set of verified brand names across the
   whole `business_accounts` table, not just the one row passed to
   `detect_scam_signals`. Precompute this set once, in `gate.py`, from
   `business_accounts` (`set(business_accounts.loc[business_accounts["verified"]
   == "1", "brand_name"].str.lower())`), and pass it as an additional
   parameter to `detect_scam_signals` (`verified_brand_names: frozenset[str]`)
   — add this parameter to the signature documented above; a business
   context with 0 or all-verified rows still works, the set is just empty.
5. In `gate.py`, `score_message` now: looks up `business_accounts` by
   `message["business_id"]` when non-blank (else `business = None`);
   computes `verified_brand_names` from the full `business_accounts` frame
   (recomputing per call is fine at this dataset's ~110-row scale — do not
   add caching here, REQ-P2-05's caching requirement is about media
   ingestion cost, not this); calls `detect_scam_signals`; sums matched
   weights capped at `1.0`; sets `risk_confidence`, `risk_type="scam"` if
   the sum is `> 0`, `risk_signals=[s.detail for s in matched]`, and
   `is_blocked = risk_confidence >= T_SCAM`.
6. Do not let this prompt's `risk_type="scam"` assignment get overwritten
   by REQ-P1-03's spam scoring — REQ-P1-03 must compare both category
   scores and pick the dominant one; that comparison logic is REQ-P1-03's
   responsibility to add (it modifies `score_message` again), not
   duplicated here. This prompt sets `risk_type="scam"` unconditionally
   whenever the scam sum is `> 0`, which REQ-P1-03 will make conditional
   on scam beating spam.

## Standards to apply
- Read all API keys/secrets from environment variables only; never write
  one into a file in this repo. N/A — no external API in this prompt.
- No AI attribution in code comments or docstrings.
- Deterministic, no I/O, no network calls; `detect_scam_signals` is a pure
  function of its arguments.
- Pattern/weight tables are isolated from the summation/threshold logic so
  either can be unit-tested and adjusted independently.

## Test suite (exhaustive)
- **Unit:** `tests/unit/test_scam_signals.py` — one test per detector,
  each with a firing case and a non-firing case in isolation (payment
  request alone, urgency alone, injection alone, QR-payment demand alone,
  suspicious link alone,
  unverified business alone, domain mismatch alone, young domain alone,
  brand impersonation alone using two synthetic business rows — one
  verified "Acme Bank", one unverified "Acme Bank" with domain mismatch);
  a case with `business=None` confirms all business-scoped detectors
  no-op without raising; threshold boundary case (combined weight exactly
  `T_SCAM`) is `is_blocked=True` (`>=`, not `>`).
- **Integration:** `tests/integration/test_scam_gate_integration.py` —
  `score_message` invoked with a `business_accounts` DataFrame built from
  a small fixture mirroring real schema (a verified "PhonePe" row and an
  unverified "PhonePe" row with mismatched young domain, modeled directly
  on the real `business_041` pattern found during dataset inspection) —
  confirms the impersonation signal fires end-to-end through the full
  DataFrame lookup path, not just the pure-function unit test.
- **System:** the assembled scam-detection path (`score_message` with all
  scam detectors wired) run over a batch of 6 synthetic messages (2 clear
  scam, 2 clear benign, 2 single-signal-only borderline) in one test,
  asserting the full set of `risk_type`/`is_blocked` outcomes together —
  `tests/integration/test_scam_gate_integration.py::test_scam_gate_batch_outcomes`.
- **Acceptance:** "detect scam/phishing patterns (urgency + payment
  request + unverified sender; suspicious links/domains; impersonation of
  known contacts or businesses)" → one acceptance test per named pattern
  type in the requirement text (urgency+payment combination, suspicious
  link, impersonation), each phrased as "given this exact pattern,
  risk_type ends up 'scam' once combined with a second corroborating
  signal or a threshold-crossing single signal — direct pass/fail".
  "route to mute / message_type: scam when risk_confidence exceeds
  threshold T_scam" → `is_blocked=True` exactly at/above `T_SCAM`,
  `False` strictly below, asserted at the boundary.
- **Smoke:** `detect_scam_signals` runs on one synthetic scam message
  (mirroring `sample_msg_020`'s "Support alert... Confirm password and
  OTP now") without error and returns a non-empty list.
- **Sanity:** the four real scam-typed rows transcribed from
  `dataset/sample_messages.csv` (`sample_msg_019/020/052/053`) as fixture
  text, scored with a minimal matching business context (or `None` for
  the two `personal` ones), all still produce `is_blocked=True` after this
  prompt lands — a narrow, fast check separate from the full regression
  suite in REQ-P1-04.
- **Regression:** `tests/fixtures/safety_scam_messages.py` fixes a small,
  named set of scam/benign message texts and their expected matched
  signal names (not just pass/fail) — pinned so a later change to a
  detector's regex/weight that silently stops matching a previously-caught
  pattern is caught immediately. Referenced again by REQ-P1-04's broader
  regression suite.
- **End-to-end:** N/A for this prompt — the full P0→P1 local dry-run is
  REQ-P1-05's batch entrypoint; not duplicated here.
- **API:** N/A — no external API interaction; pure heuristic scoring over
  already-loaded DataFrame data.
- **UI:** N/A — no rendered surface; see SPEC.md §3 Non-Goals.

Framework: `pytest`. Fixtures: new `tests/fixtures/safety_scam_messages.py`
module (plain Python, not a CSV — a list of `(text, business_row_or_None,
expected_signal_names)` tuples) importable by both this prompt's tests and
REQ-P1-04's. No externals to mock. Coverage expectation: 100% line coverage
on `signals.py`'s scam detectors and the scam-scoring branch added to
`gate.py`.

## Acceptance criteria (derived from SPEC.md, made executable)
- Urgency + payment-request combination reaches `is_blocked=True` →
  `test_scam_signals.py::test_urgency_plus_payment_request_blocks`.
- A suspicious link/domain token contributes to `risk_type="scam"` →
  `test_scam_signals.py::test_suspicious_link_detected`.
- A QR-payment demand is detected as a 0.30 corroborating signal without
  blocking by itself →
  `test_scam_signals.py::test_qr_payment_fixture_detects_a_nonblocking_corroborating_signal`.
- Impersonation of a verified business's brand name by an unverified row
  is detected without any hardcoded brand list →
  `test_scam_gate_integration.py::test_brand_impersonation_detected_from_data`.
- `risk_confidence > T_scam` (in practice `>=`, since equality must block
  per the requirement's "exceeds" being interpreted inclusively at the
  calibrated boundary — documented in `thresholds.py`) → `is_blocked=True,
  message_type-relevant risk_type="scam"` →
  `test_scam_signals.py::test_threshold_boundary_blocks_at_exactly_t_scam`.

## Definition of Done
- All acceptance criteria pass.
- All applicable test types implemented (others marked N/A with reason).
- `score_message`'s output still matches the SPEC.md §1.3 contract exactly.
- `T_SCAM`/`T_SPAM` live only in `thresholds.py`; no detector hardcodes a
  threshold value inline.

## Out of scope
- Spam signal detection (REQ-P1-03) — `T_SPAM` is defined here (single
  source of threshold truth) but not used.
- Choosing between scam and spam when both fire (REQ-P1-03's job, since it
  is the second category to land).
- The borderline-band contract when the sum is `> 0` but `< T_SCAM` —
  already true by construction after this prompt (risk_type/confidence/
  signals are populated regardless of is_blocked), but the dedicated
  REQ-P1-06 prompt adds the tests proving it and documents the contract
  explicitly.
- Wiring into `code/main.py` (REQ-P1-05).
