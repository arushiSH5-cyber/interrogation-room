"""End-to-end game tests: offline (scripted) and with fake LLMs."""
import pytest

from src import scenario as sc
from src.game import new_game
from src.offline import parse_scripted
from tests.fakes import FakeLLM

ASHFORD = sc.load("mysteries/ashford_manor.json")


def test_parse_scripted_sentences():
    raw = parse_scripted("maid", "At 21:00 I was in the kitchen. At 21:00 I saw niece in the library.")
    assert raw == {"facts": [{"person": "maid", "room": "kitchen", "hour": 21},
                             {"person": "niece", "room": "library", "hour": 21}]}


def test_offline_game_catches_the_niece():
    game = new_game(ASHFORD, offline=True)
    assert game.ask("maid", "Where were you?").new_contradictions == []
    turn = game.ask("niece", "Where were you?")
    verdicts = sorted(p["verdict"]["type"] for p in turn.new_contradictions)
    assert verdicts == ["lie_by", "one_of_them_lies"]
    board = game.board()
    assert board["accused"] == ["niece"] and board["prime_suspects"] == ["niece"]
    assert game.accuse("niece") and not game.accuse("maid")


def test_contradictions_reported_only_once_and_no_duplicate_facts():
    game = new_game(ASHFORD, offline=True)
    game.ask("maid", "Where were you?")
    game.ask("niece", "Where were you?")
    again = game.ask("niece", "Are you sure?")
    assert again.new_contradictions == []
    assert len(game.board()["testimony"]) == 7       # repeats not re-asserted


def test_new_game_resets_previous_testimony():
    first = new_game(ASHFORD, offline=True)
    first.ask("niece", "Where were you?")
    second = new_game(ASHFORD, offline=True)
    assert second.board()["testimony"] == []


def test_llm_game_flows_answer_through_translator():
    suspect_llm = FakeLLM(chat_replies=["I was in the garden at nine, darling."])
    translator_llm = FakeLLM(json_replies=[
        {"facts": [{"person": "niece", "room": "garden", "hour": 21}]}])
    game = new_game(ASHFORD, suspect_llm, translator_llm=translator_llm)
    turn = game.ask("niece", "Where were you at nine?")
    assert turn.answer.startswith("I was in the garden")
    assert turn.translation.facts == ("says(niece, location(niece, garden, 21))",)
    assert "Detective to niece" in game.transcript_text()


def test_unknown_suspect_and_invalid_scenario():
    game = new_game(ASHFORD, offline=True)
    with pytest.raises(ValueError, match="No suspect"):
        game.ask("ghost", "Boo?")
    with pytest.raises(ValueError, match="Invalid scenario"):
        new_game({**ASHFORD, "culprit": "ghost"}, offline=True)
    with pytest.raises(ValueError, match="LLM is required"):
        new_game(ASHFORD)
