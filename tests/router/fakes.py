"""A scripted stand-in for live backends: returns queued answers and records every call it receives."""
from ladder_harness.router.types import ModelResult, Usage


class FakeBackend:
    def __init__(self, answers=None, usage=Usage(1000, 200, 100, 0)):
        self.answers = list(answers or [])
        self.calls = []
        self.usage = usage

    def call(self, c):
        self.calls.append(c)
        data = self.answers.pop(0) if self.answers else {"ok": True}
        if callable(data):
            data = data(c)
        return ModelResult(data, "", self.usage, 0.01, c.model, c.effort, "fake")


def fake_backends(answers=None):
    fb = FakeBackend(answers)
    return fb, {"vertex-gemini": fb, "vertex-claude": fb}
