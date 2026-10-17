"""Generator tests: the fake LLM returns canned mysteries; Prolog judges them."""
import copy

import pytest

from src import scenario as sc
from src.generator import GenerationFailed, MysteryGenerator, check, scenario_schema
from src.engine import PrologEngine
from tests.fakes import FakeLLM

ASHFORD = sc.load("mysteries/ashford_manor.json")


def broken():
    """Ashford without the glove: nothing places the niece near the weapon."""
    bad = copy.deepcopy(ASHFORD)
    bad["evidence"] = []
    return bad


def test_check_accepts_reference_mystery():
    assert check(ASHFORD, PrologEngine()) == []


def test_check_reports_logic_problems():
    problems = check(broken(), PrologEngine())
    assert "not_exactly_one_prime_suspect([])" in problems


def test_check_reports_shape_problems_before_prolog():
    assert any("missing key" in p for p in check({"title": "x"}, PrologEngine()))


def test_check_leaves_engine_empty():
    engine = PrologEngine()
    check(ASHFORD, engine)
    assert engine.testimony() == [] and engine.evidence() == []


def test_generator_repairs_with_feedback():
    llm = FakeLLM(json_replies=[broken(), ASHFORD])
    gen = MysteryGenerator(llm)
    assert gen.generate("a manor") == ASHFORD
    assert gen.attempts_used == [1 + 1]
    _, _, messages = llm.calls[1]
    assert "not_exactly_one_prime_suspect" in messages[-1]["content"]


def test_generator_gives_up():
    llm = FakeLLM(json_replies=[broken()] * 2)
    with pytest.raises(GenerationFailed):
        MysteryGenerator(llm, max_attempts=2).generate("a manor")


def test_schema_is_strict_everywhere():
    def walk(node):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
            for child in node["properties"].values():
                walk(child)
        elif node.get("type") == "array":
            walk(node["items"])
    walk(scenario_schema())


def test_every_saved_mystery_is_fair():
    """Any mystery file in mysteries/ must pass the Prolog verifier."""
    from pathlib import Path
    engine = PrologEngine()
    for path in sorted(Path("mysteries").glob("*.json")):
        assert check(sc.load(path), engine) == [], path.name
