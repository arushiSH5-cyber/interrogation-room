"""Tests for the Suspect classes (OOP layer), using a fake LLM."""
import pytest

from src import scenario as sc
from src.agents import Culprit, InnocentSuspect, ScriptedSuspect, build_suspects
from tests.fakes import FakeLLM

ASHFORD = sc.load("mysteries/ashford_manor.json")


def test_factory_picks_the_right_class():
    suspects = build_suspects(ASHFORD, FakeLLM())
    assert isinstance(suspects["niece"], Culprit)
    assert all(isinstance(suspects[n], InnocentSuspect) for n in ("butler", "maid", "gardener"))


def test_culprit_prompt_has_cover_story_and_lie_instruction():
    prompt = build_suspects(ASHFORD, FakeLLM())["niece"].persona_prompt()
    assert "You ARE the murderer" in prompt
    assert "claim you were: at 20:00 in the kitchen; at 21:00 in the garden" in prompt


def test_innocent_prompt_has_truth_and_sightings():
    prompt = build_suspects(ASHFORD, FakeLLM())["maid"].persona_prompt()
    assert "did NOT commit" in prompt
    assert "at 20:00 in the kitchen; at 21:00 in the kitchen" in prompt
    assert "niece in the library at 21:00" in prompt


def test_ask_keeps_conversation_memory():
    llm = FakeLLM(chat_replies=["In the kitchen, sir.", "Yes, all evening."])
    maid = build_suspects(ASHFORD, llm)["maid"]
    maid.ask("Where were you at nine?")
    maid.ask("All evening?")
    # The second call sends the whole history so far (memory).
    _, _, messages = llm.calls[1]
    assert [m["content"] for m in messages] == [
        "Where were you at nine?", "In the kitchen, sir.", "All evening?"]
    assert len(maid.transcript) == 4


def test_transcript_is_a_copy():
    maid = build_suspects(ASHFORD, FakeLLM(chat_replies=["Hello."]))["maid"]
    maid.ask("Hi?")
    maid.transcript[0]["content"] = "tampered"
    assert maid.transcript[0]["content"] == "Hi?"


def test_empty_question_rejected():
    with pytest.raises(ValueError):
        build_suspects(ASHFORD, FakeLLM())["maid"].ask("   ")


def test_scripted_culprit_tells_cover_story():
    niece = build_suspects(ASHFORD, None, scripted=True)["niece"]
    assert isinstance(niece, ScriptedSuspect)
    assert niece.ask("Where were you?") == \
        "At 20:00 I was in the kitchen. At 21:00 I was in the garden."
