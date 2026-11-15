from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.dependencies import ServiceDependency
from app.schemas.ai import ChatRequest, ChatResponse
from app.services.gemini_agent import chat

router = APIRouter(prefix="/ai", tags=["AgroSat IA"])


@router.post(
    "/chat", summary="Conversar com o assistente AgroSat IA",
    responses={429: {"model": ChatResponse, "description": "Limite local de requisições."}},
)
async def chat_route(request: Request, body: ChatRequest, services: ServiceDependency) -> ChatResponse:
    state = request.app.state
    location = state.boundaries.locate(body.location) if body.location is not None else None
    host = request.client.host if request.client else "unknown"
    if state.gemini is not None and not state.chat_limit.allow(host):
        response = ChatResponse(
            status="rate_limited", answer="Limite de consultas do assistente atingido. Tente em um minuto.",
            location=location,
        )
        return JSONResponse(status_code=429, content=response.model_dump(mode="json"), headers={"Retry-After": "60"})
    return await chat(state.gemini, services.client, services.settings, state.zarc, location, body)
