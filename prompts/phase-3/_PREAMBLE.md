# Phase 3 — Personalization & Evidence Retrieval — Shared Preamble

Read `SPEC.md` in full if this extract is incomplete; it is a convenience,
not a replacement for the canonical specification.

## Role in the pipeline

This stage consumes P0's `DatasetBundle` and `UserTimeline`, P1 safety
verdicts, and P2 `NormalizedMessage` objects. It produces one Evidence Bundle
per incoming message for decision fusion. It must remain receiver-scoped:
historical records from another user may never influence retrieval or a
personalization signal.

## Requirements (verbatim from SPEC.md §2)

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

## Contracts inherited from SPEC.md §1

```text
UserTimeline = {
  user_id: [
    {
      message_id, conversation_type, group_id, business_id, sender_user_id,
      created_at, message_text, media_type, media_id, forwarded_count,
      message_opened, message_replied, reaction_time_minutes,
      notification_dismissed, muted_after_message, message_reported,
    },
    ...  # sorted by created_at ascending
  ]
}
```

```text
{
  message_id, user_id, conversation_type, group_id, business_id,
  sender_user_id, created_at, media_type,
  normalized_text: str,
  media_confidence: float,
  media_failure: bool,
  media_category: str | null,
  media_failure_reason: str | null
}
```

```text
{ message_id, evidence_ids: [str], evidence_basis: str,
  retrieval_method: str, personalization_signals: {...} }
```

`evidence_ids` is an empty sequence internally when no evidence qualifies;
the public output serialization must render that state as `none`, never a
made-up id. `personalization_signals` must expose numeric
`value_score_adjustment` and `urgency_score_adjustment` so decision fusion can
apply the evidence effect rather than merely display it.

## Binding decision

ADR-003 selects deterministic in-process TF-IDF cosine similarity. Fit the
vocabulary and inverse-document-frequency weights from the receiving user's
timeline only; never use another user's history as retrieval corpus or global
similarity corpus. Candidate evidence must meet both a source-identity match
and a positive minimum text-similarity threshold.

## Non-goals

- No custom training or fine-tuning.
- No UI or dashboard; this remains a batch pipeline.
- No hosted embedding or LLM call for this stage.

## Prompt order

1. `REQ-P3-01-user-scoped-evidence-contract.md`
2. `REQ-P3-02-dual-signal-retrieval.md`
3. `REQ-P3-04-empty-evidence-handling.md`
4. `REQ-P3-05-personalization-signals.md`
5. `REQ-P3-03-causal-score-adjustments.md`
6. `REQ-P3-06-muted-mention-override.md`

