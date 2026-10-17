"""Python <-> Prolog bridge.

Python never decides what is true. It only hands facts to SWI-Prolog
(through pyswip), asks questions, and converts the answers into plain
Python data (str, int, list, dict) so the rest of the program does not
need to know anything about pyswip.

Important: pyswip talks to ONE embedded Prolog process. Every
PrologEngine object therefore shares the same fact database; calling
``load_scenario`` / ``reset`` replaces the facts for everyone.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple

from pyswip import Atom, Functor, Prolog, Variable

PROLOG_DIR = Path(__file__).resolve().parent.parent / "prolog"

# Reasoning files, loaded once. They hold no scenario data.
LOGIC_FILES = ("schema.pl", "rules.pl", "contradictions.pl", "detective.pl",
               "verify.pl")

# Every scenario predicate (see prolog/schema.pl) as name/arity.
# reset() wipes all of them before a new mystery is loaded.
SCENARIO_PREDICATES = (
    "person/1", "room/1", "victim/1", "murder/3", "weapon_kept/2",
    "motive/2", "evidence/2", "says/2",
    "culprit/1", "true_location/3", "saw/4", "cover_story/3",
)


class Term(NamedTuple):
    """A Prolog compound term such as location(niece, study, 20)."""
    name: str
    args: tuple


def to_python(value: Any) -> Any:
    """Recursively turn a raw pyswip value into plain Python data.

    atoms -> str, numbers -> int/float, lists -> list,
    compound terms -> Term(name, args), unbound variables -> None.
    """
    if isinstance(value, Functor):
        return Term(str(value.name), tuple(to_python(a) for a in value.args))
    if isinstance(value, Atom):
        return str(value)
    if isinstance(value, bytes):          # Prolog strings arrive as bytes
        return value.decode()
    if isinstance(value, list):
        return [to_python(v) for v in value]
    if isinstance(value, Variable):
        return None
    return value                          # int / float


def claim_to_dict(claim: Term) -> dict:
    """said(S, location(P,R,H)) or evidence(location(P,R,H), Item) -> dict."""
    if claim.name == "said":
        speaker, fact = claim.args
        source = {"kind": "testimony", "speaker": speaker}
    else:  # evidence
        fact, item = claim.args
        source = {"kind": "evidence", "item": item}
    person, room, hour = fact.args
    return {**source, "person": person, "room": room, "hour": hour}


def verdict_to_dict(verdict: Any) -> dict:
    """lie_by(S) / self_contradiction(S) / one_of_them_lies(A, B) -> dict."""
    if isinstance(verdict, str):          # e.g. inconsistent_evidence
        return {"type": verdict, "suspects": []}
    return {"type": verdict.name, "suspects": list(verdict.args)}


def proof_to_dict(proof: list) -> dict:
    """Convert explain/3's proof list into a dict.

    Prolog proof: [claim(A), claim(B), breaks(Reason), verdict(V)]
    """
    claim_a, claim_b, breaks, verdict = (step.args[0] for step in proof)
    return {
        "claim_a": claim_to_dict(claim_a),
        "claim_b": claim_to_dict(claim_b),
        "rule": breaks.name,                   # e.g. one_place_at_a_time
        "rule_args": list(breaks.args),
        "verdict": verdict_to_dict(verdict),
    }


def describe_claim(c: dict) -> str:
    """One readable line for a claim dict."""
    where = f"{c['person']} was in the {c['room']} at {c['hour']}:00"
    if c["kind"] == "testimony":
        return f"{c['speaker']} said: {where}"
    return f"evidence ({c['item']}): {where}"


def describe_proof(p: dict) -> list[str]:
    """Turn a proof dict into numbered, human-readable steps."""
    v = p["verdict"]
    who = " and ".join(v["suspects"])
    verdicts = {
        "lie_by": f"evidence cannot lie, so {who} lied",
        "self_contradiction": f"{who} contradicted themselves",
        "one_of_them_lies": f"one of {who} is lying",
    }
    return [
        f"1. {describe_claim(p['claim_a'])}",
        f"2. {describe_claim(p['claim_b'])}",
        f"3. rule broken: {p['rule']}({', '.join(map(str, p['rule_args']))})",
        f"4. verdict: {verdicts.get(v['type'], v['type'])}",
    ]


class PrologEngine:
    """Thin object wrapper around the embedded SWI-Prolog database."""

    _prolog: Prolog | None = None   # shared by all instances (one process)
    resets = 0                      # bumped on every reset, so owners can tell

    def __init__(self) -> None:
        if PrologEngine._prolog is None:
            prolog = Prolog()
            for name in LOGIC_FILES:
                prolog.consult(str(PROLOG_DIR / name))
            PrologEngine._prolog = prolog
        self._p = PrologEngine._prolog

    # ---- changing the database -------------------------------------
    def assert_fact(self, fact: str) -> None:
        """Add one fact, e.g. 'says(maid, location(maid, kitchen, 21))'.

        The string must already be validated (src/pipeline.py does
        that), because it is handed to Prolog as code.
        """
        self._p.assertz(fact)

    def retract_fact(self, fact: str) -> bool:
        """Remove one matching fact. Returns False if none matched."""
        return self.ask(f"retract({fact})")

    def assert_facts(self, facts: list[str]) -> None:
        for fact in facts:
            self.assert_fact(fact)

    def reset(self) -> None:
        """Forget the current scenario and all testimony."""
        PrologEngine.resets += 1
        for pred in SCENARIO_PREDICATES:
            name, arity = pred.split("/")
            blanks = ", ".join(["_"] * int(arity))
            self.ask(f"retractall({name}({blanks}))")

    def load_scenario(self, facts: list[str]) -> None:
        """Replace the whole database with a new scenario's facts."""
        self.reset()
        self.assert_facts(facts)

    def consult(self, path: str | Path) -> None:
        """Load a .pl scenario file such as prolog/mystery.pl."""
        self._p.consult(str(path))

    # ---- asking questions --------------------------------------------
    def ask(self, goal: str) -> bool:
        """True if the goal has at least one solution."""
        return any(True for _ in self._p.query(goal, maxresult=1))

    def findall(self, template: str, goal: str) -> list:
        """All solutions of goal, each shaped like template, as Python data.

        Example: findall("P", "prime_suspect(P)") -> ["niece"]
        We let Prolog collect the answers with findall/3 and read back
        the single variable Out__, which is always the last binding.
        """
        query = f"findall({template}, ({goal}), Out__)"
        bindings = next(iter(self._p.query(query, normalize=False)))
        out = bindings[-1]                     # the =(Out__, Value) pair
        return to_python(out.args[1])

    # ---- game-level questions ----------------------------------------
    def prime_suspects(self) -> list[str]:
        return self.findall("Ps", "prime_suspects(Ps)")[0]

    def proven_liars(self) -> list[str]:
        return sorted(set(self.findall("S", "proven_liar(S)")))

    def accused(self) -> list[str]:
        """Who the logic accuses of lying (prolog/detective.pl)."""
        return self.findall("L", "accused_list(L)")[0]

    def verify(self) -> list[str]:
        """Problems with the loaded mystery (prolog/verify.pl); [] = fair."""
        return self.findall("T", "verify_mystery(Ps), member(P, Ps), "
                                 "term_to_atom(P, T)")

    def testimony(self) -> list[dict]:
        """Every says/2 fact as {'speaker', 'person', 'room', 'hour'}."""
        rows = self.findall("t(S,P,R,H)", "says(S, location(P,R,H))")
        return [dict(zip(("speaker", "person", "room", "hour"), r.args))
                for r in rows]

    def evidence(self) -> list[dict]:
        rows = self.findall("e(I,P,R,H)", "evidence(location(P,R,H), I)")
        return [dict(zip(("item", "person", "room", "hour"), r.args))
                for r in rows]

    def contradictions(self) -> list[dict]:
        """Every contradiction with its proof, as dicts (see proof_to_dict)."""
        return [proof_to_dict(p) for p in self.findall("P", "explain(_, _, P)")]
