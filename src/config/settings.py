"""
Configuración centralizada del agente.

Lee variables de entorno con valores por defecto razonables.
Todas las variables están agrupadas en un dataclass para inyección y testing.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    # ---- LLM provider switch -------------------------------------------------
    # "ollama" para desarrollo local, "bedrock" para AWS
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "bedrock"))

    # ---- Bedrock -------------------------------------------------------------
    # Para Sonnet 3.5 v2 en la mayoría de regiones se requiere el
    # cross-region inference profile (prefix "us." / "eu." / "apac.").
    # Default: us. para clientes en us-east-1 / us-west-2.
    bedrock_model_id: str = field(
        default_factory=lambda: os.getenv(
            "BEDROCK_MODEL_ID",
            "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        )
    )
    bedrock_max_tokens: int = field(default_factory=lambda: int(os.getenv("BEDROCK_MAX_TOKENS", "4096")))
    bedrock_temperature: float = field(default_factory=lambda: float(os.getenv("BEDROCK_TEMPERATURE", "0.0")))

    # ---- AWS -----------------------------------------------------------------
    aws_region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    # En ECS / Lambda la auth viene del IAM role del task; estas envs son
    # solo para desarrollo local. boto3 las recoge automáticamente si existen.

    # ---- Knowledge Base (RAG) ------------------------------------------------
    knowledge_base_id: str | None = field(default_factory=lambda: os.getenv("KNOWLEDGE_BASE_ID"))
    kb_num_results: int = field(default_factory=lambda: int(os.getenv("KB_NUM_RESULTS", "5")))

    # ---- Ollama (modo local) -------------------------------------------------
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3"))
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))

    # ---- Datos ---------------------------------------------------------------
    data_path: Path = field(
        default_factory=lambda: Path(os.getenv("DATA_PATH", str(BASE_DIR / "data" / "dataset_clean.csv")))
    )

    # ---- Storage de gráficos -------------------------------------------------
    # En ECS/Lambda los gráficos se suben a S3; en local se guardan en /tmp.
    chart_storage: str = field(default_factory=lambda: os.getenv("CHART_STORAGE", "local"))  # "local" | "s3"
    chart_s3_bucket: str | None = field(default_factory=lambda: os.getenv("CHART_S3_BUCKET"))
    chart_local_dir: Path = field(
        default_factory=lambda: Path(os.getenv("CHART_LOCAL_DIR", "/tmp/charts"))
    )

    # ---- Agente --------------------------------------------------------------
    max_agent_iterations: int = field(default_factory=lambda: int(os.getenv("MAX_AGENT_ITERATIONS", "8")))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton de Settings."""
    return Settings()
