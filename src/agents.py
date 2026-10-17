"""Suspects as objects (the object-oriented part of the project).

Each Suspect keeps PRIVATE state -- where they really were, what they
saw, their secret, how they feel about the others, and the conversation
so far -- in underscore attributes. Other code can only interact with a
suspect through its public methods (``ask``, ``name``, ``role``,
``transcript``), the way a detective can only learn things by asking.

Class hierarchy (inheritance + polymorphism):

    Suspect                 shared state, memory, prompt building
    ├── InnocentSuspect     tells the truth about where they were
    ├── Culprit             lies, sticking to a cover story
    └── ScriptedSuspect     offline stand-in: fixed sentences, no LLM

``ask`` is written once in Suspect; each subclass only overrides the
small hook it needs (``_role_instructions`` or ``_reply``).
"""

from __future__ import annotations

from . import scenario as sc
from .llm import LLM

PERSONA_PROMPT = """\
You are role-playing a suspect in a murder-mystery interrogation game.

Setting: {setting}
The victim, {victim}, was found dead in the {murder_room} at {murder_hour}:00.

You are {name}, {role}. Personality: {personality}.
How you feel about others: {relationships}.
A private secret (unrelated to the murder unless stated): {secret}

{role_instructions}

Style: stay in character, answer in 1-4 sentences of natural speech, and
use clock times (e.g. "around nine" or "at 21:00") and room names when
you talk about where people were. Never mention that you are an AI or
that this is a game.
"""


def _places(entries) -> str:
    return "; ".join(f"at {h}:00 in the {r}" for r, h in entries) or "nowhere notable"


def _sightings(entries) -> str:
    return "; ".join(f"{p} in the {r} at {h}:00" for p, r, h in entries) or "nobody"


class Suspect:
    """Base class: one character the detective can question."""

    def __init__(self, profile: dict, scenario: dict, llm: LLM | None) -> None:
        self._name = profile["name"]
        self._role = profile["role"]
        self._personality = profile["personality"]
        self._secret = profile["secret"]
        self._relationships = tuple((r["person"], r["feeling"])
                                    for r in profile.get("relationships", []))
        self._whereabouts = tuple(sc.true_whereabouts(scenario, self._name))
        self._seen = tuple(sc.observations(scenario, self._name))
        self._scene = scenario                # shared, public setting info
        self._llm = llm
        self._memory: list[dict] = []         # the conversation so far

    # ---- public interface ------------------------------------------------
    @property
    def name(self) -> str:
        return self._name

    @property
    def role(self) -> str:
        return self._role

    @property
    def transcript(self) -> tuple[dict, ...]:
        """A read-only copy of the conversation (callers cannot edit memory)."""
        return tuple(dict(m) for m in self._memory)

    def ask(self, question: str) -> str:
        """Answer one question in character and remember the exchange."""
        question = question.strip()
        if not question:
            raise ValueError("Ask the suspect something.")
        self._memory.append({"role": "user", "content": question})
        answer = self._reply()
        self._memory.append({"role": "assistant", "content": answer})
        return answer

    def persona_prompt(self) -> str:
        m = self._scene["murder"]
        return PERSONA_PROMPT.format(
            setting=self._scene["setting"], victim=self._scene["victim"],
            murder_room=m["room"], murder_hour=m["hour"],
            name=self._name, role=self._role, personality=self._personality,
            relationships="; ".join(f"{p}: {f}" for p, f in self._relationships) or "none",
            secret=self._secret, role_instructions=self._role_instructions())

    # ---- hooks for subclasses ----------------------------------------
    def _role_instructions(self) -> str:
        raise NotImplementedError

    def _reply(self) -> str:
        """Ask the LLM for the next line, given the whole conversation."""
        return self._llm.chat(self.persona_prompt(), list(self._memory))


class InnocentSuspect(Suspect):
    """Did not commit the murder; tells the truth about places and times."""

    def _role_instructions(self) -> str:
        return (
            "You did NOT commit the murder.\n"
            f"Where you really were: {_places(self._whereabouts)}.\n"
            f"Who you saw: {_sightings(self._seen)}.\n"
            "Always tell the truth about where you were and whom you saw. "
            "You may be cagey about your private secret, but never invent "
            "false places or times."
        )


class Culprit(Suspect):
    """Committed the murder; lies convincingly using a cover story."""

    def __init__(self, profile: dict, scenario: dict, llm: LLM | None) -> None:
        super().__init__(profile, scenario, llm)
        self._cover_story = tuple(sc.cover_story(scenario))

    def _role_instructions(self) -> str:
        return (
            "You ARE the murderer, and you must not be caught.\n"
            f"Where you really were (keep this hidden): {_places(self._whereabouts)}.\n"
            f"Your cover story -- claim you were: {_places(self._cover_story)}.\n"
            "Lie convincingly: stick to the cover story, stay consistent with "
            "what you said earlier, sound natural, and never confess. Do not "
            "volunteer details that are not part of the cover story."
        )


class ScriptedSuspect(Suspect):
    """Offline stand-in used without an API key: answers with fixed
    sentences built from what it will claim (no LLM call)."""

    def __init__(self, profile: dict, scenario: dict, claims, seen) -> None:
        super().__init__(profile, scenario, llm=None)
        self._claims = tuple(claims)          # (room, hour) it will state
        self._claimed_seen = tuple(seen)      # (person, room, hour)

    def _role_instructions(self) -> str:
        return "(scripted)"

    def _reply(self) -> str:
        parts = [f"At {h}:00 I was in the {r}." for r, h in self._claims]
        parts += [f"At {h}:00 I saw {p} in the {r}." for p, r, h in self._claimed_seen]
        return " ".join(parts) or "I don't remember anything useful."


def build_suspects(scenario: dict, llm: LLM | None, scripted: bool = False) -> dict[str, Suspect]:
    """Create one Suspect object per suspect in the scenario (a factory).

    The culprit gets the Culprit class, everyone else InnocentSuspect;
    with ``scripted=True`` everyone is a ScriptedSuspect instead.
    """
    suspects: dict[str, Suspect] = {}
    for prof in scenario["suspects"]:
        name = prof["name"]
        guilty = name == scenario["culprit"]
        if scripted:
            claims = sc.cover_story(scenario) if guilty else sc.true_whereabouts(scenario, name)
            seen = [] if guilty else sc.observations(scenario, name)
            suspects[name] = ScriptedSuspect(prof, scenario, claims, seen)
        else:
            cls = Culprit if guilty else InnocentSuspect
            suspects[name] = cls(prof, scenario, llm)
    return suspects
