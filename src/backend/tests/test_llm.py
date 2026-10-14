"""Tests for the local LLM endpoint."""

from fastapi.testclient import TestClient

from app.api import llm
from app.main import app
from app.services.llm_client import _final_response

client = TestClient(app)


def test_llm_test_returns_model_response(monkeypatch):
    async def fake_generate_response(prompt: str) -> str:
        assert prompt == "Say hello."
        return "Hello!"

    monkeypatch.setattr(llm, "generate_response", fake_generate_response)

    response = client.post("/api/llm/test", json={"prompt": "Say hello."})

    assert response.status_code == 200
    assert response.json() == {"response": "Hello!"}


def test_llm_test_returns_service_unavailable_when_model_is_unreachable(monkeypatch):
    async def fake_generate_response(prompt: str) -> str:
        raise llm.LLMClientError("Ollama is unavailable.")

    monkeypatch.setattr(llm, "generate_response", fake_generate_response)

    response = client.post("/api/llm/test", json={"prompt": "Say hello."})

    assert response.status_code == 503
    assert response.json() == {"detail": "Ollama is unavailable."}


def test_llm_test_rejects_empty_prompt():
    response = client.post("/api/llm/test", json={"prompt": ""})

    assert response.status_code == 422


def test_final_response_removes_reasoning_block():
    content = (
        "<think>Internal reasoning that must not be returned.</think>"
        "Midterm 1: 20%\nmidterm 2: 30%\nfinal:20%"
    )

    assert _final_response(content) == ("Midterm 1: 20%\nmidterm 2: 30%\nfinal:20%")
