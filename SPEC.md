# SPEC — Message Notification Router (HackerRank Orchestrate)

Status: DRAFT — v0.1
Owner: Aruneem Bhowmick
Scope: `dataset/messages.csv` → `output.csv` per `problem_statement.md`

This document is the single source of truth for architecture and requirements.
`CLAUDE.md`, `AGENTS.md`, and `.cursor/rules/*.mdc` are thin adapters that point
here — they do not restate requirements. If a tool's guidance and this spec
disagree, this spec wins; update it, then propagate.

---

## 0. Design Principle

The task is framed as a 3-way classifier (`notify` / `digest` / `mute`) but is
actually two coupled decisions:

1. **Safety gate** — is this message risky/unwanted regardless of who the user
   normally engages with? (user-independent, high-precision, overrides
   everything downstream)
2. **Personalized value/urgency score** — given the message survives the gate,
   how should it be prioritized for *this* user, using their history, group
   role, business relationship, and quiet hours?

Pipeline is phase-gated. Each phase has a stable contract in/out so any single
phase can be swapped (rules ↔ model) without breaking downstream phases.

```
P0 Data Load/Validate
  → P1 Safety Gate (user-independent)
    → P2 Multimodal Ingestion (OCR/ASR normalization to text)
      → P3 Personalization & Evidence Retrieval
        → P4 Decision Fusion & Confidence Calibration
          → P5 Output Generation & Validation
```

---

## 1. Data Contracts

### 1.1 Input (from `dataset/messages.csv`)
Per `problem_statement.md` §Input schema — treat as read-only, do not mutate.

### 1.2 Internal — Normalized Message (output of P2)
Every message, regardless of original modality, is normalized to:

```
{
  message_id, user_id, conversation_type, group_id, business_id,
  sender_user_id, created_at, media_type,
  normalized_text: str,       # message_text OR OCR/ASR transcript
  media_confidence: float,    # 1.0 for native text; OCR/ASR conf otherwise
  media_failure: bool,        # true if OCR/ASR could not produce usable text
  media_category: str | null  # e.g. poster, screenshot, doc-photo, voice-note
}
```

### 1.3 Internal — Safety Verdict (output of P1)
```
{ message_id, is_blocked: bool, risk_type: str | null, risk_confidence: float,
  risk_signals: [str] }
```

### 1.4 Internal — Evidence Bundle (output of P3)
```
{ message_id, evidence_ids: [str], evidence_basis: str,
  retrieval_method: str, personalization_signals: {...} }
```

### 1.5 Output (`output.csv`)
Exact columns/order per `problem_statement.md` §Required output:
`message_id, action, message_type, reason, confidence, evidence_message_ids`

---

## 2. Requirements

### Phase 0 — Data Load & Validation

- **REQ-P0-01**: System MUST load all 13 dataset files and validate expected
  columns exist before processing any message. Missing/malformed files fail
  loudly, not silently.
- **REQ-P0-02**: System MUST NOT read or reference any organizer-only or
  hidden ground-truth file. If such a file is discoverable in the repo,
  processing halts with an explicit error (submission-integrity requirement
  from README).
- **REQ-P0-03**: System MUST join `message_history.csv` + `message_events.csv`
  per user at load time into a single per-user interaction timeline, indexed
  for retrieval in P3.
- **REQ-P0-04**: System MUST validate `dataset/messages.csv` row count matches
  `output.csv` row count 1:1 before submission (also re-checked in P5).

### Phase 1 — Safety Gate (user-independent)

- **REQ-P1-01**: Safety classification MUST run before and independently of
  any personalization signal — a message's safety verdict must not depend on
  `user_id`, group role, or the user's typical engagement pattern.
- **REQ-P1-02**: System MUST detect scam/phishing patterns (urgency + payment
  request + unverified sender; suspicious links/domains; impersonation of
  known contacts or businesses) and route to `mute` / `message_type: scam`
  when risk_confidence exceeds threshold T_scam.
- **REQ-P1-03**: System MUST detect spam patterns (mass-forward, repetitive
  promotional content, high `forwarded_count` with low engagement history
  across the user base) → `mute` / `message_type: spam`.
- **REQ-P1-04**: A high safety-gate confidence MUST NOT be overridden by
  personalization signals in P3/P4 (e.g. "user usually engages with this
  sender" cannot rescue a message flagged as scam above threshold). This is
  the explicit override rule from the problem statement.
- **REQ-P1-05**: Safety gate verdicts and their `risk_signals` MUST be logged
  per-message for the reason string in P5 — the reason must name *which*
  signal fired (e.g. "payment request + unverified new sender"), not a
  generic "flagged as suspicious."
- **REQ-P1-06**: Borderline safety cases (risk_confidence in an ambiguous
  band, not high enough to force `mute`) MUST pass through to P3/P4 with the
  risk context attached, not be silently cleared.

### Phase 2 — Multimodal Ingestion

- **REQ-P2-01**: Every `media_type: image` message MUST be run through OCR
  before routing; the resulting text (if any) feeds `normalized_text`.
- **REQ-P2-02**: Every `media_type: voice` message MUST be run through ASR;
  the resulting transcript feeds `normalized_text` and is then processed by
  the *same* downstream text pipeline as native text — no forked logic.
- **REQ-P2-03**: Image messages MUST be classified into a coarse
  `media_category` (e.g. poster/promo, screenshot, document photo, meme,
  personal photo) to inform `message_type` in P4.
- **REQ-P2-04**: OCR/ASR failure (blank/garbled output, silent or unclear
  audio) MUST set `media_failure: true` and route with a lowered confidence
  and an explicit fallback reason — never crash, never silently guess as if
  ingestion succeeded.
- **REQ-P2-05**: Media ingestion cost is real (API calls / inference time);
  system MUST cache ingestion results by `media_id` so repeated media
  references are not reprocessed.

### Phase 3 — Personalization & Evidence Retrieval

- **REQ-P3-01**: Evidence retrieval MUST be scoped to the receiving
  `user_id`'s own historical timeline (from REQ-P0-03) — no cross-user
  leakage.
- **REQ-P3-02**: Retrieval MUST combine at least two signals: (a) same
  sender/business/group identity, (b) text similarity between the incoming
  normalized message and historical messages. A same-source match with no
  text relevance is insufficient on its own for evidence use.
- **REQ-P3-03**: Retrieved evidence MUST be causally connected to the P4
  decision — i.e., if evidence shows repeated dismissals from this sender,
  that must visibly lower the value/urgency score, not just appear decoratively
  in `evidence_message_ids`.
- **REQ-P3-04**: If no relevant historical evidence exists for a user/sender
  pair, `evidence_message_ids` MUST be `none` — never fabricate an ID.
- **REQ-P3-05**: Personalization signals MUST include, where available: group
  role (admin/member), mute state, quiet hours, recent open/reply/dismiss
  rate for this sender/group/business, and existing business relationship
  (`user_business_history.csv`).
- **REQ-P3-06**: A muted group with a direct @mention of the user MUST be
  detectable as an override signal that can raise action above the group's
  baseline mute state (per problem statement's explicit example).

### Phase 4 — Decision Fusion & Confidence Calibration

- **REQ-P4-01**: Final `action` MUST be a deterministic function of
  (safety verdict, personalization score, urgency signals) — not a single
  opaque LLM call with no visible intermediate state. Intermediate scores
  must be loggable for debugging/eval.
- **REQ-P4-02**: `confidence` MUST be computed from a documented formula
  combining: safety-gate certainty, evidence retrieval strength (count +
  relevance of matched evidence), and agreement between independent signals
  (e.g. rule-based heuristic vs. model judgment). Raw LLM-emitted confidence
  numbers with no grounding are not acceptable as the sole source.
- **REQ-P4-03**: `message_type` MUST be selected from the fixed allowed-value
  list in the problem statement; no invented categories.
- **REQ-P4-04**: `reason` MUST reference the specific signal(s) that drove the
  decision (sender history, safety signal, quiet hours, group mute + mention
  override, etc.) in one short human-readable sentence — not a templated
  restatement of the action.

### Phase 5 — Output Generation & Validation

- **REQ-P5-01**: `output.csv` MUST contain exactly one row per `message_id`
  in `dataset/messages.csv`, in the required column order.
- **REQ-P5-02**: System MUST self-validate against `dataset/sample_messages.csv`
  before final submission — report action/message_type agreement rate in the
  README as a calibration sanity check (not scored directly, but demonstrates
  self-verification).
- **REQ-P5-03**: No row may have empty `action`, `message_type`, or
  `confidence`. `evidence_message_ids` may be `none` but not blank/null.
- **REQ-P5-04**: Full run MUST be reproducible from a documented single
  command per README instructions, reading secrets only from environment
  variables (no hardcoded keys).

---

## 3. Non-Goals

- No custom model training or fine-tuning within the 24h window.
- No UI/dashboard — this is a batch scoring pipeline, CLI-invoked.
- No attempt to handle languages beyond what's present in the dataset without
  explicit evidence of need.

---

## 4. Test Taxonomy (skeleton — expand per phase during implementation)

Each REQ above gets at least one test. Use explicit N/A justification where a
test category doesn't apply rather than omitting silently.

| REQ | Test type | Notes |
|---|---|---|
| REQ-P1-01 | Unit | Same message, two synthetic users with different engagement history → identical safety verdict |
| REQ-P1-04 | Integration | High-risk message + high-engagement sender history → still muted |
| REQ-P2-04 | Unit | Feed corrupted/blank media path → graceful fallback, no crash |
| REQ-P3-04 | Unit | New sender, no history → evidence_message_ids == "none" |
| REQ-P3-06 | Integration | Muted group + explicit @mention → action escalates |
| REQ-P5-01 | Integration | Row-count parity check, run as final CI-style gate |
| (voice-specific tests) | N/A for text-only messages | Justify explicitly rather than skipping silently |

---

## 5. ADR Log (Architecture Decision Records)

Append-only. Each entry: date, decision, alternatives considered, rationale.

- **ADR-001** (pending): OCR engine choice.
- **ADR-002** (pending): ASR engine choice.
- **ADR-003** (pending): Text similarity method for retrieval (embeddings vs.
  TF-IDF) — likely driven by time budget once actual dataset volume is known.
- **ADR-004** (pending): Confidence formula weights — to be tuned against
  `sample_messages.csv` behavior.

---

## 6. Open Questions (resolve once Claude Code has inspected the actual dataset)

- Actual row counts / message volume — affects whether embeddings or TF-IDF
  is the right retrieval choice within the time budget.
- Distribution of `media_type` — affects how much OCR/ASR effort is justified.
- Whether `sample_messages.csv` reason strings imply a house style worth
  matching exactly (tone, length) for the `reason` scoring criterion.