"""The one place that talks to Claude.

Everything else in the project depends only on the small ``LLM``
interface below (``chat`` and ``json``). Tests pass in a fake object with
the same two methods, so no test ever needs an API key or the network.
This is dependency injection: callers receive an LLM, they never build
one themselves.
"""

from __future__ import annotations

import json
import os
from typing import Protocol

# Haiku 5.5 is the default everywhere: at $0.10 / $0.50 per million
# input / output tokens a whole game costs well under a cent. For a demo
# with stronger role-play, set IR_MODEL=claude-sonnet-5-5 (20x the price)
# or claude-opus-5-5 (40x) in .env, or pass --model.
DEFAULT_MODEL = "claude-haiku-5-5"
BULK_MODEL = "claude-haiku-5-5"

# Models that accept the server-side refusal fallback ("default" mode).
_FALLBACK_MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1")


class LLM(Protocol):
    """What the rest of the code needs from a language model."""

    def chat(self, system: str, messages: list[dict]) -> str:
        """Return a free-text reply to a conversation."""
        ...

    def json(self, system: str, messages: list[dict], schema: dict) -> dict:
        """Return a reply that matches the JSON schema, already parsed."""
        ...


class LLMError(RuntimeError):
    """The model could not give a usable answer (refusal, cut off, ...)."""


def load_api_key() -> str:
    """Read ANTHROPIC_API_KEY from the environment or a .env file."""
    from dotenv import load_dotenv

    load_dotenv()
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise LLMError(
            "ANTHROPIC_API_KEY is not set. Create a file named .env in the "
            "project root containing:\n  ANTHROPIC_API_KEY=sk-ant-...\n"
            "(.env is gitignored, so the key never gets committed.) "
            "Or run with --offline to use the scripted suspects."
        )
    return key


class ClaudeLLM:
    """LLM implementation backed by the Anthropic Messages API."""

    def __init__(self, model: str | None = None, effort: str = "low",
                 max_tokens: int = 4000, client=None) -> None:
        import anthropic

        from dotenv import load_dotenv

        load_dotenv()          # before reading IR_MODEL, so .env can set it
        self.model = model or os.environ.get("IR_MODEL", DEFAULT_MODEL)
        self.effort = effort
        self.max_tokens = max_tokens
        self._client = client or anthropic.Anthropic(api_key=load_api_key())
        self.calls = 0                 # simple usage counters for evaluation
        self.input_tokens = 0
        self.output_tokens = 0

    def _create(self, system: str, messages: list[dict],
                fmt: dict | None = None) -> str:
        output_config: dict = {"effort": self.effort}
        if fmt is not None:
            output_config["format"] = fmt
        extra = {}
        if self.model in _FALLBACK_MODELS:
            # If a safety classifier declines (murder mysteries can trip
            # one), let the API retry on its recommended fallback model.
            extra = {"extra_headers": {"anthropic-beta": "server-side-fallback-2026-07-01"},
                     "extra_body": {"fallbacks": "default"}}
        import anthropic

        # Turn network / account problems into LLMError, which the CLI, the
        # web app and the evaluation already catch, instead of a traceback
        # in the middle of a game. (The SDK has already retried twice.)
        try:
            response = self._client.messages.create(
                model=self.model, max_tokens=self.max_tokens, system=system,
                messages=messages, output_config=output_config, **extra)
        except anthropic.AuthenticationError:
            raise LLMError("The API key was rejected. Check ANTHROPIC_API_KEY in .env.")
        except anthropic.PermissionDeniedError:
            raise LLMError("This API key can't use that model, or the account has no credit.")
        except anthropic.NotFoundError:
            raise LLMError(f"Unknown model '{self.model}'. Check IR_MODEL / --model.")
        except anthropic.RateLimitError:
            raise LLMError("Rate limited by the API. Wait a minute and try again.")
        except anthropic.APIConnectionError:
            raise LLMError("Could not reach the API. Check your internet connection.")
        except anthropic.APIStatusError as err:
            raise LLMError(f"The API returned an error ({err.status_code}). Try again.")
        self.calls += 1
        self.input_tokens += response.usage.input_tokens
        self.output_tokens += response.usage.output_tokens
        if response.stop_reason == "refusal":
            raise LLMError("The model declined to answer.")
        if response.stop_reason == "max_tokens":
            raise LLMError("The reply was cut off (max_tokens reached).")
        return "".join(b.text for b in response.content if b.type == "text")

    def chat(self, system: str, messages: list[dict]) -> str:
        return self._create(system, messages).strip()

    def json(self, system: str, messages: list[dict], schema: dict) -> dict:
        text = self._create(system, messages,
                            {"type": "json_schema", "schema": schema})
        return json.loads(text)
