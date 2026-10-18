"""Language -> logic: turn a suspect's free-text answer into location facts.

The LLM only does the fuzzy part (reading English). Its output is forced
into a strict JSON schema, then the pure pipeline (src/pipeline.py)
checks and converts it. The translator never decides who is lying.
"""

from __future__ import annotations

from . import pipeline
from .llm import LLM

SYSTEM_PROMPT = """\
You translate statements from a murder-mystery interrogation into facts.

Each fact means "PERSON was in ROOM at HOUR" (24-hour clock, whole hours).
Rules:
- Only record places and times the speaker actually CLAIMS (about
  themselves or about someone they say they saw). Ignore guesses,
  questions, hearsay ("X told me..."), denials and vague statements
  with no room or no time.
- "I", "me", "myself" refer to the speaker: {speaker}.
- Convert times to the hour of the evening: "around nine" -> 21,
  "9:30 pm" -> 21. "All evening" means every hour in {hours}.
- Use only these names. People: {persons}. Rooms: {rooms}.
- Suspects often call each other by first name or title. Map them to
  these names:
{people}
- If nothing qualifies, return an empty list.
"""


def fact_schema(world: pipeline.World) -> dict:
    """JSON schema for the reply; enums keep names inside the world."""
    return {
        "type": "object",
        "properties": {
            "facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "person": {"type": "string", "enum": sorted(world.persons)},
                        "room": {"type": "string", "enum": sorted(world.rooms)},
                        "hour": {"type": "integer"},
                    },
                    "required": ["person", "room", "hour"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["facts"],
        "additionalProperties": False,
    }


class Translator:
    """Calls an LLM (injected) and runs its output through the pipeline."""

    def __init__(self, llm: LLM, world: pipeline.World, hours: tuple[int, ...],
                 people: dict[str, str] | None = None):
        """people maps each name to who it is, e.g. {"niece": "Lord
        Ashford's niece, Celia"}, so "Celia" in an answer becomes niece."""
        self._llm = llm
        self._world = world
        self._hours = hours
        self._people = people or {}

    def system_prompt(self, speaker: str) -> str:
        return SYSTEM_PROMPT.format(
            speaker=speaker, hours=list(self._hours),
            persons=", ".join(sorted(self._world.persons)),
            rooms=", ".join(sorted(self._world.rooms)),
            people="\n".join(f"  {name} = {who}" for name, who in sorted(self._people.items()))
                   or "  (no other names)")

    def translate(self, speaker: str, question: str, answer: str) -> pipeline.Translation:
        message = f"Detective asked {speaker}: {question}\n{speaker} answered: {answer}"
        raw = self._llm.json(self.system_prompt(speaker),
                             [{"role": "user", "content": message}],
                             fact_schema(self._world))
        return pipeline.translate(raw, speaker, self._world)
