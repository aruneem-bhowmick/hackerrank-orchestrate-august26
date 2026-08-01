---
name: avoid-ai-writing
description: Audit and rewrite prose to remove AI writing patterns ("AI-isms"). Use when asked to remove AI-isms, clean up AI writing, edit writing for AI patterns, audit writing for AI tells, or make text sound less like AI. Supports detect-only and edit-in-place modes, optional voice profiles, and a second corrective pass.
---

# Avoid AI Writing

Edit prose for the patterns that make it sound machine-generated. Treat the
patterns as signals, not proof of authorship. The goal is writing with a clear,
specific human voice, not a mechanically sanitized draft.

## Choose a mode

Use `rewrite` by default. Audit the text, return a rewritten version, summarize
the important changes, then run one corrective audit on the rewrite.

Use `detect` when the user says "detect," "flag only," "audit only," "just
flag," "scan," or asks what patterns are present. Identify the passages and
separate clear problems from choices that may be intentional. Do not rewrite.

Use `edit` when the user names a file and asks for it to be cleaned in place.
Read the file first. Make small, targeted edits to the flagged spans. Preserve
paragraphs that already sound human, and never rewrite quotations, code blocks,
or attributed material. Re-read the edited file before reporting completion.

Accept optional voice hints: `casual`, `professional`, `technical`, `warm`, or
`blunt`. When none is supplied, infer the register from the source. Keep the
writer's perspective and vocabulary rather than imposing a generic persona.

Use an optional context hint to calibrate strictness:

- `linkedin`: permit punchier fragments and sparse visual structure.
- `blog`: apply the full audit.
- `technical-blog` or `docs`: prioritize technical precision and clarity over
  artificial informality.
- `investor-email`: remove promotional language aggressively.
- `casual`: fix only strong, distracting patterns.

If the user asks to iterate, repeat the audit and rewrite once more at most.
Stop after two total passes or when no meaningful patterns remain.

## Audit procedure

1. Read the whole piece before changing it. Identify its audience, purpose,
   existing voice, and any quoted or code material to leave alone.
2. Flag concrete AI-isms with the exact phrase or sentence that caused the
   concern. Do not call a normal technical term an AI tell without context.
3. Replace vague praise with the specific fact, mechanism, example, or opinion
   that gives the sentence its value.
4. Vary sentence and paragraph length. Keep useful fragments and idiosyncratic
   phrasing when they sound like the writer, not like an error.
5. Re-read the result for remaining template language, repetitive rhythm, and
   accidental loss of meaning.

In rewrite mode, return: issues found, the rewritten text, a concise change
summary, and the corrective-pass result. In edit mode, report the passages
changed and the verification result. In detect mode, report only the audit and
its assessment.

## Fix these patterns

### Formatting

- Replace stylistic em dashes and double-hyphen substitutes with punctuation or
  a rewritten sentence. Do not alter legitimate CLI flags, code, or quoted text.
- Remove decorative bold and emoji headings. Use sentence structure to show
  importance instead.
- Turn bullet-heavy prose into paragraphs unless the content is genuinely a
  list, procedure, or set of API parameters.
- In plain-text drafts and code comments, use straight quotes. Finished prose
  may retain locale-correct typography.

### Sentence shape

- Replace "It's not X, it's Y" constructions with a direct claim.
- Cut hollow intensifiers such as `genuine`, `truly`, `quite frankly`, `to be
  honest`, and `it's worth noting`.
- Replace vague endorsements such as "worth exploring" with the reason the
  reader should care.
- Cut hedges including `perhaps`, `could potentially`, and `to be clear` when
  the evidence supports a direct statement.
- Add a bridge when adjacent paragraphs could be swapped without affecting the
  argument.
- Break up compulsive lists of three. Use the number of items the thought needs.
- Avoid formulaic openings such as "In today's..." and generic closing
  predictions. Lead with the actual insight and end with a concrete implication.

### Vocabulary

Replace these words on sight unless they are part of a necessary quotation or
technical term: `delve`, `landscape` as a metaphor, `tapestry`, `realm`,
`paradigm`, `embark`, `testament to`, `robust`, `comprehensive`,
`cutting-edge`, `leverage` as a verb, `pivotal`, `meticulous`, `seamless`,
`game-changing`, `utilize`, `watershed moment`, `vibrant`, `thriving`,
`showcasing`, `deep dive`, `intricate`, `ever-evolving`, `holistic`,
`actionable`, `impactful`, `learnings`, `thought leadership`, `best practices`,
`synergy`, `in order to`, `due to the fact that`, `serves as`, `boasts`,
`commence`, `ascertain`, and `endeavor`.

Flag these only when two or more appear in one paragraph: `harness`,
`navigate`, `foster`, `elevate`, `unleash`, `streamline`, `empower`, `bolster`,
`spearhead`, `resonate`, `revolutionize`, `facilitate`, `underpin`, `nuanced`,
`crucial`, `multifaceted`, `ecosystem` as a metaphor, `myriad`, `plethora`,
`encompass`, `catalyze`, `reimagine`, `galvanize`, `augment`, `cultivate`,
`illuminate`, `juxtapose`, `transformative`, `cornerstone`, `paramount`, and
`poised`.

At high density, replace vague terms such as `significant`, `innovative`,
`effective`, `dynamic`, `scalable`, `compelling`, `unprecedented`,
`exceptional`, `remarkable`, `sophisticated`, and `instrumental` with a number,
comparison, mechanism, or example. The isolated word is not a problem; the
pattern is.

### Templates and transitions

Rewrite or remove these templates when they do not add information:

- "a [adjective] step forward for..."
- "Whether you're X or Y"
- "I recently had the pleasure of..."
- "Moreover," "Furthermore," and "Additionally,"
- "Here's what's interesting"
- "In conclusion," "To summarize," and "At the end of the day"
- "When it comes to" and "That said"

Name the action, evidence, or audience instead. Do not replace one stock phrase
with another.

## Preserve humanity

Do not over-polish. Perfectly even paragraphs, tidy transitions, and a flat
neutral register can make a revision sound more generated than the draft.
Retain a stated preference, a first-person observation, a small irregularity,
or a sharp opinion when it fits the writer and the medium. Technical documents
need precision first; social writing may need energy; neither needs inflated
language.

This project-local skill is based on the MIT-licensed "Avoid AI Writing"
guidance supplied by Conor Bronsdon.
