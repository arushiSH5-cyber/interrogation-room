"""A fake LLM for tests: returns canned replies and records every call."""


class FakeLLM:
    def __init__(self, chat_replies=(), json_replies=()):
        self.chat_replies = list(chat_replies)
        self.json_replies = list(json_replies)
        self.calls = []                       # (method, system, messages)

    def chat(self, system, messages):
        self.calls.append(("chat", system, messages))
        return self.chat_replies.pop(0)

    def json(self, system, messages, schema):
        self.calls.append(("json", system, messages))
        return self.json_replies.pop(0)
