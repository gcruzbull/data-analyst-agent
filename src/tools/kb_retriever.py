"""
Cliente para Amazon Bedrock Knowledge Bases.

A diferencia del retriever original (FAISS local + embeddings Ollama), aquí
delegamos toda la búsqueda vectorial a un servicio gestionado:
- Los documentos viven en S3.
- Bedrock genera y almacena los embeddings (Titan v2 o Cohere) en
  OpenSearch Serverless.
- Nosotros solo llamamos a la API `retrieve` con la query del usuario.

Esto desacopla completamente al agente del backend de embeddings y permite
escalar el corpus sin tocar código.
"""
from __future__ import annotations

import logging
from typing import Any

import boto3
from botocore.config import Config

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        s = get_settings()
        _client = boto3.client(
            "bedrock-agent-runtime",
            config=Config(region_name=s.aws_region, retries={"max_attempts": 3, "mode": "adaptive"}),
        )
    return _client


def retrieve_from_kb(query: str, num_results: int | None = None) -> list[dict[str, Any]]:
    """
    Ejecuta una consulta semántica contra la Knowledge Base configurada.

    Returns:
        Lista de chunks: [{"content": str, "source": str, "score": float}]
    """
    s = get_settings()
    if not s.knowledge_base_id:
        raise RuntimeError("KNOWLEDGE_BASE_ID no está configurado.")

    n = num_results or s.kb_num_results
    response = _get_client().retrieve(
        knowledgeBaseId=s.knowledge_base_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {
                "numberOfResults": n,
                # HYBRID combina búsqueda semántica + keyword. Mejor para queries
                # mixtas (terminología técnica + conceptos). Si la KB está sobre
                # un store que no soporta hybrid, AWS hace fallback a SEMANTIC.
                "overrideSearchType": "HYBRID",
            }
        },
    )

    results: list[dict[str, Any]] = []
    for item in response.get("retrievalResults", []):
        results.append({
            "content": item.get("content", {}).get("text", ""),
            "source": item.get("location", {}).get("s3Location", {}).get("uri", ""),
            "score": item.get("score", 0.0),
        })

    logger.info("KB retrieve: query=%r → %d resultados", query, len(results))
    return results