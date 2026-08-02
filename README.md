# Message Notification Router

This submission routes each incoming WhatsApp message to `notify`, `digest`, or `mute`. It combines multimodal normalization, deterministic safety checks, recipient-specific evidence, and auditable decision fusion to write a submission-ready `dataset/output.csv`.

## Judge quick start

Use a Python environment with the project dependencies installed:

```sh
python -m pip install -r requirements.txt
python code/main.py
```

The command reads `dataset/` and writes `dataset/output.csv`. It prints a batch summary, safety and media counts, action counts, and the sample calibration result.

Optional credentials improve image and voice-note handling. They are read only from environment variables; do not put them in source control.

| Shell | Commands |
| --- | --- |
| POSIX shells | `export ANTHROPIC_API_KEY="..."`<br>`export OPENAI_API_KEY="..."`<br>`python code/main.py` |
| PowerShell | `$env:ANTHROPIC_API_KEY = "..."`<br>`$env:OPENAI_API_KEY = "..."`<br>`python code/main.py` |

`ANTHROPIC_API_KEY` enables image OCR and `OPENAI_API_KEY` enables voice transcription. Either key may be omitted: the router completes deterministically with explicit media-failure fallbacks. For the strongest final artifact, provide both keys and rerun the command above.

To use another dataset directory or artifact path:

```sh
python code/main.py --dataset-dir path/to/dataset --output path/to/output.csv
```

## Submission artifact

`output.csv` has exactly one row for every `message_id` in `messages.csv` and these columns, in this order:

```text
message_id,action,message_type,reason,confidence,evidence_message_ids
```

`evidence_message_ids` is `none` when no supporting historical evidence is available. Multiple identifiers are separated by semicolons so the CSV remains unambiguous.

Before packaging, run:

```sh
pytest -q
interrogate -v code
python code/main.py
```

The first two commands verify behavior and docstring coverage; the last command regenerates the deliverable. The router also validates column order, row parity, allowed values, confidence values, and evidence serialization before writing the artifact.

## Routing approach

| Stage | Purpose |
| --- | --- |
| Dataset checks | Validate the expected participant-facing files, schemas, joins, and message identifiers. |
| Media normalization | Extract text from image and voice attachments when credentials are available; cache results by media identifier. |
| Safety gate | Apply deterministic scam, spam, and unwanted-content checks before personalization. Blocking verdicts cannot be overridden. |
| Personalization | Retrieve recipient-scoped historical evidence and derive relationship, interaction, group, and quiet-hour signals. |
| Decision fusion | Combine content urgency, safety, and personalization into an action, message type, reason, confidence, and evidence list. |
| Output validation | Enforce the required submission schema and complete message coverage. |

## Documentation

| Document | Contents |
| --- | --- |
| [Architecture](docs/ARCHITECTURE.md) | Component topology, data flow, interfaces, invariants, runtime lifecycle, and operational behavior. |
| [Design decisions and AI usage](docs/DESIGN_DECISIONS_AND_AI_USAGE.md) | Decision rationale, the precise boundary for external AI services, safety controls, trade-offs, and calibration evidence. |
| [Problem statement](problem_statement.md) | Participant-facing challenge context, dataset description, and submission contract. |
| [Implementation specification](SPEC.md) | Detailed functional requirements, acceptance criteria, and recorded implementation decisions. |
| [Agent and transcript instructions](AGENTS.md) | Repository operating rules and required conversation-transcript handling. |

## Submission checklist

- Install dependencies and provide both optional media credentials when available.
- Run `python code/main.py` against the final `dataset/` directory.
- Confirm `dataset/output.csv` is the freshly generated six-column artifact.
- Run the validation commands above and include the required code package, output artifact, and transcript in the submission channel.
