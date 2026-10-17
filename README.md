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
- [ ] Stage 7 — evaluation
- [ ] Stage 8 — Streamlit UI
- [ ] Stage 9 — report

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

## Stage 1: try it

```bash
swipl prolog/load.pl
```

Then see [`QUERIES.md`](QUERIES.md) for queries to type. Run the tests with:

```bash
swipl -g run_tests -t halt tests/test_prolog.pl
```

## Layout

```
prolog/
  mystery.pl         the scenario: cast, rooms, murder, evidence, testimony (data only)
  rules.pl           opportunity / means / motive -> prime_suspect
  contradictions.pl  contradiction/2, explain/3 (proof), proven_liar/1
  load.pl            loads all three
tests/
  test_prolog.pl     plunit tests for the Prolog logic
```
