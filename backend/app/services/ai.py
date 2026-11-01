from typing import Protocol


class AIProvider(Protocol):
    name: str

    def respond(self, prompt: str) -> str: ...


class MockAIProvider:
    name = "mock-development-only"

    def respond(self, prompt: str) -> str:
        return "Mock AI Provider (development only). No model is installed. No maritime advice is generated."
