"""Tests for the Python <-> Prolog bridge (src/engine.py)."""
import pytest

from src.engine import PROLOG_DIR, PrologEngine, describe_proof

FACT = "says(gardener, location(gardener, study, 21))"


@pytest.fixture
def engine():
    """A fresh engine with the Stage 1 mystery (prolog/mystery.pl) loaded."""
    eng = PrologEngine()
    eng.reset()
    eng.consult(PROLOG_DIR / "mystery.pl")
    yield eng
    eng.reset()


def test_prime_suspects_are_plain_strings(engine):
    assert engine.prime_suspects() == ["niece"]


def test_two_contradictions_converted_to_dicts(engine):
    proofs = engine.contradictions()
    assert len(proofs) == 2
    verdicts = sorted(p["verdict"]["type"] for p in proofs)
    assert verdicts == ["lie_by", "one_of_them_lies"]


def test_proof_dict_shape(engine):
    lie = next(p for p in engine.contradictions()
               if p["verdict"]["type"] == "lie_by")
    assert lie["claim_a"] == {"kind": "evidence", "item": "torn_glove",
                              "person": "niece", "room": "study", "hour": 20}
    assert lie["claim_b"]["speaker"] == "niece"
    assert lie["rule"] == "one_place_at_a_time"
    assert lie["verdict"]["suspects"] == ["niece"]
    assert describe_proof(lie)[3] == "4. verdict: evidence cannot lie, so niece lied"


def test_assert_then_retract_changes_answers(engine):
    engine.assert_fact(FACT)
    kinds = [p["verdict"]["type"] for p in engine.contradictions()]
    assert "self_contradiction" in kinds
    assert engine.retract_fact(FACT) is True
    assert engine.retract_fact(FACT) is False      # nothing left to remove
    assert len(engine.contradictions()) == 2


def test_reset_empties_everything(engine):
    engine.reset()
    assert engine.testimony() == []
    assert engine.contradictions() == []
    assert engine.prime_suspects() == []


def test_findall_with_no_solutions_is_empty_list(engine):
    assert engine.findall("X", "person(X), X == nobody") == []


def test_proven_liars(engine):
    assert engine.proven_liars() == ["niece"]
