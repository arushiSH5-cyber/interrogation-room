"""Functional pipeline: raw translator output -> safe Prolog fact strings.

    parse  ->  validate  ->  transform
    (JSON)     (World)       ("says(maid, location(maid, kitchen, 21))")

Every function here is PURE: it only looks at its arguments, never
changes them, never prints, never touches Prolog or the network, and
always returns the same output for the same input. That makes each step
easy to test on its own and easy to chain together.

Bad input is never thrown away silently: each step returns either a
good value or a ``Rejected(item, reason)`` record, and ``translate``
reports both lists.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, NamedTuple

MIN_HOUR, MAX_HOUR = 0, 23              # 24-hour clock, inclusive
_ATOM = re.compile(r"^[a-z][a-z0-9_]*$")  # a safe, unquoted Prolog atom


@dataclass(frozen=True)
class World:
    """The names a fact may use (frozen = cannot be changed after creation)."""
    persons: frozenset[str]
    rooms: frozenset[str]


class Location(NamedTuple):
    """location(Person, Room, Hour) as an immutable Python value."""
    person: str
    room: str
    hour: int


class Rejected(NamedTuple):
    """An input that failed a step, and why."""
    item: Any
    reason: str


class Translation(NamedTuple):
    """Final pipeline result for one answer."""
    facts: tuple[str, ...]          # Prolog strings ready to assert
    accepted: tuple[Location, ...]
    rejected: tuple[Rejected, ...]


# ---- small helpers ----------------------------------------------------

def to_atom(text: Any) -> str | None:
    """Normalise a name to a Prolog atom: 'The Old Library' -> 'old_library'.

    Returns None if nothing usable is left (empty, starts with a digit,
    not a string).
    """
    if not isinstance(text, str):
        return None
    words = re.sub(r"[^a-z0-9]+", " ", text.lower()).split()
    if words[:1] == ["the"]:
        words = words[1:]
    atom = "_".join(words)
    return atom if _ATOM.match(atom) else None


def to_hour(value: Any) -> int | None:
    """Accept 21 or "21"; reject 21.5, True, "nine", None."""
    if isinstance(value, bool):           # bool is a subclass of int!
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


# ---- step 1: parse ------------------------------------------------------

def parse(raw: Any) -> tuple[list, tuple[Rejected, ...]]:
    """Read the translator output: a dict (or JSON text) with a 'facts' list."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return [], (Rejected(raw, "not valid JSON"),)
    if not isinstance(raw, dict) or not isinstance(raw.get("facts"), list):
        return [], (Rejected(raw, "expected an object with a 'facts' list"),)
    return raw["facts"], ()


def parse_fact(item: Any) -> Location | Rejected:
    """One raw dict -> Location with normalised fields (not yet checked)."""
    if not isinstance(item, dict):
        return Rejected(item, "fact is not an object")
    missing = {"person", "room", "hour"} - item.keys()
    if missing:
        return Rejected(item, f"missing field(s): {', '.join(sorted(missing))}")
    person, room, hour = to_atom(item["person"]), to_atom(item["room"]), to_hour(item["hour"])
    if person is None or room is None:
        return Rejected(item, "person/room is not a usable name")
    if hour is None:
        return Rejected(item, "hour is not a whole number")
    return Location(person, room, hour)


# ---- step 2: validate ---------------------------------------------------

def validate(loc: Location, world: World) -> Location | Rejected:
    """Check the fact only mentions known people, known rooms, real hours."""
    if loc.person not in world.persons:
        return Rejected(loc, f"unknown person '{loc.person}'")
    if loc.room not in world.rooms:
        return Rejected(loc, f"unknown room '{loc.room}'")
    if not MIN_HOUR <= loc.hour <= MAX_HOUR:
        return Rejected(loc, f"hour {loc.hour} is outside {MIN_HOUR}-{MAX_HOUR}")
    return loc


# ---- step 3: transform --------------------------------------------------

def to_prolog(speaker: str, loc: Location) -> str:
    """Location -> 'says(speaker, location(person, room, hour))'.

    Only ever called on validated values, so every atom is safe to hand
    to Prolog as code (no quotes, spaces or operators can sneak in).
    """
    return f"says({speaker}, location({loc.person}, {loc.room}, {loc.hour}))"


def unique(items: tuple) -> tuple:
    """Drop repeats, keep first-seen order."""
    return tuple(dict.fromkeys(items))


# ---- the whole pipeline -------------------------------------------------

def translate(raw: Any, speaker: str, world: World) -> Translation:
    """parse -> validate -> transform, collecting every rejection."""
    speaker_atom = to_atom(speaker)
    if speaker_atom not in world.persons:
        return Translation((), (), (Rejected(speaker, "unknown speaker"),))

    items, parse_errors = parse(raw)
    checked = [r if isinstance(r, Rejected) else validate(r, world)
               for r in map(parse_fact, items)]
    accepted = unique(tuple(c for c in checked if isinstance(c, Location)))
    rejected = parse_errors + tuple(c for c in checked if isinstance(c, Rejected))
    facts = tuple(to_prolog(speaker_atom, loc) for loc in accepted)
    return Translation(facts, accepted, rejected)
