"""Scenarios (mysteries) stored as JSON, and pure helpers over them.

A scenario is a plain dict (see mysteries/ashford_manor.json). The
functions here only read it: they check it is well-formed, turn it into
Prolog fact strings, and pick out what each character knows. The one
exception is ``load``, which reads a file.
"""

from __future__ import annotations

import json
from pathlib import Path

from .pipeline import MAX_HOUR, MIN_HOUR, World, to_atom

REQUIRED_KEYS = ("title", "setting", "victim", "hours", "rooms", "murder",
                 "suspects", "culprit", "timeline", "sightings",
                 "cover_story", "evidence")


def load(path: str | Path) -> dict:
    """Read a scenario JSON file (the only function here that does I/O)."""
    return json.loads(Path(path).read_text())


# ---- simple views -------------------------------------------------------

def suspect_names(s: dict) -> list[str]:
    return [p["name"] for p in s["suspects"]]


def world(s: dict) -> World:
    """Everyone (suspects + victim) and every room, for the pipeline."""
    return World(persons=frozenset(suspect_names(s) + [s["victim"]]),
                 rooms=frozenset(s["rooms"]))


def profile(s: dict, name: str) -> dict:
    return next(p for p in s["suspects"] if p["name"] == name)


# ---- validation ---------------------------------------------------------

def _is_atom(x) -> bool:
    return isinstance(x, str) and to_atom(x) == x


def _is_hour(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool) and MIN_HOUR <= x <= MAX_HOUR


def validate(s: dict) -> list[str]:
    """Structural problems with a scenario ([] means it is well-formed).

    This checks shape and names only. Whether the mystery is FAIR (one
    solution, culprit catchable) is a logic question, answered by
    prolog/verify.pl in Stage 6.
    """
    missing = [k for k in REQUIRED_KEYS if k not in s]
    if missing:
        return [f"missing key(s): {', '.join(missing)}"]
    try:
        names = suspect_names(s)
        people = set(names) | {s["victim"]}
        rooms = set(s["rooms"])
        m = s["murder"]
        problems = (
            [f"bad name '{n}'" for n in names + [s["victim"]] + s["rooms"]
             + [m["weapon"]] if not _is_atom(n)]
            + [f"bad hour {h}" for h in s["hours"] + [m["hour"]] if not _is_hour(h)]
            + (["duplicate suspect names"] if len(names) != len(set(names)) else [])
            + (["victim is also a suspect"] if s["victim"] in names else [])
            + ([f"culprit '{s['culprit']}' is not a suspect"]
               if s["culprit"] not in names else [])
            + [f"murder/weapon room '{r}' unknown"
               for r in (m["room"], m["weapon_room"]) if r not in rooms]
            + [f"bad motive for {p['name']}" for p in s["suspects"]
               if p.get("motive") and not _is_atom(p["motive"])]   # "" / None = no motive
            + [f"timeline entry {e} uses unknown names or hour"
               for e in s["timeline"]
               if e["person"] not in people or e["room"] not in rooms or not _is_hour(e["hour"])]
            + [f"sighting {e} uses unknown names or hour"
               for e in s["sightings"]
               if e["witness"] not in names or e["person"] not in people
               or e["room"] not in rooms or not _is_hour(e["hour"])]
            + [f"cover story entry {e} uses unknown room or hour"
               for e in s["cover_story"] if e["room"] not in rooms or not _is_hour(e["hour"])]
            + [f"evidence {e.get('item')} uses unknown names or hour"
               for e in s["evidence"]
               if not _is_atom(e["item"]) or e["person"] not in people
               or e["room"] not in rooms or not _is_hour(e["hour"])]
        )
    except (KeyError, TypeError) as err:     # wrong nesting / wrong types
        return [f"malformed scenario: {err!r}"]
    return problems


# ---- to Prolog ------------------------------------------------------------

def facts(s: dict) -> list[str]:
    """All Prolog facts for a VALIDATED scenario (case file + answer key)."""
    m, v = s["murder"], s["victim"]
    loc = "location({person}, {room}, {hour})".format
    return (
        [f"person({p})" for p in suspect_names(s) + [v]]
        + [f"room({r})" for r in s["rooms"]]
        + [f"victim({v})",
           f"murder({v}, {m['room']}, {m['hour']})",
           f"weapon_kept({m['weapon']}, {m['weapon_room']})"]
        + [f"motive({p['name']}, {p['motive']})"
           for p in s["suspects"] if p.get("motive")]
        + [f"evidence({loc(**e_loc(e))}, {e['item']})" for e in s["evidence"]]
        # answer key -- only prolog/verify.pl reads these
        + [f"culprit({s['culprit']})"]
        + [f"true_location({e['person']}, {e['room']}, {e['hour']})" for e in s["timeline"]]
        + [f"saw({e['witness']}, {e['person']}, {e['room']}, {e['hour']})"
           for e in s["sightings"]]
        + [f"cover_story({s['culprit']}, {e['room']}, {e['hour']})"
           for e in s["cover_story"]]
    )


def e_loc(e: dict) -> dict:
    return {"person": e["person"], "room": e["room"], "hour": e["hour"]}


# ---- what each character knows ------------------------------------------

def true_whereabouts(s: dict, name: str) -> list[tuple[str, int]]:
    """[(room, hour), ...] where this person really was, by hour."""
    return sorted(((e["room"], e["hour"]) for e in s["timeline"]
                   if e["person"] == name), key=lambda rh: rh[1])


def observations(s: dict, name: str) -> list[tuple[str, str, int]]:
    """[(person, room, hour), ...] this person saw: explicit sightings,
    plus everyone who was in the same room at the same hour."""
    mine = set(true_whereabouts(s, name))
    shared = {(e["person"], e["room"], e["hour"]) for e in s["timeline"]
              if e["person"] != name and (e["room"], e["hour"]) in mine}
    seen = {(e["person"], e["room"], e["hour"]) for e in s["sightings"]
            if e["witness"] == name}
    return sorted(shared | seen, key=lambda prh: (prh[2], prh[0]))


def cover_story(s: dict) -> list[tuple[str, int]]:
    return sorted(((e["room"], e["hour"]) for e in s["cover_story"]),
                  key=lambda rh: rh[1])


def case_file(s: dict) -> str:
    """What the detective (player, judge, LLM detective) is told up front."""
    m = s["murder"]
    lines = [
        s["title"], s["setting"],
        f"Victim: {s['victim']}, killed in the {m['room']} at {m['hour']}:00 "
        f"with the {m['weapon']} (normally kept in the {m['weapon_room']}).",
        f"Rooms: {', '.join(s['rooms'])}. Hours of interest: {s['hours']}.",
        "Suspects:",
        *[f"  - {p['name']}: {p['role']}"
          + (f" (motive: {p['motive']})" if p.get("motive") else "")
          for p in s["suspects"]],
        "Physical evidence (always true):",
        *[f"  - {e['item']}: {e['description']} (proves: {e['person']} was "
          f"in the {e['room']} at {e['hour']}:00)" for e in s["evidence"]],
    ]
    return "\n".join(lines)
