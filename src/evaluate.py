"""Stage 7: does logic catch liars better than an LLM?

For every mystery we run one scripted interrogation with LLM suspects,
then compare three detectors on the SAME mystery:

  (a) prolog    -- translate answers to facts, accused_list/1 decides
  (b) judge     -- an LLM reads the same transcript + case file
  (c) detective -- a pure-LLM detective asks its own questions, no Prolog

Ground truth: only the culprit is instructed to lie, so the culprit is
the one "liar". Metrics per detector:
  lie detection rate  = share of mysteries where the culprit was flagged
  false-alarm rate    = flagged innocents / all innocents
  exact               = flagged set is exactly {culprit}
  culprit accuracy    = the named murderer is right

Usage:
    python -m src.evaluate --dry-run       # just print the planned API calls
    python -m src.evaluate                 # run, write results/*.csv + charts
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import NamedTuple

from . import scenario as sc
from .agents import build_suspects
from .game import Game, new_game
from .llm import BULK_MODEL, LLM, ClaudeLLM, LLMError

RESULTS = Path("results")
DETECTORS = ("prolog", "judge", "detective")
DETECTIVE_QUESTIONS = 6          # question budget for the pure-LLM detective

QUESTIONS = (
    "Where exactly were you at each hour from {first}:00 to {last}:00?",
    "Who did you see during that time, and where and when did you see them?",
)


class Verdict(NamedTuple):
    liars: tuple[str, ...]       # who the detector says lied
    culprit: str | None          # who it names as the murderer (None = no idea)


# ---- (a) Prolog ------------------------------------------------------------

def interrogate(scenario: dict, suspect_llm: LLM, translator_llm: LLM) -> Game:
    """Ask every suspect the same fixed questions (one shared transcript)."""
    game = new_game(scenario, suspect_llm, translator_llm=translator_llm)
    hours = scenario["hours"]
    for name in game.suspect_names:
        for q in QUESTIONS:
            game.ask(name, q.format(first=min(hours), last=max(hours)))
    return game


def prolog_verdict(game: Game) -> Verdict:
    board = game.board()
    primes, accused = board["prime_suspects"], board["accused"]
    culprit = primes[0] if len(primes) == 1 else (accused[0] if len(accused) == 1 else None)
    return Verdict(tuple(accused), culprit)


# ---- (b) LLM judge ---------------------------------------------------------

JUDGE_PROMPT = """\
You are an expert judge reviewing a murder-mystery interrogation.
Exactly one suspect is the murderer and lies about where they were; the
others are told to be truthful. Physical evidence is always true.
Decide which suspects lied (contradicted evidence, each other, or
themselves) and who the murderer is.

CASE FILE
{case_file}
"""


def verdict_schema(names: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "reasoning": {"type": "string"},
            "liars": {"type": "array", "items": {"type": "string", "enum": names}},
            "culprit": {"type": "string", "enum": names},
        },
        "required": ["reasoning", "liars", "culprit"],
        "additionalProperties": False,
    }


def judge_verdict(llm: LLM, scenario: dict, transcript: str) -> Verdict:
    names = sc.suspect_names(scenario)
    reply = llm.json(JUDGE_PROMPT.format(case_file=sc.case_file(scenario)),
                     [{"role": "user", "content": "TRANSCRIPT\n" + transcript}],
                     verdict_schema(names))
    return Verdict(tuple(sorted(set(reply["liars"]))), reply["culprit"])


# ---- (c) pure-LLM detective -----------------------------------------------

DETECTIVE_PROMPT = """\
You are a detective solving a murder. Exactly one suspect is the murderer
and will lie; the others tell the truth. Physical evidence is always true.
You have no tools: only your own reasoning.

CASE FILE
{case_file}
"""


def plan_schema(names: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {"questions": {"type": "array", "items": {
            "type": "object",
            "properties": {"suspect": {"type": "string", "enum": names},
                           "question": {"type": "string"}},
            "required": ["suspect", "question"],
            "additionalProperties": False}}},
        "required": ["questions"],
        "additionalProperties": False,
    }


def detective_verdict(llm: LLM, scenario: dict, suspect_llm: LLM) -> tuple[Verdict, str]:
    """The detective plans its own questions, hears the answers, decides."""
    names = sc.suspect_names(scenario)
    system = DETECTIVE_PROMPT.format(case_file=sc.case_file(scenario))
    plan = llm.json(system, [{"role": "user", "content":
                    f"Plan up to {DETECTIVE_QUESTIONS} questions to ask the suspects."}],
                    plan_schema(names))
    suspects = build_suspects(scenario, suspect_llm)   # fresh memories
    lines = [f"Detective to {q['suspect']}: {q['question']}\n"
             f"{q['suspect']}: {suspects[q['suspect']].ask(q['question'])}"
             for q in plan["questions"][:DETECTIVE_QUESTIONS]]
    transcript = "\n".join(lines)
    reply = llm.json(system, [{"role": "user", "content":
                     "Here is what they said:\n" + transcript +
                     "\nWho lied, and who is the murderer?"}], verdict_schema(names))
    return Verdict(tuple(sorted(set(reply["liars"]))), reply["culprit"]), transcript


# ---- scoring (pure) ----------------------------------------------------------

def score(verdict: Verdict, scenario: dict) -> dict:
    culprit = scenario["culprit"]
    innocents = [n for n in sc.suspect_names(scenario) if n != culprit]
    false_alarms = [n for n in verdict.liars if n != culprit]
    return {
        "flagged": ";".join(verdict.liars),
        "named_culprit": verdict.culprit or "",
        "culprit_flagged": int(culprit in verdict.liars),
        "false_alarms": len(false_alarms),
        "innocents": len(innocents),
        "exact": int(set(verdict.liars) == {culprit}),
        "culprit_correct": int(verdict.culprit == culprit),
    }


def innocent_misstatements(game: Game, scenario: dict) -> int:
    """Facts recorded for innocents that are NOT true (agent or translator
    noise). These cause false alarms that are not the detector's fault."""
    culprit = scenario["culprit"]
    count = 0
    for t in game.board()["testimony"]:
        if t["speaker"] == culprit:
            continue
        truth = ({(t["speaker"], r, h) for r, h in sc.true_whereabouts(scenario, t["speaker"])}
                 | set(sc.observations(scenario, t["speaker"])))
        count += (t["person"], t["room"], t["hour"]) not in truth
    return count


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson confidence interval for a proportion (pure)."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def summarize(rows: list[dict]) -> list[dict]:
    """One summary row per detector (pure)."""
    out = []
    for det in DETECTORS:
        rs = [r for r in rows if r["detector"] == det]
        if not rs:
            continue
        n = len(rs)
        caught = sum(r["culprit_flagged"] for r in rs)
        alarms, innocents = sum(r["false_alarms"] for r in rs), sum(r["innocents"] for r in rs)
        lo, hi = wilson(caught, n)
        out.append({
            "detector": det, "mysteries": n,
            "lie_detection_rate": round(caught / n, 3),
            "lie_detection_ci_low": round(lo, 3), "lie_detection_ci_high": round(hi, 3),
            "false_alarm_rate": round(alarms / innocents, 3) if innocents else 0.0,
            "exact_rate": round(sum(r["exact"] for r in rs) / n, 3),
            "culprit_accuracy": round(sum(r["culprit_correct"] for r in rs) / n, 3),
        })
    return out


# ---- running -------------------------------------------------------------

def planned_calls(scenarios: list[dict]) -> int:
    """Upper bound on API calls for a full run."""
    per = [4 * len(s["suspects"]) + 1 + 2 + DETECTIVE_QUESTIONS for s in scenarios]
    return sum(per)


def evaluate_one(path: Path, bulk: LLM, judge: LLM) -> dict:
    """Run all three detectors on one mystery; returns a raw record."""
    scenario = sc.load(path)
    game = interrogate(scenario, bulk, bulk)
    verdicts = {"prolog": prolog_verdict(game),
                "judge": judge_verdict(judge, scenario, game.transcript_text())}
    verdicts["detective"], det_transcript = detective_verdict(judge, scenario, bulk)
    return {
        "mystery": path.stem, "culprit": scenario["culprit"],
        "noise": innocent_misstatements(game, scenario),
        "verdicts": {k: v._asdict() for k, v in verdicts.items()},
        "transcript": game.transcript_text(),
        "detective_transcript": det_transcript,
        "contradictions": game.board()["contradictions"],
    }


def rows_from_record(record: dict, scenario: dict) -> list[dict]:
    return [{"mystery": record["mystery"], "detector": det, "culprit": record["culprit"],
             "noise": record["noise"],
             **score(Verdict(tuple(v["liars"]), v["culprit"]), scenario)}
            for det, v in record["verdicts"].items()]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare lie detectors")
    parser.add_argument("--mysteries", default="mysteries/*.json")
    parser.add_argument("--model", default=BULK_MODEL, help="suspects + translator")
    parser.add_argument("--judge-model", default=BULK_MODEL, help="LLM judge + detective")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    paths = sorted(Path().glob(args.mysteries))
    scenarios = [sc.load(p) for p in paths]
    print(f"{len(paths)} mysteries, at most {planned_calls(scenarios)} API calls "
          f"(suspects/translator: {args.model}, judge/detective: {args.judge_model}).")
    if args.dry_run:
        return
    try:
        bulk = ClaudeLLM(model=args.model, effort="low")
        judge = ClaudeLLM(model=args.judge_model, effort="medium", max_tokens=8000)
    except LLMError as err:
        raise SystemExit(str(err))

    raw_dir = RESULTS / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for path, scenario in zip(paths, scenarios):
        cached = raw_dir / f"{path.stem}.json"      # resume after a crash
        if cached.exists():
            record = json.loads(cached.read_text())
        else:
            try:
                record = evaluate_one(path, bulk, judge)
            except LLMError as err:
                print(f"{path.stem}: skipped ({err})")
                continue
            cached.write_text(json.dumps(record, indent=2))
        rows += rows_from_record(record, scenario)
        print(f"{path.stem}: " + ", ".join(
            f"{d}={record['verdicts'][d]['liars']}" for d in DETECTORS)
            + f" (culprit {record['culprit']})")

    if not rows:
        raise SystemExit("No mystery could be evaluated (see the errors above).")
    summary = summarize(rows)
    write_csv(RESULTS / "eval_runs.csv", rows)
    write_csv(RESULTS / "summary.csv", summary)
    from .charts import plot_summary
    plot_summary(summary, RESULTS)
    for s in summary:
        print(s)
    print(f"API calls: {bulk.calls + judge.calls}; tokens in/out: "
          f"{bulk.input_tokens + judge.input_tokens}/{bulk.output_tokens + judge.output_tokens}")


if __name__ == "__main__":
    main()
