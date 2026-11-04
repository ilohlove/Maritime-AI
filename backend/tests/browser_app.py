"""Synthetic Playwright harness: real DB/HTTP, mocked OpenAI transport. Never deploy."""

import json
import os

import httpx
from app.core.config import Settings
from app.main import create_app
from app.services.document_ai import ProviderRegistration
from app.services.openai_provider import OpenAIProvider
from openai import OpenAI


def create_e2e_app():
    if os.environ.get("MARITIME_E2E_SYNTHETIC") != "1":
        raise RuntimeError(
            "Test factory requires MARITIME_E2E_SYNTHETIC=1 and a disposable database"
        )
    settings = Settings(openai_api_key="synthetic-browser-test-only")
    app = create_app(settings)

    def handle(request):
        body = json.loads(request.content)
        data = json.loads(body["messages"][1]["content"])
        if "evidence" in data:
            content = {
                "status": "answered",
                "claims": [
                    {
                        "text": "SYNTHETIC SDK RESPONSE: kiểm tra hằng tuần.",
                        "excerpt_id": data["evidence"][0]["excerpt_id"],
                        "quote": "Lifeboat inspections must be performed weekly.",
                    }
                ],
            }
        else:
            content = {
                "english": "lifeboat inspections",
                "vietnamese": "xuồng cứu sinh",
            }
        return httpx.Response(
            200,
            json={
                "id": "synthetic",
                "object": "chat.completion",
                "created": 0,
                "model": settings.openai_model,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(content),
                        },
                    }
                ],
            },
        )

    def factory(model):
        provider = OpenAIProvider(settings, model)
        provider.client.close()
        provider.client = OpenAI(
            api_key="synthetic-browser-test-only",
            max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(handle)),
        )
        return provider

    app.state.document_providers["openai"] = ProviderRegistration(True, factory)
    return app
