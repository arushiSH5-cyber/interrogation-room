"""Tests for scenario JSON helpers (pure functions)."""
import copy

import pytest

from src import scenario as sc
from src.engine import PrologEngine

ASHFORD = sc.load("mysteries/ashford_manor.json")


def test_reference_scenario_is_valid():
    assert sc.validate(ASHFORD) == []


@pytest.mark.parametrize("change, expected", [
    (lambda s: s.pop("culprit"), "missing key"),
    (lambda s: s.update(culprit="ghost"), "not a suspect"),
    (lambda s: s["murder"].update(hour=24), "bad hour 24"),
    (lambda s: s["rooms"].append("Grand Hall"), "bad name"),
    (lambda s: s["timeline"].append({"person": "maid", "room": "attic", "hour": 20}), "unknown"),
    (lambda s: s.update(victim="butler"), "victim is also a suspect"),
    (lambda s: s.update(suspects="oops"), "malformed"),
])
def test_validate_catches_problems(change, expected):
    bad = copy.deepcopy(ASHFORD)
    change(bad)
    assert any(expected in p for p in sc.validate(bad))


def test_validate_does_not_mutate():
    before = copy.deepcopy(ASHFORD)
    sc.validate(ASHFORD)
    sc.facts(ASHFORD)
    assert ASHFORD == before


def test_observations_include_roommates_and_sightings():
    assert sc.observations(ASHFORD, "maid") == [
        ("butler", "kitchen", 20), ("butler", "kitchen", 21), ("niece", "library", 21)]
    assert sc.observations(ASHFORD, "gardener") == []


def test_json_scenario_reproduces_stage1_results():
    """Loading the JSON form + the same testimony gives the same answers
    as the hand-written prolog/mystery.pl."""
    engine = PrologEngine()
    engine.load_scenario(sc.facts(ASHFORD))
    engine.assert_facts([
        "says(maid, location(niece, library, 21))",
        "says(niece, location(niece, garden, 21))",
        "says(niece, location(niece, kitchen, 20))",
    ])
    assert engine.prime_suspects() == ["niece"]
    assert engine.proven_liars() == ["niece"]
    engine.reset()


def test_case_file_mentions_evidence_but_not_answer_key():
    text = sc.case_file(ASHFORD)
    assert "torn_glove" in text and "proves: niece was in the study at 20:00" in text
    assert "cover" not in text.lower() and "culprit" not in text.lower()
