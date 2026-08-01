---
name: orchestrate-phase-planner
description: Turn a single development phase of the Message Notification Router (SPEC.md) into a complete, granular, executable set of implementation prompts. Each generated prompt fully specifies the code to write and an exhaustive test suite across every applicable test type, written so any agent (Claude Code, Codex, Cursor) can build the phase reproducibly from the prompts alone. Use this whenever working on this repo and the user references building, planning, scaffolding, or "doing" a phase (e.g. "Phase 1", "the safety gate phase", "the next phase"), asks to convert SPEC.md or a phase into prompts, wants a per-requirement build backlog, or asks an agent to execute a phase of the router. Trigger this even if the user only says "let's build P1" or "turn Phase 2 into prompts" without naming this skill.
---

# Orchestrate Phase Planner

## Purpose

The Message Notification Router is delivered in phase-gated increments
(P0 → P5, per `SPEC.md` §0/§2). `SPEC.md` is the single source of truth: it
defines, for each phase, a set of uniquely-identified requirements
(`REQ-P<phase>-<nn>`), and separately defines the shared data contracts
(§1), non-goals (§3), test taxonomy skeleton (§4), and locked architecture
decisions (§5 ADR log).

This skill takes **one phase** and expands **every requirement in it** into
a granular implementation prompt. The output is a directory of prompts
standardized enough that any agent — Claude Code, Codex, or Cursor,
whichever has quota at the time — can execute the entire phase from the
prompts alone: write the code, write all relevant tests, and satisfy the
Definition of Done, without re-reading the rest of `SPEC.md` for missing
detail.

The two non-negotiables this skill exists to enforce, unchanged from the
project's general working style:

1. **Exhaustive testing.** Every prompt specifies tests for *every
   applicable type* (unit, integration, system, acceptance, smoke, sanity,
   regression, end-to-end, API, UI) and explicitly marks inapplicable types
   as "N/A — `<reason>`" so coverage is auditable, never silently skipped.
2. **Standardization & reproducibility.** Every prompt follows one fixed
   template, inherits one shared phase preamble, references its source
   requirement ID, and is self-contained. Regenerating the same phase
   produces the same structure. From these prompts, the build is
   deterministic and tool-agnostic.

## Inputs

Before generating, confirm three things (locate them; only ask the user if
they cannot be found):

- **The spec.** `SPEC.md` at the repo root. If it is missing or has
  unresolved items in §6 (Open Questions) that block the target phase, stop
  and surface them — this skill must not invent requirements or guess at
  unresolved ADRs.
- **The target phase.** One of `P0` (Data Load/Validate), `P1` (Safety
  Gate), `P2` (Multimodal Ingestion), `P3` (Personalization & Retrieval),
  `P4` (Decision Fusion & Confidence Calibration), `P5` (Output Generation &
  Validation). Map names/descriptions to phase numbers using `SPEC.md` §2
  headers.
- **The output location.** Default `prompts/phase-<N>/` at the repo root.
  Create it if absent.

## Workflow

Follow these steps in order.

1. **Read `SPEC.md` in full.** Internalize §1 (data contracts), §3
   (non-goals), §5 (ADR log — only *resolved* entries are binding; a
   `(pending)` ADR relevant to this phase must be resolved, or explicitly
   flagged as a prompt-level assumption per rule below), and §6 (open
   questions relevant to the phase). These are inherited by every prompt —
   do not contradict them.

2. **Locate the phase.** Find the target phase's requirements under §2 in
   `SPEC.md`. Extract every `REQ-P<phase>-<nn>` in that section verbatim —
   description, and any explicit acceptance language embedded in the
   requirement text.

3. **Order requirements by dependency.** `SPEC.md`'s requirements are
   already listed in a sensible build order within each phase, but check
   for implicit dependencies (e.g. a decision-fusion requirement that reads
   a field produced by an earlier requirement in the same phase) and
   topologically sort. Preserve `SPEC.md` ID order to break ties (stable,
   reproducible ordering).

4. **Write the phase preamble** (`_PREAMBLE.md`) — the shared context block
   every prompt references, so each prompt is self-contained without
   duplicating all of `SPEC.md`. See "Phase preamble" below.

5. **Generate one prompt per requirement** using the mandated template, in
   dependency order. A requirement may warrant splitting into multiple
   prompts only if it contains genuinely separable deliverables; if so,
   suffix the IDs (`REQ-P1-02a`, `REQ-P1-02b`) and keep traceability to the
   parent requirement. Do not merge requirements.

6. **Write the index and traceability matrix** (`INDEX.md`,
   `traceability.md`). See "Output layout."

7. **Run the quality gate** ("Self-check before finishing"). Fix any
   failures before presenting.

## Phase preamble (`_PREAMBLE.md`)

A single file the prompts point to, carrying inherited context so
individual prompts stay focused yet self-contained. Include:

- The phase's REQ list from `SPEC.md` §2, verbatim, with the phase's role in
  the pipeline (what feeds in from the prior phase's contract, what this
  phase must hand off per §1).
- The exact relevant data contract(s) from `SPEC.md` §1 — quoted verbatim,
  not paraphrased (e.g. P2 prompts inherit the Normalized Message contract
  in §1.2; P3 prompts inherit the Evidence Bundle contract in §1.4).
- Any resolved ADRs from §5 that bind this phase's tooling/library choices.
  If a relevant ADR is still `(pending)`, the preamble must say so
  explicitly and instruct prompts to state their tooling choice as a
  documented **assumption** rather than silently picking one — and note
  that `SPEC.md` §5 should be updated with the resolved ADR once the phase
  is implemented.
- The relevant subset of §3 Non-Goals, so prompts don't over-build (e.g. no
  fine-tuning, no dashboard/UI).
- The dependency-ordered list of prompts in this phase.

Every prompt begins by telling the executor to read `_PREAMBLE.md` first,
and `_PREAMBLE.md` itself begins by telling the executor to read `SPEC.md`
in full if anything here seems incomplete — the preamble is a convenience
extract, not a replacement for the spec.

## The prompt template (use this EXACT structure for every prompt)

Each prompt is one markdown file named `<requirement-id>-<slug>.md` (e.g.
`REQ-P1-02-scam-threshold.md`). Populate every section; never leave a
placeholder. Prefer concrete signatures, exact file paths, and explicit
assertions over prose.

```markdown
# <Requirement ID> — <Title>

## Traceability
- Source requirement: <ID> (SPEC.md §2, Phase <N>)
- Depends on: <prior requirement IDs, or "none">
- Unblocks: <later requirement IDs, or "none">

## Objective
<One paragraph: the capability this delivers, tied to this requirement's
role in the phase and the phase's role in the overall pipeline (SPEC.md §0).>

## Context & assumptions
- Read `_PREAMBLE.md` first; inherit the data contracts (§1) and any
  resolved ADRs (§5) it carries.
- <State the relevant slice of the pipeline/contract this prompt touches —
  what struct it consumes, what it must emit per §1.>
- <List assumptions about what prior prompts in this phase (or prior
  phases) already produced.>
- <If this prompt depends on a `(pending)` ADR, state the chosen tooling
  here explicitly as an assumption, and flag it for the ADR log.>

## Files to create or modify
- `path/to/file.py` — <what changes; create vs modify>
- `tests/...` — <test files this prompt adds>
<Exact paths only. No "etc.">

## Interfaces & signatures
<The concrete public API to implement: function/class signatures with full
type annotations, docstring intent, return types, and raised exceptions.
Be precise enough that two engineers would produce compatible
implementations. Signatures must match the phase's input/output contract
from SPEC.md §1 exactly — no silent field renames.>

## Implementation details
<Numbered, step-by-step instructions: algorithm, edge cases, error
handling, logging hooks, external calls and how they're abstracted for
mockability (OCR/ASR/LLM/embedding clients must be behind an interface that
tests can fake). Call out every edge case implied by the requirement text
in SPEC.md, especially the explicit override/fallback rules (e.g.
REQ-P1-04's safety-overrides-personalization rule, REQ-P2-04's media-failure
fallback, REQ-P3-04's "none" evidence rule).>

## Standards to apply
- Read all API keys/secrets from environment variables only; never write
  one into a file in this repo (SPEC.md, CLAUDE.md, AGENTS.md, and
  `.cursor/rules` all restate this — it is non-negotiable).
- No AI attribution in code comments or docstrings.
- Deterministic behavior wherever the requirement doesn't call for a live
  model call; isolate pure logic from I/O so it's unit-testable without
  network access.
- Cache expensive calls (media ingestion, embeddings, LLM classification)
  per SPEC.md REQ-P2-05 and analogous caching implied elsewhere.

## Test suite (exhaustive)
For EVERY test type below, either specify the tests or write
"N/A — `<reason>`". Never omit a type silently. Tag every test with the
requirement ID.

- **Unit:** <cases incl. happy path, each edge case, each error path;
  target files>
- **Integration:** <module-boundary cases with external clients
  (OCR/ASR/LLM/embedding APIs) mocked>
- **System:** <assembled-phase behavior — e.g. full P1 safety gate given a
  batch of synthetic messages — externals mocked>
- **Acceptance:** <one check per acceptance-relevant clause in the
  requirement's SPEC.md text, phrased as a pass/fail condition>
- **Smoke:** <does it import / run / process a single message end-to-end
  through this unit at all>
- **Sanity:** <narrow post-change correctness checks — e.g. does the
  known-scam fixture still route to mute after unrelated changes>
- **Regression:** <fixtures/snapshots that lock behavior this prompt
  establishes or fixes, esp. for confidence-formula or retrieval-ranking
  logic>
- **End-to-end:** <local dry-run over a small slice of
  `dataset/messages.csv`, or gated e2e with live OCR/ASR/LLM APIs — state
  which, and default to the local/mocked path unless the requirement is
  explicitly about live-API behavior>
- **API:** <request/response shaping and error handling for whichever
  external API this requirement calls — OCR, ASR, embeddings, LLM
  classification. N/A if the requirement is pure logic with no external
  call.>
- **UI:** almost always **N/A — no rendered user-facing surface; the
  deliverable is `output.csv`, not a UI (SPEC.md §3 Non-Goals)**. Only
  populate this if a requirement affects the literal legibility of an
  output field a human reads directly (e.g. the `reason` string's
  human-readability, per REQ-P4-04) — in that case, specify a small set of
  readability/format checks instead of a rendered-surface test.

Specify framework (state it explicitly, e.g. `pytest`), fixtures used (from
a `tests/fixtures/` directory seeded with synthetic messages mirroring the
real schema), how externals are mocked, and the coverage expectation on
pure-logic modules.

## Acceptance criteria (derived from SPEC.md, made executable)
<Restate each acceptance-relevant clause from the requirement's SPEC.md
text as a checkable condition, paired with the test that proves it.>

## Definition of Done
- All acceptance criteria pass.
- All applicable test types implemented (others marked N/A with reason).
- Output/interface matches the SPEC.md §1 contract exactly.
- No change to a shared data contract (§1) unless this requirement
  explicitly authorizes it — if one is needed, update `SPEC.md` first and
  note it in the ADR log, then implement.

## Out of scope
<What this prompt must NOT do — work that belongs to other requirements or
phases — so the executor does not bleed scope into a later phase's
concerns.>
```

## Test taxonomy (authoritative definitions and applicability for this project)

Apply this to decide which types are in-scope for each requirement. Default
to **including** a type unless it is clearly inapplicable, and justify
every exclusion.

- **Unit** — a single function/class in isolation, all I/O mocked.
  *Applies to:* essentially every requirement (safety heuristics, contract
  validators, retrieval scoring, confidence formula, CSV writer).
- **Integration** — two or more components across a boundary, external
  services mocked. *Applies to:* anything touching OCR/ASR/LLM/embedding
  clients, the per-user history index, the P1→P2→P3→P4 handoffs.
- **System** — an assembled phase behaving as a whole with externals
  mocked (e.g. the full safety gate over a batch, the full retrieval
  subsystem). *Applies to:* phase-level orchestration requirements.
- **Acceptance** — the requirement's SPEC.md-derived acceptance clauses,
  verified directly. *Applies to:* every requirement.
- **Smoke** — the thing runs at all on one input. *Applies to:* every
  entry-point-level requirement (phase runners, CLI, the main pipeline
  script).
- **Sanity** — quick, narrow checks that an existing capability still works
  after a later change. *Applies to:* requirements that modify shared logic
  (contracts, confidence formula, retrieval).
- **Regression** — pins previously-correct behavior via fixtures/snapshots.
  *Applies to:* confidence calibration, retrieval ranking, safety-override
  behavior (REQ-P1-04 in particular — this must never silently regress).
- **End-to-end** — the full real path, local dry-run by default; gated
  live-API e2e only where a requirement is explicitly about live external
  behavior. *Applies to:* the full P0→P5 run over `dataset/messages.csv`,
  and any requirement whose correctness depends on real OCR/ASR/LLM output
  quality rather than mocked responses.
- **API** — correct request/response shaping and error/edge handling for
  OCR, ASR, embedding, or LLM classification calls. *Applies to:* P2
  ingestion requirements, any P3/P4 requirement using embeddings or an LLM
  judgment call. **N/A** for requirements with no external API interaction.
- **UI** — see the template section above: **N/A** for nearly everything in
  this project; only the human-readability of output fields a person reads
  directly (chiefly `reason`) is in scope, and even then it's a formatting
  check, not a rendered-surface test.

If a requirement is purely internal plumbing with no external call, mark
**API: N/A — no external API interaction**. If it has no human-read output
surface, mark **UI: N/A — no user-facing rendered surface; see SPEC.md §3
Non-Goals**. Always give the reason, never omit silently.

## Standardization & reproducibility rules

- **One template, always.** Every prompt uses the exact template above,
  every section populated.
- **Stable IDs.** Prompt filenames and headers use `SPEC.md`'s requirement
  IDs unchanged. Splits use letter suffixes; never renumber the spec.
- **Deterministic ordering.** Dependency-topological, `SPEC.md` ID order as
  tiebreak. Regeneration yields the same order and the same files.
- **Self-contained + shared preamble.** Each prompt is executable on its
  own given `_PREAMBLE.md`; shared context lives in the preamble, not
  copy-pasted divergently into each prompt.
- **Inherit, don't restate-then-drift.** Contracts and non-goals come from
  `SPEC.md` verbatim where quoted; never paraphrase them into a conflicting
  form.
- **No ambiguity.** No "TODO", "etc.", or unresolved choices. If `SPEC.md`
  is genuinely silent on a decision the prompt needs (a still-pending ADR),
  state the decision explicitly in the prompt as a documented assumption
  and flag it for the ADR log — see the template's "Context & assumptions"
  section.
- **Traceability everywhere.** Every test is tagged with its requirement
  ID; `traceability.md` maps requirement → prompt(s) → test files.
- **Tool-agnostic.** Nothing in a generated prompt should assume it will be
  executed by Claude Code specifically — Codex or Cursor picking up the
  same prompt file must be able to produce the same result. No references
  to tool-specific features unless the tool is explicitly and unavoidably
  part of the requirement.
- **Secrets discipline.** Every prompt that touches an external API
  restates: read keys from environment variables only, never write one into
  the repo.

## Output layout

Write to `prompts/phase-<N>/`:

```
prompts/phase-<N>/
  _PREAMBLE.md            # shared context for the whole phase
  INDEX.md                # ordered list of prompts + how to execute them
  traceability.md         # requirement -> prompt(s) -> test files matrix
  REQ-P<N>-01-<slug>.md   # one file per requirement, dependency-ordered
  REQ-P<N>-02-<slug>.md
  ...
```

`INDEX.md` states the phase's objective (from its `SPEC.md` §2 header) and
Definition of Done (all REQs in phase satisfied + the phase's output
contract in §1 validated; for P5, additionally the full-run row-count and
non-empty-field checks in REQ-P5-01/03), lists the prompts in execution
order with a one-line summary each, and tells the executor: read
`_PREAMBLE.md`, then execute prompts in listed order, running each prompt's
full test suite before moving on; the phase is complete when every prompt's
Definition of Done passes and the phase's output contract holds against a
small real or synthetic batch.

## Self-check before finishing

Verify, and fix any failure before presenting:

- [ ] Every `REQ-P<N>-*` requirement in the target phase has at least one
      prompt; none skipped or merged.
- [ ] Every prompt uses the exact template with all sections populated and
      no placeholders.
- [ ] Every prompt's test section addresses all ten test types (specified
      or explicit N/A + reason).
- [ ] Every acceptance-relevant clause from the requirement's `SPEC.md`
      text maps to a stated test.
- [ ] Prompts are in valid dependency order; no forward references.
- [ ] `_PREAMBLE.md`, `INDEX.md`, and `traceability.md` exist and are
      consistent with the prompts.
- [ ] No prompt contradicts a `SPEC.md` §1 data contract or §3 non-goal.
- [ ] Any prompt resting on a `(pending)` ADR states its assumption
      explicitly and flags the ADR for resolution.
- [ ] Filenames/IDs match `SPEC.md`; ordering is reproducible on
      regeneration.

## Example (abbreviated — shows the format, not full content)

For **REQ-P1-02 — scam-pattern detection**, the generated
`REQ-P1-02-scam-threshold.md` would, among the full template sections,
contain:

- **Interfaces & signatures:** a `SafetyGate.score(normalized_message) ->
  SafetyVerdict` method matching the §1.3 Safety Verdict contract exactly,
  plus a pure `detect_scam_signals(text: str, sender_context: SenderContext)
  -> list[RiskSignal]` helper kept separate from I/O for testability.
- **Test suite:**
  - Unit: urgency+payment-request combinations, unverified-vs-verified
    sender, link/domain heuristics, each in isolation; threshold boundary
    cases around `T_scam`.
  - Integration: `SafetyGate` invoked with a mocked sender-verification
    lookup.
  - System: N/A vs. covered — state which; if a dedicated P1 system test
    exists, reference it here instead of duplicating.
  - Acceptance: "risk_confidence > T_scam → is_blocked=true, risk_type=scam"
    as a direct check.
  - Smoke: gate runs on one synthetic scam message without error.
  - Sanity: known-scam fixture still triggers after unrelated changes.
  - Regression: fixture set of borderline messages locked to their current
    verdicts.
  - End-to-end: N/A for this requirement — covered by the full-pipeline e2e
    prompt in P5, not duplicated here.
  - API: N/A — no external call; pure heuristic scoring.
  - UI: N/A — no rendered surface (SPEC.md §3).
- **Acceptance criteria → tests:** "safety gate MUST NOT depend on
  personalization signals" (REQ-P1-01, cross-referenced) → the
  same-message-different-user unit test; "risk signals named in reason
  string" (REQ-P1-05, cross-referenced) → an acceptance test asserting the
  verdict's `risk_signals` field is non-generic.

This is what every prompt should feel like: precise enough to implement and
test without further questions, and uniform enough that the whole phase
reads as one coherent, tool-agnostic build plan.