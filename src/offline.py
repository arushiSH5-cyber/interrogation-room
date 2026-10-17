"""Offline mode: play without an API key.

ScriptedSuspect (src/agents.py) answers with fixed sentences such as
"At 21:00 I was in the kitchen." and "At 21:00 I saw niece in the
library." PatternTranslator reads exactly those sentences with regular
expressions instead of an LLM. Its output still goes through the same
pure pipeline, so the rest of the game cannot tell the difference.
"""

from __future__ import annotations

import re

from . import pipeline

_SELF = re.compile(r"At (\d+):00 I was in the (\w+)\.")
_SAW = re.compile(r"At (\d+):00 I saw (\w+) in the (\w+)\.")


def parse_scripted(speaker: str, answer: str) -> dict:
    """Pure: the scripted sentences -> the same JSON shape the LLM returns."""
    own = [{"person": speaker, "room": room, "hour": int(hour)}
           for hour, room in _SELF.findall(answer)]
    seen = [{"person": person, "room": room, "hour": int(hour)}
            for hour, person, room in _SAW.findall(answer)]
    return {"facts": own + seen}


class PatternTranslator:
    """Same interface as translator.Translator, no LLM needed."""

    def __init__(self, world: pipeline.World) -> None:
        self._world = world

    def translate(self, speaker: str, question: str, answer: str) -> pipeline.Translation:
        return pipeline.translate(parse_scripted(speaker, answer), speaker, self._world)
