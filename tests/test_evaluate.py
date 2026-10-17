"""Evaluation harness tests: pure scoring + a full offline run with fakes."""
from pathlib import Path

import pytest

from src import evaluate as ev
from src import scenario as sc
from src.charts import plot_summary

ASHFORD_PATH = Path("mysteries/ashford_manor.json")
ASHFORD = sc.load(ASHFORD_PATH)


class SchemaFakeLLM:
    """Answers by looking at what the schema asks for (no network)."""

    def __init__(self):
        self.calls = 0

    def chat(self, system, messages):
        self.calls += 1
        return "I was in the kitchen all evening."

    def json(self, system, messages, schema):
        self.calls += 1
        props = schema["properties"]
        if "facts" in props:                  # translator
            return {"facts": [{"person": "niece", "room": "garden", "hour": 21}]}
        if "questions" in props:              # detective plan
            return {"questions": [{"suspect": "niece", "question": "Where were you?"}] * 9}
        return {"reasoning": "...", "liars": ["niece", "maid"], "culprit": "niece"}


def test_score_perfect_and_false_alarm():
    perfect = ev.score(ev.Verdict(("niece",), "niece"), ASHFORD)
    assert perfect["culprit_flagged"] == 1 and perfect["exact"] == 1
    assert perfect["false_alarms"] == 0 and perfect["innocents"] == 3
    noisy = ev.score(ev.Verdict(("maid", "niece"), "maid"), ASHFORD)
    assert noisy["false_alarms"] == 1 and noisy["exact"] == 0 and noisy["culprit_correct"] == 0


def test_score_nobody_flagged():
    s = ev.score(ev.Verdict((), None), ASHFORD)
    assert s["culprit_flagged"] == 0 and s["named_culprit"] == ""


@pytest.mark.parametrize("k, n", [(0, 10), (10, 10), (5, 10), (0, 0)])
def test_wilson_stays_in_bounds(k, n):
    lo, hi = ev.wilson(k, n)
    assert 0.0 <= lo <= hi <= 1.0


def test_summarize():
    rows = [{"detector": "prolog", "culprit_flagged": 1, "false_alarms": 0, "innocents": 3,
             "exact": 1, "culprit_correct": 1},
            {"detector": "prolog", "culprit_flagged": 0, "false_alarms": 1, "innocents": 3,
             "exact": 0, "culprit_correct": 0}]
    (s,) = ev.summarize(rows)
    assert s["lie_detection_rate"] == 0.5 and s["false_alarm_rate"] == round(1 / 6, 3)


def test_full_run_with_fakes():
    fake = SchemaFakeLLM()
    record = ev.evaluate_one(ASHFORD_PATH, fake, fake)
    rows = ev.rows_from_record(record, ASHFORD)
    assert [r["detector"] for r in rows] == ["prolog", "judge", "detective"]
    judge = rows[1]
    assert judge["culprit_flagged"] == 1 and judge["false_alarms"] == 1
    # The detective's question budget is enforced.
    assert record["detective_transcript"].count("Detective to") == ev.DETECTIVE_QUESTIONS
    # Every innocent "was in the garden at 21" per the fake translator: noise.
    assert record["noise"] == 3
    assert fake.calls <= ev.planned_calls([ASHFORD])


def test_innocent_misstatements_zero_for_honest_offline_game():
    from src.game import new_game
    game = new_game(ASHFORD, offline=True)
    for name in game.suspect_names:
        game.ask(name, "Where were you?")
    assert ev.innocent_misstatements(game, ASHFORD) == 0
    assert ev.prolog_verdict(game) == ev.Verdict(("niece",), "niece")


def test_charts_are_written(tmp_path):
    summary = [{"detector": d, "mysteries": 2, "lie_detection_rate": 0.5,
                "lie_detection_ci_low": 0.1, "lie_detection_ci_high": 0.9,
                "false_alarm_rate": 0.2, "culprit_accuracy": 1.0} for d in ev.DETECTORS]
    for path in plot_summary(summary, tmp_path):
        assert path.exists() and path.stat().st_size > 0
