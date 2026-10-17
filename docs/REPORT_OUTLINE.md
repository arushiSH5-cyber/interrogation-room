# Report outline (NeurIPS style)

Working title: **Interrogation Room: Catching Lying LLM Agents with Logic Programming**
Arushi Nirmal, CS 152, San José State University

Target length: 4–6 pages + references (NeurIPS template, `neurips_2025.sty`
or the course-provided one). Every section lists what to write and where
the evidence is in this repo.

> **Numbers marked `[RUN]` are filled from `results/summary.csv` after
> `python -m src.evaluate` has been run with an API key.** Nothing in this
> outline is a measured result until that run exists.

---

## Abstract (≈150 words)

- Problem: LLMs are fluent but can be logically inconsistent; an LLM
  judge inherits the same weakness.
- What we built: a murder-mystery game where LLM suspects are
  interrogated, every answer is translated into Prolog facts, and
  SWI-Prolog proves contradictions live.
- Paradigms: logic (truth), functional (translation pipeline), OOP (agents).
- Headline result: across `[RUN]` generated mysteries, the Prolog
  checker caught the lying culprit in `[RUN]`% of cases with a
  `[RUN]`% false-alarm rate, vs `[RUN]`% / `[RUN]`% for an LLM judge and
  `[RUN]`% / `[RUN]`% for a pure-LLM detective.

## 1 Introduction

- Motivation: hallucination and inconsistency [Ji et al. 2023]; the
  LLM-as-a-judge approach and its biases [Zheng et al. 2023];
  neuro-symbolic fixes on static benchmarks [Logic-LM, Pan et al. 2023].
- Gap: few tests of symbolic checking in a *live, adversarial* setting
  where one agent is told to deceive.
- Contributions (bullet list):
  1. A working game where Prolog, not the LLM, decides what is true, and
     every exposed lie comes with a readable proof.
  2. A generator whose mysteries are *verified by Prolog* to have exactly
     one solution before use.
  3. An evaluation comparing three detectors on the same transcripts.
  4. A case study in matching paradigm to role.

## 2 Related work (short)

- Hallucination surveys [1]; LLM-as-a-judge [4]; Logic-LM and LLM +
  solver pipelines [2]; generative agents with memory [3]; SWI-Prolog [5].
- Position: we reuse the "LLM translates, solver reasons" idea from [2],
  but add adversarial agents and a live game loop.

## 3 System design

Figure 1: architecture diagram (draw from the loop in `src/game.py`):
`Suspect.ask → Translator → pipeline → PrologEngine.assert → contradictions/explain`.

### 3.1 Logic: the truth engine (`prolog/`)
- Facts: `location(Person, Room, Hour)` wrapped as `says/2` (testimony)
  or `evidence/2` (trusted).
- Rules: `prime_suspect/1` = opportunity ∧ means ∧ motive (`rules.pl`).
- Contradictions: `conflict/3` by unification (same person, same hour,
  different room); `explain/3` returns a 4-step proof; `verdict/3`
  ranks evidence over testimony (`contradictions.pl`).
- Accusation: `accused/1` (`detective.pl`).
- Fairness: `verify.pl` simulates a perfect interrogation with
  `setup_call_cleanup/3` and reuses the game's own rules to require
  exactly one prime suspect and no wrongly accused innocent.
- Show one real proof from `results/raw/*.json` as a listing.

### 3.2 Functional: the translation pipeline (`src/pipeline.py`)
- `parse → parse_fact → validate → to_prolog`, all pure, immutable data
  (`NamedTuple`, frozen dataclass), errors as values (`Rejected`).
- Security: only `^[a-z][a-z0-9_]*$` atoms reach Prolog; injection test.
- Boundary handling: hours 0–23 inclusive; `bool` rejected as an hour.

### 3.3 Object-oriented: suspect agents (`src/agents.py`)
- `Suspect` with private state (whereabouts, sightings, secret,
  relationships, memory); public `ask`, read-only `transcript`.
- Inheritance/polymorphism: `InnocentSuspect`, `Culprit` (cover story),
  `ScriptedSuspect` (offline). Factory `build_suspects`.

### 3.4 LLM components
- Structured output (JSON schema with name enums) for the translator,
  the generator, the judge and the detective; refusal fallback.
- Dependency injection (`LLM` protocol) so all 94 Python tests run
  offline.

## 4 Paradigm comparison (the course-specific section)

Table 1: for each role, the paradigm used, why it fits, and what would go
wrong in another paradigm. Suggested rows:

| Role | Paradigm | Why it fits | What breaks otherwise |
| --- | --- | --- | --- |
| Deciding truth / contradictions | Logic | declarative rules, unification does matching, backtracking enumerates every conflict, proofs fall out of the rules | in Python: nested loops, hand-written matching, no proof object |
| Language → facts | Functional | stateless, composable, every step testable in isolation | stateful parsers mix validation with I/O and hide errors |
| Suspects | OOP | each agent bundles private state + behaviour; polymorphic `ask` | with free functions, memory and secrets leak into callers |
| Fuzzy language understanding | LLM | handles paraphrase ("around nine" → 21) | rules cannot cover open-ended English |

Discuss: the one shared Prolog database (a global, mutable store) inside
an otherwise immutable/encapsulated program, and how `Game.activate`
contains it.

## 5 Evaluation

### 5.1 Setup
- `[RUN]` mysteries: `mysteries/ashford_manor.json` (hand-written) +
  `[RUN]` generated by `src/generator.py`, each verified by `verify.pl`.
  Report generation stats: average attempts per accepted mystery `[RUN]`
  and the most common problems the checker found.
- Interrogation: two fixed questions per suspect; suspects and translator
  on `claude-haiku-5-5` (low effort); judge and detective on
  `[RUN: model]`.
- Detectors (a) Prolog `accused_list/1`, (b) LLM judge on the same
  transcript, (c) pure-LLM detective with a 6-question budget.
- Metrics: lie-detection rate (with 95% Wilson CI), false-alarm rate,
  exact-match rate, culprit accuracy; plus *noise* = false facts recorded
  for innocents (agent or translator error).

### 5.2 Results
- Table 2: copy `results/summary.csv`.

| Detector | Lie detection (95% CI) | False alarms | Exact | Culprit named |
| --- | --- | --- | --- | --- |
| Prolog checker | `[RUN]` | `[RUN]` | `[RUN]` | `[RUN]` |
| LLM judge | `[RUN]` | `[RUN]` | `[RUN]` | `[RUN]` |
| Pure-LLM detective | `[RUN]` | `[RUN]` | `[RUN]` | `[RUN]` |

- Figure 2: `results/detection_vs_false_alarms.png`.
- Figure 3: `results/culprit_accuracy.png`.
- API cost of the run: `[RUN]` calls, `[RUN]` input / `[RUN]` output tokens.

### 5.3 Analysis (write after reading `results/raw/`)
- Where Prolog wins: cite one mystery where the judge missed a
  contradiction that Prolog proved (quote the proof).
- Where Prolog loses: cases where the culprit's lie was never stated as a
  place and time (vague answers yield no facts), or where translation
  noise caused a false alarm. Use the `noise` column to separate
  translator/agent errors from rule errors.
- Interpretability: Prolog gives a proof for every accusation; the judge
  gives free-text reasoning that may not be faithful.

## 6 Limitations

- Only one kind of contradiction (one place at a time); no reasoning about
  travel time, alibis "between" hours, or object possession.
- Facts are only as good as the translator: a misread answer becomes a
  "proven" lie. The pipeline rejects malformed facts but cannot catch a
  well-formed wrong one.
- Ground truth assumes innocents never lie; LLM innocents can still
  misspeak (measured as noise).
- Small sample (`[RUN]` mysteries, one run each); no variance across
  seeds; generated mysteries share one template and the same model
  family wrote and played them.
- The fixed questionnaire favours detectors that read structured facts;
  the pure-LLM detective chooses its own questions, which is fairer to
  how it would really be used but less controlled.

## 7 Conclusion and future work

- Summary of the finding in one paragraph.
- Future: richer conflict rules (travel time, objects), letting the
  Prolog proof steer the next question, multiple runs per mystery, and
  giving the LLM judge the Prolog proofs (hybrid detector).

## References

1. Z. Ji et al. Survey of hallucination in natural language generation. ACM Computing Surveys, 2023.
2. L. Pan et al. Logic-LM: Empowering large language models with symbolic solvers. Findings of EMNLP, 2023.
3. J. S. Park et al. Generative agents: Interactive simulacra of human behavior. ACM UIST, 2023.
4. L. Zheng et al. Judging LLM-as-a-judge with MT-Bench and Chatbot Arena. NeurIPS Datasets and Benchmarks, 2023.
5. J. Wielemaker et al. SWI-Prolog. Theory and Practice of Logic Programming, 12(1–2), 2012.

## Appendix ideas

- Full proof trace for one mystery (`trace, prime_suspect(P).` output).
- The persona prompts for an innocent and the culprit (`Suspect.persona_prompt()`).
- The JSON schemas for translator and generator.
