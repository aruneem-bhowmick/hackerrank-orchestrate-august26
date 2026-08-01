# Phase 1 — Safety Gate — Index

## Objective (SPEC.md §2, Phase 1)

Build a user-independent safety gate that classifies every message for
scam/spam risk before any personalization signal is applied, per
`SPEC.md` §0's framing: this is the first of the two coupled decisions the
whole router makes, and its high-confidence verdicts must not be
overridable by anything downstream.

## Definition of Done for the phase

- Every `REQ-P1-01` through `REQ-P1-06` requirement's own Definition of
  Done has passed.
- The phase's output contract (`SPEC.md` §1.3, `SafetyVerdict`) holds
  against a real batch: `run_safety_gate` run against the actual
  `dataset/` (via `code/main.py`) completes without error and produces one
  verdict per row of `dataset/messages.csv`.
- The four real scam-typed rows transcribed from
  `dataset/sample_messages.csv` (`sample_msg_019/020/052/053`) are blocked
  by the gate, and the override-contract regression suite
  (REQ-P1-04) passes.
- `code/router/safety/`'s public functions and dataclasses are fully
  docstringed.

## How to execute

1. Read `_PREAMBLE.md` in full.
2. Execute the prompts below in the listed order. Each prompt's own Files
   to create/modify, Interfaces & signatures, and Test suite sections are
   self-contained given the preamble — no need to re-read `SPEC.md` unless
   a prompt says otherwise.
3. Run that prompt's full test suite before moving to the next; do not
   start a later prompt with an earlier one's tests failing.
4. After REQ-P1-04 (the last prompt) passes, run the entire
   `tests/unit`, `tests/integration`, `tests/system` suite together once
   more as a final phase-level check.

## Prompts, in execution order

| # | Prompt | Summary |
|---|---|---|
| 1 | `REQ-P1-01-safety-verdict-contract.md` | `SafetyVerdict`/`RiskSignal` dataclasses and the `score_message` entrypoint signature — the user-independence guarantee starts here, structurally. |
| 2 | `REQ-P1-02-scam-signal-detection.md` | Scam/phishing detectors (credential request, urgency, router-instruction injection, suspicious link, unverified/impersonating business) and `T_scam` scoring. |
| 3 | `REQ-P1-03-spam-signal-detection.md` | Spam detectors (mass-forward chain language, high forwarded_count, aggregate low-engagement corroborator, repetitive promotion, high-volume broadcast) and `T_spam` scoring. |
| 4 | `REQ-P1-06-borderline-passthrough.md` | Locks the ambiguous-band contract: nonzero-but-below-threshold risk is never silently cleared. |
| 5 | `REQ-P1-05-risk-signal-logging.md` | `run_safety_gate` batch entrypoint (nothing dropped), wired into `code/main.py`; non-generic `risk_signals` wording check. |
| 6 | `REQ-P1-04-override-contract.md` | Regression suite proving high-confidence verdicts are immune to personalization-shaped variation; closes out the phase. |

See `traceability.md` for the full requirement → prompt → test-file matrix.
