"""Unit tests for the pure translation pipeline (no LLM, no Prolog)."""
import pytest

from src.pipeline import (Location, Rejected, World, parse, parse_fact,
                          to_atom, to_hour, to_prolog, translate, validate)

WORLD = World(persons=frozenset({"butler", "maid", "niece", "lord_ashford"}),
              rooms=frozenset({"kitchen", "library", "study"}))


@pytest.mark.parametrize("text, atom", [
    ("butler", "butler"),
    ("The Butler", "butler"),
    ("Lord Ashford", "lord_ashford"),
    ("  the old-library ", "old_library"),
    ("", None),
    ("the", None),
    ("9th room", None),       # atoms cannot start with a digit
    (42, None),
])
def test_to_atom(text, atom):
    assert to_atom(text) == atom


@pytest.mark.parametrize("value, hour", [
    (21, 21), ("21", 21), (" 0 ", 0), (21.5, None), (True, None),
    ("nine", None), (None, None), ("-1", None),
])
def test_to_hour(value, hour):
    assert to_hour(value) == hour


def test_parse_accepts_dict_and_json_text():
    assert parse({"facts": []}) == ([], ())
    assert parse('{"facts": [1]}') == ([1], ())


@pytest.mark.parametrize("raw", ["not json", '["a list"]', {"other": 1}, None])
def test_parse_rejects_bad_shapes(raw):
    items, errors = parse(raw)
    assert items == [] and len(errors) == 1


def test_parse_fact_normalises():
    assert parse_fact({"person": "The Maid", "room": "Kitchen", "hour": "21"}) \
        == Location("maid", "kitchen", 21)


@pytest.mark.parametrize("item, reason", [
    ("text", "not an object"),
    ({"person": "maid", "room": "kitchen"}, "missing field(s): hour"),
    ({"person": "", "room": "kitchen", "hour": 1}, "not a usable name"),
    ({"person": "maid", "room": "kitchen", "hour": "late"}, "not a whole number"),
])
def test_parse_fact_rejects(item, reason):
    result = parse_fact(item)
    assert isinstance(result, Rejected) and reason in result.reason


@pytest.mark.parametrize("hour, ok", [(-1, False), (0, True), (23, True), (24, False)])
def test_validate_hour_boundaries(hour, ok):
    result = validate(Location("maid", "kitchen", hour), WORLD)
    assert isinstance(result, Location) == ok


def test_validate_unknown_names():
    assert "unknown person" in validate(Location("ghost", "kitchen", 1), WORLD).reason
    assert "unknown room" in validate(Location("maid", "attic", 1), WORLD).reason


def test_to_prolog():
    assert to_prolog("maid", Location("butler", "kitchen", 21)) \
        == "says(maid, location(butler, kitchen, 21))"


def test_translate_end_to_end_keeps_good_and_reports_bad():
    raw = {"facts": [
        {"person": "maid", "room": "kitchen", "hour": 21},
        {"person": "maid", "room": "kitchen", "hour": 21},     # duplicate
        {"person": "niece", "room": "library", "hour": 21},
        {"person": "maid", "room": "attic", "hour": 21},       # unknown room
        {"person": "maid", "room": "kitchen", "hour": 30},     # bad hour
    ]}
    result = translate(raw, "The Maid", WORLD)
    assert result.facts == ("says(maid, location(maid, kitchen, 21))",
                            "says(maid, location(niece, library, 21))")
    assert len(result.rejected) == 2


def test_translate_rejects_unknown_speaker():
    result = translate({"facts": []}, "stranger", WORLD)
    assert result.facts == () and result.rejected[0].reason == "unknown speaker"


def test_injection_attempt_never_reaches_prolog():
    raw = {"facts": [{"person": "maid), halt, (x", "room": "kitchen", "hour": 1}]}
    result = translate(raw, "maid", WORLD)
    assert result.facts == ()


def test_pipeline_does_not_mutate_input():
    raw = {"facts": [{"person": "Maid", "room": "Kitchen", "hour": "21"}]}
    before = repr(raw)
    translate(raw, "maid", WORLD)
    assert repr(raw) == before
