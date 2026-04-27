"""Carga del dataset de retail con cache en memoria."""
from __future__ import annotations

import logging
from functools import lru_cache

import pandas as pd

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_data() -> pd.DataFrame:
    """
    Carga el dataset Online Retail (UCI) ya limpiado.

    El cache evita reparsear el CSV en cada request del agente.
    En ECS este dataset vive en la imagen Docker o en EFS / S3 montado.
    """
    path = get_settings().data_path
    logger.info("Cargando dataset desde %s", path)

    df = pd.read_csv(path, parse_dates=["InvoiceDate"])

    # Normalizaciones defensivas: el dataset original tiene devoluciones
    # (Quantity < 0) que distorsionan agregaciones de "ventas".
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")

    if "TotalPrice" not in df.columns:
        df["TotalPrice"] = df["Quantity"] * df["UnitPrice"]

    return df

