"""Interrogation Room -- web UI.

    .venv/bin/streamlit run app/streamlit_app.py

Left: chat with one suspect at a time. Right: the live evidence board
(physical evidence, every recorded statement, contradictions with their
Prolog proofs, prime suspects). The page only displays what Game and
Prolog report; it contains no reasoning of its own.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))                     # so `import src...` works

from src import scenario as sc                     # noqa: E402
from src.engine import describe_proof              # noqa: E402
from src.game import Game, new_game                # noqa: E402
from src.llm import ClaudeLLM, LLMError            # noqa: E402

st.set_page_config(page_title="Interrogation Room", page_icon="🔎", layout="wide")


def has_api_key() -> bool:
    try:
        ClaudeLLM()
        return True
    except LLMError:
        return False


def start_game(path: Path, offline: bool) -> None:
    llm = None if offline else ClaudeLLM()
    st.session_state.game = new_game(sc.load(path), llm, offline=offline)
    st.session_state.verdict = None


# ---- sidebar: choose a mystery and a mode ---------------------------------
mysteries = sorted((ROOT / "mysteries").glob("*.json"))
with st.sidebar:
    st.header("Case")
    choice = st.selectbox("Mystery", mysteries, format_func=lambda p: sc.load(p)["title"])
    key_ok = has_api_key()
    offline = st.toggle("Offline (scripted suspects)", value=not key_ok, disabled=not key_ok,
                        help="Without ANTHROPIC_API_KEY in .env only offline mode is available.")
    if st.button("New game", type="primary") or "game" not in st.session_state:
        start_game(choice, offline)
    if not key_ok:
        st.caption("No API key found: suspects answer from a script.")

game: Game = st.session_state.game

with st.sidebar:
    st.divider()
    st.subheader("Accuse")
    accused = st.selectbox("The murderer is…", game.suspect_names, key="accuse_pick")
    if st.button("Make accusation"):
        st.session_state.verdict = (accused, game.accuse(accused))
    if st.session_state.verdict:
        name, right = st.session_state.verdict
        culprit = game.scenario["culprit"]
        (st.success if right else st.error)(
            f"{'Correct' if right else 'Wrong'}: the murderer was {culprit}.")

st.title("🔎 Interrogation Room")
with st.expander("Case file", expanded=not game.turns):
    st.text(sc.case_file(game.scenario))

chat_col, board_col = st.columns([3, 2], gap="large")

# ---- left: interrogation ------------------------------------------------------
with chat_col:
    suspect = st.radio("Question", game.suspect_names, horizontal=True,
                       format_func=lambda n: f"{n}")
    st.caption(game.role(suspect))
    for turn in (t for t in game.turns if t.suspect == suspect):
        st.chat_message("user").write(turn.question)
        st.chat_message("assistant", avatar="🗣️").write(turn.answer)
    question = st.chat_input(f"Ask {suspect} something…")
    if question:
        try:
            with st.spinner(f"{suspect} is thinking…"):
                turn = game.ask(suspect, question)
        except (ValueError, LLMError) as err:
            st.error(str(err))
        else:
            for proof in turn.new_contradictions:
                verdict = describe_proof(proof)[3].removeprefix("4. verdict: ")
                st.toast(f"Contradiction! {verdict}", icon="⚠️")
            st.rerun()

# ---- right: evidence board ------------------------------------------------
with board_col:
    board = game.board()
    st.subheader("Evidence board")
    c1, c2 = st.columns(2)
    c1.metric("Prime suspects", ", ".join(board["prime_suspects"]) or "—")
    c2.metric("Logic accuses", ", ".join(board["accused"]) or "—")

    st.markdown("**Contradictions**")
    if not board["contradictions"]:
        st.caption("None yet. Keep asking about places and times.")
    for proof in board["contradictions"]:
        steps = describe_proof(proof)
        with st.container(border=True):
            st.markdown(f"⚠️ **{steps[3].removeprefix('4. verdict: ')}**")
            st.markdown("  \n".join(steps[:3]))      # two spaces + \n = line break

    st.markdown("**Physical evidence**")
    st.dataframe(board["evidence"], hide_index=True, width="stretch")
    st.markdown("**Statements (as Prolog facts)**")
    if board["testimony"]:
        st.dataframe(board["testimony"], hide_index=True, width="stretch")
    else:
        st.caption("Nothing recorded yet.")
    if game.turns and game.turns[-1].translation.rejected:
        with st.expander("Ignored in the last answer"):
            for rej in game.turns[-1].translation.rejected:
                st.write(f"{rej.reason}: `{rej.item}`")
