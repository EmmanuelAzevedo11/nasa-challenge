from types import SimpleNamespace

import httpx
from google.genai import types

from app.services.gemini_agent import ChatRateLimit
from conftest import ITAPETININGA


def completion(*parts):
    content = types.Content(role="model", parts=list(parts))
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


def test_chat_dispatches_tool_and_returns_backend_sources(make_client):
    async def generate_content(*, model, contents, config):
        if len(contents) == 1:
            return completion(types.Part(
                function_call=types.FunctionCall(name="get_terrain", args={}, id="terrain-call"),
                thought_signature=b"test-signature",
            ))
        part = contents[-1].parts[0].function_response
        assert part.id == "terrain-call" and part.response["elevation_m"] == 663
        assert contents[-2].parts[0].thought_signature == b"test-signature"
        return completion(types.Part(text="A altitude estimada é 663 m."))

    def provider(request):
        assert request.url.host == "api.opentopodata.org"
        return httpx.Response(200, json={"status": "OK", "results": [{"dataset": "srtm90m", "elevation": 663}]})

    with make_client(provider) as client:
        client.app.state.gemini = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        client.app.state.chat_limit = ChatRateLimit(1)
        body = {"message": "Qual a altitude local?", "location": ITAPETININGA}
        response = client.post("/api/v1/ai/chat", json=body)
        limited = client.post("/api/v1/ai/chat", json=body)

    assert response.status_code == 200
    assert response.json()["status"] == "available"
    assert response.json()["sources"][0]["title"] == "Open Topo Data / NASA SRTM"
    assert limited.status_code == 429 and limited.json()["status"] == "rate_limited"


def test_chat_rejects_coordinates_in_model_tool_arguments(make_client):
    async def generate_content(*, model, contents, config):
        if len(contents) == 1:
            return completion(types.Part(function_call=types.FunctionCall(
                name="get_terrain", args={"latitude": -23.4, "url": "https://example.com"}, id="blocked",
            )))
        assert contents[-1].parts[0].function_response.response["status"] == "invalid_parameters"
        return completion(types.Part(text="Não consegui consultar com esses parâmetros."))

    def provider(_):
        raise AssertionError("O modelo enviou argumentos fora do contrato.")

    with make_client(provider) as client:
        client.app.state.gemini = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        response = client.post("/api/v1/ai/chat", json={"message": "Qual a altitude?", "location": ITAPETININGA})
    assert response.json()["status"] == "partial"
    assert response.json()["sources"] == []


def test_chat_handles_missing_key_and_blank_message(make_client):
    with make_client(lambda _: httpx.Response(500)) as client:
        response = client.post("/api/v1/ai/chat", json={"message": "Como usar o AgroSat?"})
        invalid = client.post("/api/v1/ai/chat", json={"message": "  "})
    assert response.json()["status"] == "unavailable"
    assert invalid.status_code == 422
