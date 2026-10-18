# Interrogation Room

CS 152 (Programming Paradigms) term project by Arushi Nirmal — see
[`Arushi_Nirmal_CS152_Proposal.pdf`](Arushi_Nirmal_CS152_Proposal.pdf).

A murder-mystery game where each suspect is an LLM agent (the culprit lies),
every statement is translated into Prolog facts, and SWI-Prolog detects
contradictions live and explains them with a proof.

| Paradigm | Where it lives |
| --- | --- |
| Logic | `prolog/` — all truth and reasoning (facts, rules, unification, backtracking) |
| Functional | `src/pipeline.py` — pure statement → fact pipeline |
| Object-oriented | `src/agents.py` — `Suspect` objects with private state |

## Progress

- [x] **Stage 1** — hand-written Prolog mystery, rules, contradiction detection with proofs
- [x] **Stage 2** — Python ↔ Prolog bridge (`src/engine.py`)
- [x] **Stage 3** — Claude translator + pure functional pipeline (`src/translator.py`, `src/pipeline.py`)
- [x] **Stage 4** — `Suspect` agents with private state + JSON scenarios (`src/agents.py`, `src/scenario.py`)
- [x] **Stage 5** — multi-suspect interrogation CLI with live checking + offline mode (`src/game.py`, `src/cli.py`)
- [x] **Stage 6** — LLM mystery generator, verified fair by Prolog (`src/generator.py`, `prolog/verify.pl`)
- [x] **Stage 7** — evaluation harness: Prolog vs LLM judge vs pure-LLM detective (`src/evaluate.py`)
- [x] **Stage 8** — Streamlit UI with live evidence board (`app/streamlit_app.py`)
- [x] **Stage 9** — NeurIPS-style report outline (`docs/REPORT_OUTLINE.md`)
- [ ] Real-LLM runs: generate 20 mysteries, run the evaluation, fill the `[RUN]` numbers in the outline (needs `ANTHROPIC_API_KEY` in `.env`)

## Setup

```bash
brew install swi-prolog
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt
```

Run every test (Prolog + Python):

```bash
swipl -g run_tests -t halt tests/test_prolog.pl
.venv/bin/python -m pytest
```

Step-by-step notes for each stage are in [`docs/LEARNING.md`](docs/LEARNING.md).

## Play

```bash
.venv/bin/python -m src.cli --offline                 # scripted suspects, no API key
.venv/bin/python -m src.cli                           # Claude suspects (needs .env)
.venv/bin/streamlit run app/streamlit_app.py          # web UI with live evidence board
```

To use Claude, create `.env` in the project root (it is gitignored):

```
ANTHROPIC_API_KEY=sk-ant-...
```

### Model and cost

Everything uses **Claude Haiku 5.5** by default ($0.10 per million input tokens,
$0.50 per million output tokens). One answer is two API calls (the suspect's reply
and its translation into facts), so a whole game costs well under a cent, and
generating 20 mysteries plus the full evaluation (about 550 calls) is under a dollar.

For stronger role-play in a live demo, put a bigger model in `.env`:

```
IR_MODEL=claude-sonnet-5-5
```

`--model` on the CLI does the same for one run. Network, key and rate-limit problems
show a short message instead of crashing the game.

## Generate mysteries and evaluate

```bash
.venv/bin/python -m src.generator --count 20          # mysteries/gen_001.json ... (Prolog-verified)
.venv/bin/python -m src.evaluate --dry-run            # shows how many API calls a run will make
.venv/bin/python -m src.evaluate                      # results/*.csv + charts
```

## Prolog on its own

```bash
swipl prolog/load.pl
```

Then see [`QUERIES.md`](QUERIES.md) for queries to type.

## Layout

```
prolog/                    LOGIC: all truth and reasoning
  schema.pl                scenario predicates (dynamic)
  mystery.pl               reference scenario "Death at Ashford Manor" + answer key
  rules.pl                 opportunity / means / motive -> prime_suspect
  contradictions.pl        contradiction/2, explain/3 (proof), proven_liar/1
  detective.pl             accused/1: who the logic says lied
  verify.pl                verify_mystery/1: is a mystery fair and solvable?
  load.pl                  loads everything for interactive use
src/
  engine.py                Python <-> Prolog bridge (pyswip), proofs as dicts
  pipeline.py              FUNCTIONAL: pure parse -> validate -> to_prolog
  translator.py            Claude structured output -> pipeline
  agents.py                OOP: Suspect / InnocentSuspect / Culprit / ScriptedSuspect
  scenario.py              mystery JSON helpers (validate, facts, case file)
  game.py                  one interrogation: ask -> translate -> assert -> check
  cli.py                   command-line game
  offline.py               regex translator for scripted suspects (no API key)
  generator.py             LLM writes mysteries, verify.pl approves them
  evaluate.py, charts.py   Prolog vs LLM judge vs pure-LLM detective
  llm.py                   the only file that calls the Anthropic API
app/streamlit_app.py       web UI
mysteries/                 scenarios as JSON
results/                   evaluation CSVs, charts, raw transcripts
tests/                     plunit (test_prolog.pl) + pytest
docs/LEARNING.md           step-by-step notes for every stage
docs/REPORT_OUTLINE.md     NeurIPS-style report outline
```
