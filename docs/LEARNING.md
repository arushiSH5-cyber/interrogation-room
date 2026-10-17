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
