"""Translator tests with a fake LLM (no API key needed)."""
from src.pipeline import World
from src.translator import Translator, fact_schema
from tests.fakes import FakeLLM

WORLD = World(frozenset({"maid", "niece"}), frozenset({"kitchen", "library"}))


def test_translator_runs_llm_output_through_pipeline():
    llm = FakeLLM(json_replies=[{"facts": [
        {"person": "maid", "room": "kitchen", "hour": 21},
        {"person": "niece", "room": "library", "hour": 99}]}])
    result = Translator(llm, WORLD, (20, 21)).translate(
        "maid", "Where were you at nine?", "In the kitchen. I saw the niece too.")
    assert result.facts == ("says(maid, location(maid, kitchen, 21))",)
    assert len(result.rejected) == 1
    method, system, messages = llm.calls[0]
    assert method == "json" and "speaker: maid" in system
    assert "In the kitchen" in messages[0]["content"]


def test_schema_restricts_names_to_the_world():
    item = fact_schema(WORLD)["properties"]["facts"]["items"]["properties"]
    assert item["person"]["enum"] == ["maid", "niece"]
    assert item["room"]["enum"] == ["kitchen", "library"]
