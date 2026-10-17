"""Command-line interrogation.

    python -m src.cli                       # Ashford Manor, real Claude suspects
    python -m src.cli --offline             # scripted suspects, no API key
    python -m src.cli --mystery mysteries/gen_001.json

Type  <suspect>: <question>  to question someone, e.g.
    niece: where were you at nine?
Other commands: board, accuse <suspect>, help, quit
"""

from __future__ import annotations

import argparse

from . import scenario as sc
from .engine import describe_claim, describe_proof
from .game import Game, Turn, new_game
from .llm import ClaudeLLM, LLMError

HELP = """Commands:
  <suspect>: <question>   question a suspect   (e.g.  maid: who did you see at 21:00?)
  board                   show all testimony, evidence and contradictions
  accuse <suspect>        name the murderer (ends the game)
  help                    show this help
  quit                    leave"""


def print_proofs(proofs: list[dict], header: str) -> None:
    for proof in proofs:
        print(f"\n  !! {header}")
        for step in describe_proof(proof):
            print(f"     {step}")


def print_turn(turn: Turn) -> None:
    print(f"\n{turn.suspect}: {turn.answer}")
    for loc in turn.translation.accepted:
        print(f"  + fact: {loc.person} in the {loc.room} at {loc.hour}:00")
    for rej in turn.translation.rejected:
        print(f"  - ignored: {rej.reason}")
    print_proofs(turn.new_contradictions, "CONTRADICTION FOUND")


def print_board(game: Game) -> None:
    board = game.board()
    print("\n=== Evidence board ===")
    for e in board["evidence"]:
        print(f"  [evidence] {e['item']}: {e['person']} in the {e['room']} at {e['hour']}:00")
    for t in board["testimony"]:
        print("  " + describe_claim({"kind": "testimony", **t}))
    print_proofs(board["contradictions"], "contradiction")
    print(f"\n  Prime suspects (motive + means + opportunity): {board['prime_suspects'] or 'none yet'}")
    print(f"  Logic accuses of lying: {board['accused'] or 'nobody yet'}")


def run(game: Game) -> None:
    print("\n" + sc.case_file(game.scenario))
    print("\n" + HELP)
    while True:
        try:
            line = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        command = line.lower()
        if command in ("quit", "exit"):
            return
        if command == "help":
            print(HELP)
        elif command == "board":
            print_board(game)
        elif command.startswith("accuse"):
            name = command.removeprefix("accuse").strip()
            if name not in game.suspect_names:
                print(f"Accuse whom? {', '.join(game.suspect_names)}")
                continue
            culprit = game.scenario["culprit"]
            verdict = "Correct!" if game.accuse(name) else "Wrong."
            print(f"{verdict} The murderer was {culprit}.")
            return
        elif ":" in line:
            name, question = (part.strip() for part in line.split(":", 1))
            try:
                print_turn(game.ask(name.lower(), question))
            except (ValueError, LLMError) as err:
                print(f"  {err}")
        else:
            print("Type  <suspect>: <question>  or  help")


def main() -> None:
    parser = argparse.ArgumentParser(description="Interrogation Room")
    parser.add_argument("--mystery", default="mysteries/ashford_manor.json")
    parser.add_argument("--offline", action="store_true",
                        help="scripted suspects, no API key needed")
    parser.add_argument("--model", default=None, help="Claude model id")
    args = parser.parse_args()
    scenario = sc.load(args.mystery)
    try:
        llm = None if args.offline else ClaudeLLM(model=args.model)
    except LLMError as err:
        raise SystemExit(str(err))
    run(new_game(scenario, llm, offline=args.offline))


if __name__ == "__main__":
    main()
