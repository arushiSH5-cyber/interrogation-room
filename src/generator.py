"""Generate new mysteries with an LLM, and let Prolog approve them.

    LLM writes JSON  ->  scenario.validate (shape)  ->  verify.pl (fairness)
          ^                                                   |
          +----------- problems fed back, try again ----------+

Only mysteries with zero problems are saved, so every generated mystery
is known to have exactly one prime suspect, a catchable culprit, and no
innocent who the logic would wrongly accuse.

Usage:
    python -m src.generator --count 20            # writes mysteries/gen_001.json ...
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import scenario as sc
from .engine import PrologEngine
from .llm import BULK_MODEL, LLM, ClaudeLLM, LLMError

# Varied settings so the generated set is not twenty copies of one house.
THEMES = (
    "a snowed-in ski lodge", "a 1920s ocean liner", "a university chemistry department",
    "a vineyard during harvest", "a lighthouse on a remote island", "a film set in the desert",
    "a Victorian theatre", "a space research station", "a jazz club in 1950s Chicago",
    "a country fair", "a monastery in the mountains", "a luxury sleeper train",
    "a natural history museum after closing", "a Parisian fashion house", "a Scottish castle hotel",
    "a tech startup's retreat", "a circus winter camp", "an Antarctic research base",
    "a riverboat casino", "a botanical garden greenhouse", "a small-town bakery",
    "an observatory on a mountain", "a racing stable", "a boarding school",
)

SYSTEM_PROMPT = """\
You design small, fair murder mysteries for a logic-checked detective game.
All names (people, rooms, weapon, evidence items, motives) must be lowercase
snake_case atoms like "head_chef" or "wine_cellar". Hours are integers 0-23.

Hard rules (a Prolog checker rejects the mystery otherwise):
1. Exactly {n} suspects plus one victim (the victim is NOT in "suspects").
   Use 4 or 5 rooms and exactly 2 consecutive evening hours in "hours";
   the murder happens at the second hour.
2. "timeline" gives where EVERY suspect and the victim truly were at EVERY
   hour in "hours" (one room per person per hour).
3. The culprit is a suspect with a motive, is in the murder room at the
   murder hour, and is in the weapon_room at the earlier hour.
4. No innocent suspect is in the murder room at the murder hour.
5. "cover_story" lists one (room, hour) for each hour in "hours"; it must
   be false for at least one hour and must give an alibi for the murder hour.
6. Make it solvable: at least one evidence item puts the culprit in the
   weapon_room at the earlier hour, AND at least one innocent "sighting"
   (or a second evidence item) puts the culprit in the murder room at the
   murder hour. Sightings and evidence must match the timeline.
7. Give at least one innocent suspect a motive too (a red herring), but
   make sure that innocent was never in the weapon_room and was not in the
   murder room at the murder hour. Use "" for no motive.
8. Every suspect has a short role, personality, a private secret, and
   relationships with one or two others.
"""


def scenario_schema() -> dict:
    """Strict JSON schema for one mystery (structured output)."""
    string, integer = {"type": "string"}, {"type": "integer"}

    def obj(**props):
        return {"type": "object", "properties": props,
                "required": list(props), "additionalProperties": False}

    def array(item):
        return {"type": "array", "items": item}

    return obj(
        title=string, setting=string, victim=string,
        hours=array(integer), rooms=array(string),
        murder=obj(room=string, hour=integer, weapon=string, weapon_room=string),
        suspects=array(obj(name=string, role=string, personality=string,
                           motive=string, secret=string,
                           relationships=array(obj(person=string, feeling=string)))),
        culprit=string,
        timeline=array(obj(person=string, room=string, hour=integer)),
        sightings=array(obj(witness=string, person=string, room=string, hour=integer)),
        cover_story=array(obj(room=string, hour=integer)),
        evidence=array(obj(item=string, description=string, person=string,
                           room=string, hour=integer)),
    )


def check(scenario: dict, engine: PrologEngine) -> list[str]:
    """All problems with a candidate mystery: shape first, then logic."""
    problems = sc.validate(scenario)
    if problems:
        return problems
    engine.load_scenario(sc.facts(scenario))
    try:
        return engine.verify()
    finally:
        engine.reset()


class GenerationFailed(RuntimeError):
    pass


class MysteryGenerator:
    """Asks the LLM for a mystery until Prolog finds no problems."""

    def __init__(self, llm: LLM, engine: PrologEngine | None = None,
                 max_attempts: int = 4) -> None:
        self._llm = llm
        self._engine = engine or PrologEngine()
        self._max_attempts = max_attempts
        self.attempts_used: list[int] = []      # attempts per success (for the report)

    def generate(self, theme: str, n_suspects: int = 4) -> dict:
        messages = [{"role": "user", "content": f"Write a mystery set in {theme}."}]
        system = SYSTEM_PROMPT.format(n=n_suspects)
        problems: list[str] = []
        for attempt in range(1, self._max_attempts + 1):
            candidate = self._llm.json(system, messages, scenario_schema())
            problems = check(candidate, self._engine)
            if not problems:
                self.attempts_used.append(attempt)
                return candidate
            # Multi-turn repair: show the model its JSON and what Prolog found.
            messages += [
                {"role": "assistant", "content": json.dumps(candidate)},
                {"role": "user", "content": "The checker found these problems:\n- "
                 + "\n- ".join(problems) + "\nReturn a corrected full mystery."},
            ]
        raise GenerationFailed(f"Gave up after {self._max_attempts} attempts: {problems}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate verified mysteries")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--out", default="mysteries")
    parser.add_argument("--model", default=BULK_MODEL)
    parser.add_argument("--start", type=int, default=1, help="first file number")
    args = parser.parse_args()
    try:
        llm = ClaudeLLM(model=args.model, effort="medium", max_tokens=16000)
    except LLMError as err:
        raise SystemExit(str(err))
    gen = MysteryGenerator(llm)
    out = Path(args.out)
    for i in range(args.start, args.start + args.count):
        theme = THEMES[(i - 1) % len(THEMES)]
        n_suspects = 4 if i % 2 else 5
        try:
            mystery = gen.generate(theme, n_suspects)
        except (GenerationFailed, LLMError) as err:
            print(f"[{i}] {theme}: FAILED ({err})")
            continue
        path = out / f"gen_{i:03d}.json"
        path.write_text(json.dumps(mystery, indent=2) + "\n")
        print(f"[{i}] {theme}: ok after {gen.attempts_used[-1]} attempt(s) -> {path}")
    print(f"LLM calls: {llm.calls}, tokens in/out: {llm.input_tokens}/{llm.output_tokens}")


if __name__ == "__main__":
    main()
