# Design Decisions and AI Usage

## Decision record

This router is designed to make notification decisions understandable after the fact. A final row contains an action, message type, reason, confidence, and historical evidence identifiers; each field has a defined source in the pipeline. The system does not use a general-purpose language model to make the routing decision itself.

The following table records the major choices and their rationale.

| Decision | Approach | Rationale |
| --- | --- | --- |
| Routing policy | Deterministic local rules and fusion | Keeps actions reproducible, reviewable, and testable on a fixed dataset. |
| Safety ordering | Safety evaluates before personalization | Prevents a recipient's engagement history from making unsafe or unwanted content more interruptive. |
| Safety inputs | Narrow, user-independent message view | Separates universal risk assessment from recipient preference and reduces opportunities for leakage. |
| Safety outcome | Blocks are final | A scam or spam decision at threshold always maps to `mute`; downstream logic cannot override it. |
| Historical evidence | Recipient-scoped TF-IDF retrieval | Makes evidence relevant to the recipient while avoiding a global or cross-user history corpus. |
| Evidence grounding | Existing IDs only | Preserves traceability; the system uses `none` instead of fabricating support. |
| Media understanding | Optional OCR and transcription adapters | Adds useful content from attachments without making a valid artifact depend on external credentials. |
| External AI boundary | Media-to-text only | Keeps safety, action, type, confidence, rationale, and evidence deterministic and locally auditable. |
| Caching | In-memory cache keyed by `media_id` | Avoids duplicate provider calls, including when production and sample rows share media. |
| Output evidence format | Semicolon-delimited IDs; `none` when absent | Prevents commas inside evidence from conflicting with the CSV delimiter. |
| Calibration | Separate labeled sample, never decision input | Measures agreement without leaking labels into production routing. |

## Routing policy and precedence

The core policy answers two distinct questions in a fixed order:

1. **Is this content unsafe or clearly unwanted?** The safety gate uses message-level signals such as suspicious financial or credential requests, unsafe links, business-domain inconsistencies, impersonation indicators, and forwarding patterns. Scam and spam scores at or above the `0.55` blocking threshold produce a `mute` decision.
2. **If it is eligible for delivery, how interruptive is it for this recipient?** The personalization and fusion layers assess direct relevance, urgency, group context, relationship history, interaction behavior, quiet hours, and grounded historical evidence.

This ordering encodes a deliberate product constraint: personalization can tune attention for legitimate content, but it cannot make a blocked message eligible for notification. Borderline safety signals remain part of the fusion context when no blocking threshold is crossed.

The output action has three meanings:

| Action | Intended use |
| --- | --- |
| `notify` | Immediate, direct, urgent, or clearly high-value information. |
| `digest` | Useful information that does not warrant an interruption now. |
| `mute` | Suppressed spam, scam, unwanted, repetitive, or low-value content. |

Message type, reason, and confidence are generated from the same decision trace as the action. This avoids a common failure mode in which an explanation describes a different rule than the one that actually determined the action.

## Why external AI is constrained to media normalization

Images and voice notes may contain routing-relevant content that is absent from the row's text field. The project uses external models only to transform those modalities into machine-readable text:

| Capability | Provider adapter | Credential | Request style | Downstream role |
| --- | --- | --- | --- | --- |
| Image OCR | Anthropic vision Messages API | `ANTHROPIC_API_KEY` | Structured tool output | Supplies normalized attachment text. |
| Voice transcription | OpenAI audio transcription API | `OPENAI_API_KEY` | Verbose JSON response | Supplies normalized attachment text. |

Once text is available, the remaining route is local code. No external model is asked whether to notify, digest, or mute; no external model assigns message type or confidence; and no external model chooses historical evidence or writes the final reason. That separation gives the system several useful properties:

- **Repeatable policy.** Identical normalized input passes through the same thresholds and precedence rules.
- **Explainable actions.** Reasons and evidence correspond to stored, inspectable signals rather than an unbounded generation step.
- **Bounded data sharing.** Provider requests are limited to the attachment required for OCR or transcription, not the recipient's timeline, behavioral history, or the final decision trace.
- **Testable failure modes.** Providers can be absent or mocked without changing the routing-policy test surface.

The router does not train a model, fine-tune a provider, or persist provider credentials. API keys are read only from the process environment.

## Media failure policy

Media enrichment is useful but not required to satisfy the output contract. The ingestion layer therefore treats the following as a media-level result rather than a batch-level failure:

- an unset API key;
- an unavailable provider client;
- an unreadable or missing attachment that fails path or file checks; and
- a provider request that returns an error or unusable response.

The normalized message records that outcome, and deterministic routing continues with the information that is available. This behavior is important for reproducible local evaluation and for environments without credentials. It is also why the best final run should provide both credentials: successful OCR and transcription give downstream rules more content to evaluate, particularly for image-only and voice-only messages.

Media results are cached by `media_id`. Cache reuse applies within production routing and across production and sample calibration routing during a single command invocation. Caching limits external requests and ensures the same attachment is represented consistently throughout one run.

## Safety and prompt-injection posture

Attachment text and message content are treated as untrusted data. The safety gate evaluates them with deterministic signals, not instructions embedded in the content. The media adapters request extraction/transcription rather than general routing advice, and their output becomes plain normalized text for subsequent local analysis.

The safety interface intentionally excludes user-specific fields. A rule can inspect a business identity, normalized text, forwarding count, and other message-level facts, but cannot inspect who received the message, their history, group role, engagement rate, quiet hours, or relationships. This keeps the safety verdict universal for the same message content and makes it impossible for personalization to be an implicit safety override.

At least one risk score crossing the blocking threshold yields an immutable blocked verdict. The rest of the pipeline can retain the risk signal for explanation, but action fusion respects the block. This is stricter than using a safety score as merely one soft preference among others.

## Evidence, privacy, and personalization choices

Personalization works from the recipient's own timeline. Retrieval uses receiver-scoped TF-IDF similarity; it is not fit across all users and does not use another recipient's history to justify a decision. Candidate evidence must be both relevant and attributable to the same recipient context.

The CSV carries only message identifiers for evidence, not message bodies or behavioral details. When no useful historical support is available, the artifact uses the literal `none`. When several IDs are selected, they are serialized as a semicolon-separated value such as `history-12;history-47`. This is deliberately distinct from the comma that separates CSV fields and round-trips safely through common CSV readers.

The system uses existing data rather than inferred labels to derive relationship, interaction, group, direct-mention, and quiet-hour signals. It does not create historical messages or extrapolate evidence IDs from model output.

## Confidence and reasons

Confidence is not a provider probability. It is a local combination of:

- safety certainty;
- the availability and strength of retrieved evidence; and
- agreement among routing signals.

This makes a high confidence meaningful as agreement in the router's explicit policy, rather than a claim that an external model is calibrated for notification outcomes. The reason renderer uses concrete, decision-trace facts and avoids unsupported statements about the recipient or message.

## Calibration and known limitation

The supplied sample is used after routing to report agreement, not before routing to learn policy. On the documented keyless baseline snapshot of `dataset/sample_messages.csv`:

| Measure | Result |
| --- | --- |
| Sample rows | 30 |
| Action agreement | 25/30 (83.3%) |
| Message-type agreement | 28/30 (93.3%) |
| SHA-256 snapshot | `C81C6960B65E945D35E8B0CE7C0C70334006AFFCF9C3EF166CF163E960BD1FEE` |

The baseline is a diagnostic rather than a training score. The router deliberately avoids fabricating distinctions that the participant-visible data cannot support. For example, some relationship recency distinctions are not exposed by the available business-history fields, so otherwise similar sample cases may remain indistinguishable to a data-grounded policy.

Calibration should be read alongside the data snapshot and credential state. Supplying media credentials can change normalized media text and therefore can change final routing behavior for attachments. It does not change the safety ordering, evidence scope, output schema, or deterministic fusion policy.

## Validation and operational guidance

Run the following before creating the final artifact:

```sh
pytest -q
interrogate -v code
python code/main.py
```

The application validates the final frame before writing it. The checks cover exact column order, full message coverage, unique identifiers, permitted actions and message types, nonblank reasons, finite confidence, and valid evidence serialization. Any dataset contract failure stops the command with a clear error instead of generating a partial submission.

For setup commands and packaging guidance, see the [README](../README.md). For module-level flow and interfaces, see [Architecture](ARCHITECTURE.md). The challenge-facing contract remains in [the problem statement](../problem_statement.md).

