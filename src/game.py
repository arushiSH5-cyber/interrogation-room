"""One game of Interrogation Room: suspects + translator + Prolog.

After every answer the game runs the full loop:

    suspect.ask  ->  translator.translate  ->  engine.assert  ->  engine.contradictions

and reports any contradiction it has not reported before, with its proof.
The Game object only coordinates; it never decides who is lying.
"""

from __future__ import annotations

import json
from typing import NamedTuple

from . import scenario as sc
from .agents import Suspect, build_suspects
from .engine import PrologEngine
from .llm import LLM
from .offline import PatternTranslator
from .pipeline import Translation
from .translator import Translator


class Turn(NamedTuple):
    """Everything that happened for one question."""
    suspect: str
    question: str
    answer: str
    translation: Translation
    new_contradictions: list[dict]


def proof_key(proof: dict) -> str:
    """A stable id for a contradiction, so each is reported only once."""
    return json.dumps([proof["claim_a"], proof["claim_b"]], sort_keys=True)


class Game:
    """Holds the state of one interrogation."""

    def __init__(self, scenario: dict, suspects: dict[str, Suspect],
                 translator, engine: PrologEngine | None = None) -> None:
        problems = sc.validate(scenario)
        if problems:
            raise ValueError("Invalid scenario: " + "; ".join(problems))
        self.scenario = scenario
        self._suspects = suspects
        self._translator = translator
        self._engine = engine or PrologEngine()
        self._reported: set[str] = set()
        self.turns: list[Turn] = []
        self._loaded_at = -1
        self.activate()

    def activate(self) -> None:
        """Make sure the shared Prolog database holds THIS game's facts."""
        # pyswip has ONE Prolog database per process. If another game (a
        # second browser tab) or the generator reset it since we loaded,
        # reload our scenario and replay our testimony.
        if self._loaded_at == PrologEngine.resets:
            return
        self._engine.load_scenario(sc.facts(self.scenario))
        for turn in self.turns:
            self._add_testimony(turn.translation.facts)
        self._loaded_at = PrologEngine.resets

    def _add_testimony(self, facts) -> None:
        for fact in facts:
            if not self._engine.ask(fact):        # skip repeats of known testimony
                self._engine.assert_fact(fact)

    @property
    def suspect_names(self) -> list[str]:
        return list(self._suspects)

    def role(self, name: str) -> str:
        return self._suspects[name].role

    def ask(self, name: str, question: str) -> Turn:
        """Question one suspect and update the evidence board."""
        if name not in self._suspects:
            raise ValueError(f"No suspect called '{name}'. "
                             f"Choose from: {', '.join(self._suspects)}")
        answer = self._suspects[name].ask(question)
        translation = self._translator.translate(name, question, answer)
        self.activate()
        self._add_testimony(translation.facts)
        new = [p for p in self._engine.contradictions()
               if proof_key(p) not in self._reported]
        self._reported.update(proof_key(p) for p in new)
        turn = Turn(name, question, answer, translation, new)
        self.turns.append(turn)
        return turn

    def board(self) -> dict:
        """Everything the evidence board shows, as plain data."""
        self.activate()
        return {
            "testimony": self._engine.testimony(),
            "evidence": self._engine.evidence(),
            "contradictions": self._engine.contradictions(),
            "prime_suspects": self._engine.prime_suspects(),
            "accused": self._engine.accused(),
        }

    def accuse(self, name: str) -> bool:
        """True if the player named the real culprit."""
        return name == self.scenario["culprit"]

    def transcript_text(self) -> str:
        """The whole interrogation as plain text (for LLM judges in Stage 7)."""
        return "\n".join(f"Detective to {t.suspect}: {t.question}\n{t.suspect}: {t.answer}"
                         for t in self.turns)


def new_game(scenario: dict, llm: LLM | None = None, offline: bool = False,
             translator_llm: LLM | None = None) -> Game:
    """Build a ready-to-play game.

    offline=True  -> scripted suspects + regex translator (no API key)
    otherwise     -> LLM suspects; translator uses translator_llm or llm
    """
    world = sc.world(scenario)
    if offline:
        return Game(scenario, build_suspects(scenario, None, scripted=True),
                    PatternTranslator(world))
    if llm is None:
        raise ValueError("An LLM is required unless offline=True.")
    translator = Translator(translator_llm or llm, world, tuple(scenario["hours"]))
    return Game(scenario, build_suspects(scenario, llm), translator)
