# Learning notes

One section per stage: what was built, the key code, how to run it, and
a few exercises. Stage 1 (pure Prolog) is covered in `README.md` and
`QUERIES.md`.

---

## Stage 2 — Python ↔ Prolog bridge (`src/engine.py`)

### What was built

A small Python class, `PrologEngine`, that lets Python *talk to* Prolog
without ever deciding what is true itself. Python hands Prolog facts
("the maid said she was in the kitchen at 21"), asks it questions
("who are the prime suspects?"), and gets answers back as ordinary
Python strings, ints, lists and dicts.

It uses **pyswip**, a library that embeds SWI-Prolog inside the Python
process. There is exactly one Prolog database per process, so every
`PrologEngine` object shares it.

Two Prolog-side changes came with it:

- `prolog/schema.pl` declares every scenario predicate (`person/1`,
  `room/1`, `says/2`, …) as **dynamic**. Dynamic predicates can be
  changed at run time with `assertz/1` and `retract/1`, which is how the
  game adds testimony and swaps one mystery for another.
- `prolog/mystery.pl` gained an **answer key** (`culprit/1`,
  `true_location/3`, `saw/4`, `cover_story/3`). The detective rules never
  read it; Stage 6 uses it to check a mystery is fair.

### Key code walk-through

```python
def findall(self, template, goal):
    query = f"findall({template}, ({goal}), Out__)"
    bindings = next(iter(self._p.query(query, normalize=False)))
    return to_python(bindings[-1].args[1])
```

Instead of looping over solutions in Python, we let Prolog's own
`findall/3` collect them into one list, then read that list back.
`normalize=False` gives us the raw pyswip objects, and `to_python`
walks them recursively:

| Prolog | pyswip object | Python |
| --- | --- | --- |
| `niece` | `Atom` | `"niece"` |
| `21` | `int` | `21` |
| `[a, b]` | `list` | `["a", "b"]` |
| `location(niece, study, 20)` | `Functor` | `Term("location", ("niece", "study", 20))` |

`proof_to_dict` then turns the proof list from `explain/3`
(`[claim(A), claim(B), breaks(Reason), verdict(V)]`) into a dict with
`claim_a`, `claim_b`, `rule` and `verdict` keys, and `describe_proof`
prints it as four numbered steps.

Notice what is **not** in `engine.py`: no `if` deciding who lied. All of
that stays in the `.pl` files — the logic paradigm owns the truth.

### How to run it

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt
.venv/bin/python -m pytest tests/test_engine.py -v
```

Expect 7 passing tests. To poke at it yourself:

```python
from src.engine import PrologEngine, PROLOG_DIR, describe_proof
e = PrologEngine(); e.consult(PROLOG_DIR / "mystery.pl")
e.prime_suspects()                 # ['niece']
for p in e.contradictions(): print("\n".join(describe_proof(p)))
```

### Exercises

1. Add a method `who_was_placed_in(room, hour)` that returns everyone
   `placed_at/3` puts in that room at that hour. (Hint: one `findall`.)
2. Assert `says(butler, location(butler, garden, 21))` and print the new
   proofs. Which verdicts appear, and why?
3. Why must `assert_fact` only ever receive validated strings? Try to
   think of an input that would let a suspect's answer run arbitrary
   Prolog. (Stage 3 fixes this.)

---

## Stage 3 — Language → logic (`src/llm.py`, `src/pipeline.py`, `src/translator.py`)

### What was built

The bridge from English to Prolog, in three layers:

1. **`llm.py`** — the *only* file that talks to Claude. It defines a tiny
   `LLM` interface (`chat` and `json`) and one real implementation,
   `ClaudeLLM`. Everything else receives an `LLM` object as a parameter
   (*dependency injection*), so tests can pass a fake one and never need
   an API key.
2. **`translator.py`** — asks Claude to read a suspect's answer and
   return JSON that *must* match a schema (structured output): a list of
   `{person, room, hour}`. The schema's `enum` lists only the people and
   rooms in this mystery.
3. **`pipeline.py`** — the **functional** part. Pure functions that turn
   that JSON into safe Prolog strings:

```
parse(raw)            -> list of raw items        (is it JSON with "facts"?)
parse_fact(item)      -> Location | Rejected      (normalise "The Maid" -> maid)
validate(loc, world)  -> Location | Rejected      (known person/room, 0 <= hour <= 23)
to_prolog(speaker, l) -> "says(maid, location(maid, kitchen, 21))"
translate(...)        -> Translation(facts, accepted, rejected)
```

### Key ideas

- **Pure functions**: no printing, no global state, no mutation; same
  input → same output. `test_pipeline_does_not_mutate_input` checks it.
- **Immutable data**: `World` is a frozen dataclass, `Location` and
  `Rejected` are `NamedTuple`s.
- **Errors as values**: instead of raising, each step returns either a
  good value or `Rejected(item, reason)`. `translate` keeps both lists,
  so nothing is dropped silently.
- **Boundaries**: hours `-1` and `24` are rejected, `0` and `23` accepted
  (`test_validate_hour_boundaries`). `True` is rejected as an hour even
  though Python treats `bool` as an `int`.
- **Safety**: only names matching `^[a-z][a-z0-9_]*$` reach Prolog, so an
  answer like `maid), halt, (x` cannot run Prolog code
  (`test_injection_attempt_never_reaches_prolog`). This answers exercise
  3 from Stage 2. The schema enum is a first line of defence; the
  pipeline is the one we trust.

Why not trust the schema alone? The LLM is the fuzzy, unreliable
component. The pipeline is small, pure and fully tested.

### How to run it

```bash
.venv/bin/python -m pytest tests/test_pipeline.py tests/test_translator.py tests/test_llm.py -v
```

All of these run offline. `tests/fakes.py` has the `FakeLLM` used in
place of Claude, and `test_llm.py` checks the real request shape with a
stand-in client.

### Exercises

1. Add a `to_hour` case for strings like `"9pm"` → `21`. Write the test
   first, then make it pass without breaking the others.
2. Write `count_by_room(locations) -> dict[str, int]` as a pure function
   using only comprehensions or `functools.reduce`.
3. Change `translate` so a fact about the speaker comes before facts
   about other people. Which test would you add?

---

## Stage 4 — Suspect agents (`src/agents.py`, `src/scenario.py`)

### What was built

- **Scenarios as JSON.** `mysteries/ashford_manor.json` is the Stage 1
  mystery in a form Python (and later an LLM) can read and write. Besides
  the case file it holds the *answer key*: the true `timeline`, extra
  `sightings` (the maid saw the niece go into the library), and the
  culprit's `cover_story`. `src/scenario.py` has pure helpers:
  `validate` (shape and names), `facts` (JSON → Prolog strings),
  `observations` (what a character saw), and `case_file` (what the
  detective is told).
- **Suspects as objects.** Each suspect is an object with **private
  state** — real whereabouts, what they saw, their secret, their
  relationships, and the conversation so far (`_memory`). The only way in
  is the public interface: `ask(question)`, `name`, `role`, and
  `transcript` (a *copy*, so callers cannot rewrite history).

### Key code walk-through

```python
class Suspect:
    def ask(self, question):
        self._memory.append({"role": "user", "content": question})
        answer = self._reply()                       # <- hook
        self._memory.append({"role": "assistant", "content": answer})
        return answer

class InnocentSuspect(Suspect):
    def _role_instructions(self): return "...Always tell the truth about where you were..."

class Culprit(Suspect):
    def _role_instructions(self): return "...You ARE the murderer... claim you were: <cover story>"

class ScriptedSuspect(Suspect):
    def _reply(self): return "At 20:00 I was in the kitchen. ..."   # no LLM
```

- **Encapsulation**: state lives in `_attributes`; read-only properties
  expose only what a detective may know.
- **Inheritance**: `ask`, memory and prompt building are written once in
  `Suspect`.
- **Polymorphism**: the game calls `suspect.ask(q)` without knowing which
  subclass it holds. The culprit lies, the innocents do not, and the
  scripted suspect skips the LLM, all through the same call.
- **Memory**: every call to the LLM sends the whole conversation, so the
  suspect can stay consistent with (or slip up against) what they said
  before.
- **Factory**: `build_suspects(scenario, llm, scripted=False)` picks the
  right class for each character.

### How to run it

```bash
.venv/bin/python -m pytest tests/test_agents.py tests/test_scenario.py -v
```

With an API key in `.env` you can talk to one suspect directly:

```python
from src import scenario as sc
from src.agents import build_suspects
from src.llm import ClaudeLLM
s = sc.load("mysteries/ashford_manor.json")
niece = build_suspects(s, ClaudeLLM())["niece"]
print(niece.ask("Where were you at nine o'clock?"))
print(niece.persona_prompt())        # see exactly what the model was told
```

### Exercises

1. Add a `NervousInnocent` subclass that tells the truth but sometimes
   gets the hour wrong by one. What does the Prolog checker do with it?
   (This is a source of false alarms in Stage 7.)
2. Add a read-only property `questions_asked` that counts questions
   without exposing `_memory`.
3. Why does `transcript` return copies of the dicts and not the list
   itself? Write the test that would fail if it returned `self._memory`.
