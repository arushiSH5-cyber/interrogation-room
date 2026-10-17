"""Smoke test for the Streamlit UI (headless, offline mode)."""
from streamlit.testing.v1 import AppTest


def test_offline_game_in_the_browser_ui(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    at = AppTest.from_file("../app/streamlit_app.py", default_timeout=30).run()
    assert not at.exception
    at.radio[0].set_value("niece").run()
    at.chat_input[0].set_value("Where were you?").run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "evidence cannot lie, so niece lied" in text
    assert at.metric[1].value == "niece"          # logic accuses the niece
