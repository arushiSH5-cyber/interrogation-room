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

---

## Stage 5 — Live multi-suspect interrogation (`src/game.py`, `src/cli.py`)

### What was built

The first playable game. You question any suspect; after **every**
answer the game runs the full loop and prints any lie it can now prove:

```
suspect.ask(q)  ->  translator.translate  ->  engine.assert_fact  ->  engine.contradictions
   (OOP)              (LLM + functional)          (Prolog)               (Prolog)
```

New pieces:

- **`Game`** (`src/game.py`) coordinates one interrogation. It remembers
  which contradictions it has already shown (`proof_key`) so each is
  reported once, and skips testimony Prolog already knows so repeats do
  not create duplicate proofs.
- **`prolog/detective.pl`** adds `accused/1`: the logic accuses someone
  if evidence contradicts them, if they contradict themselves, or if they
  are in a two-witness tie *and* are a prime suspect (the tie-breaker).
- **Offline mode** (`src/offline.py`): `ScriptedSuspect` answers with
  fixed sentences and `PatternTranslator` reads them with regular
  expressions, so you can play and test without an API key. Its output
  still goes through the same pure pipeline.
- **CLI** (`src/cli.py`): a simple command loop.

### How to run it

Offline (works now, no key):

```bash
.venv/bin/python -m src.cli --offline
```

```
> maid: where were you?
maid: At 20:00 I was in the kitchen. At 21:00 I was in the kitchen. ... At 21:00 I saw niece in the library.
  + fact: maid in the kitchen at 20:00
  ...
> niece: and you?
  !! CONTRADICTION FOUND
     1. evidence (torn_glove): niece was in the study at 20:00
     2. niece said: niece was in the kitchen at 20:00
     3. rule broken: one_place_at_a_time(niece, 20, study, kitchen)
     4. verdict: evidence cannot lie, so niece lied
> board
> accuse niece
Correct! The murderer was niece.
```

With real Claude suspects (needs `ANTHROPIC_API_KEY` in `.env`):

```bash
.venv/bin/python -m src.cli
```

Ask naturally, e.g. `niece: where were you around eight?`. Expect the
niece to give her cover story, and a proof to appear as soon as her
story clashes with the glove or with the maid's sighting. Each question
costs two API calls (the suspect's answer and the translation).

Tests: `.venv/bin/python -m pytest tests/test_game.py -v`.

### Exercises

1. Add a `undo` command that retracts the facts from the last turn.
   Which `PrologEngine` method do you need?
2. In `prolog/detective.pl`, what happens if two innocent witnesses
   disagree and neither is a prime suspect? Write a plunit test for it.
3. Add a `who <room> <hour>` command that lists everyone placed in that
   room at that hour (reuse your Stage 2 exercise).

---

## Stage 6 — Mystery generator checked by Prolog (`src/generator.py`, `prolog/verify.pl`)

### What was built

Claude writes brand-new mysteries as JSON; **Prolog decides whether each
one is fair** before anyone plays it. If not, the problems Prolog found
are sent back to Claude and it tries again (up to 4 attempts).

```
LLM writes JSON -> scenario.validate (shape, names, hours) -> verify.pl (logic)
      ^                                                          |
      +---------------- problems fed back, try again ------------+
```

`prolog/verify.pl` reads the hidden answer key and lists problems as
plain Prolog terms, one `problem/1` clause per rule, for example:

```prolog
problem(culprit_not_at_scene(C)) :-
    culprit(C), murder(_, R, H), \+ true_location(C, R, H).
problem(innocent_accused(S)) :-
    simulated(accused_list(L)), member(S, L), \+ culprit(S).
```

The interesting one is `simulated/1`. It asks "what if a perfect
detective questioned everyone?": it asserts what every innocent would
truthfully say plus the culprit's cover story, runs the **same detective
rules the game uses** (`prime_suspects/1`, `accused_list/1`), and then
retracts the pretend testimony. `setup_call_cleanup/3` guarantees the
cleanup runs even if the goal fails. So "exactly one solution" is checked
by the logic itself, not by Python.

The logic files stay scenario-independent: `prolog/mystery.pl` is still
the hand-written reference scenario (now with its answer key), and
`mysteries/ashford_manor.json` is the same mystery in JSON form.

### How to run it

Tests (offline, a fake LLM returns canned mysteries):

```bash
swipl -g run_tests -t halt tests/test_prolog.pl     # includes the verify unit
.venv/bin/python -m pytest tests/test_generator.py -v
```

In Prolog you can ask directly:

```prolog
?- verify_mystery(P).                 % P = []  (Ashford is fair)
?- retract(evidence(_, torn_glove)), verify_mystery(P).
% P = [culprit_not_caught(niece), not_exactly_one_prime_suspect([])]
```

Generating real mysteries needs an API key in `.env`:

```bash
.venv/bin/python -m src.generator --count 20
```

This uses the cheaper bulk model (`claude-haiku-5-5`) and makes about
20–40 calls (one per attempt). Each success is saved as
`mysteries/gen_NNN.json`, and `test_every_saved_mystery_is_fair` re-checks
every saved file whenever you run pytest.

### Exercises

1. Add `problem(weapon_room_is_murder_room)` for mysteries where the
   weapon is kept in the murder room (too easy). Test it in plunit.
2. Add a new kind of contradiction to `contradictions.pl`, for example
   "nobody can be somewhere after the victim's body was found there".
   Does `verify.pl` need to change? (It should not; explain why.)
3. Look at `attempts_used` after a generation run. Which problems did the
   LLM make most often? What does that tell you about LLMs and rules?
