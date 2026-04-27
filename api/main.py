# This is the main entry point for the FastAPI application. 
# It defines the API endpoints and integrates the agent built in src.agent.agent_graph.

"""
FastAPI app del agente de retail.

Endpoints:
  POST /ask         → pregunta al agente, devuelve respuesta + URLs de gráficos
  GET  /health      → health check para ECS / ALB
  GET  /readiness   → readiness check (verifica acceso a Bedrock)

Diseño:
- Logging estructurado JSON (compatible con CloudWatch).
- CORS configurable.
- El agente se construye una sola vez al arrancar (lifespan).
"""
from __future__ import annotations

import logging
import sys
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.agent.agent_graph import build_agent, run_agent
from src.config.settings import get_settings
from src.llm.llm_factory import get_llm

# ---- Logging -------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    stream=sys.stdout,
)
logger = logging.getLogger("retail_agent.api")


# ---- Lifespan ------------------------------------------------------------- #
agent_singleton = None

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_singleton
    logger.info("Inicializando agente y precargando dataset...")
    # Preconstruir el grafo. La carga del dataset ocurre lazy en la primera tool.
    agent_singleton = build_agent()
    logger.info("Agente listo. Provider=%s, model=%s",
                get_settings().llm_provider, get_settings().bedrock_model_id)
    yield
    logger.info("Apagando app")

app = FastAPI(
    title="Retail Data Analyst Agent",
    version="2.0.0",
    description="Agente ReAct sobre Bedrock Claude con tool-use y RAG.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En prod, restringir a los dominios reales.
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ---- Schemas -------------------------------------------------------------- #
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class AskResponse(BaseModel):
    answer: str
    chart_urls: list[str] = []
    n_iterations: int
    elapsed_seconds: float


# ---- Endpoints ------------------------------------------------------------ #
@app.get("/health")
def health() -> dict[str, str]:
    """Liveness para el ALB de ECS."""
    return {"status": "ok"}


@app.get("/readiness")
def readiness() -> dict[str, Any]:
    """Readiness: verifica que podemos hablar con Bedrock."""
    try:
        # Llamada barata: solo construir el cliente. No invocamos el modelo.
        llm = get_llm()
        return {"status": "ready", "provider": type(llm).__name__}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Readiness check falló")
        raise HTTPException(status_code=503, detail=f"Not ready: {exc}")


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, request: Request) -> AskResponse:
    request_id = request.headers.get("x-request-id", "-")
    logger.info("ask request_id=%s question=%r", request_id, req.question[:200])
    t0 = time.time()

    try:
        result = run_agent(req.question)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error ejecutando agente")
        raise HTTPException(status_code=500, detail=str(exc))

    elapsed = time.time() - t0
    logger.info(
        "ask done request_id=%s iterations=%d elapsed=%.2fs charts=%d",
        request_id, result["n_iterations"], elapsed, len(result["chart_urls"]),
    )

    return AskResponse(
        answer=result["answer"],
        chart_urls=result["chart_urls"],
        n_iterations=result["n_iterations"],
        elapsed_seconds=round(elapsed, 3),
    )


@app.exception_handler(Exception)
async def unhandled_exc(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception")
    return JSONResponse(status_code=500, content={"error": str(exc), "type": type(exc).__name__})  
