"""
Storage de gráficos. Abstrae si el destino es S3 o disco local.

El agente devuelve URLs/paths a las imágenes; nunca las codifica en base64
en la respuesta del usuario porque infla mucho los tokens.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

import boto3

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


def save_chart_bytes(image_bytes: bytes, suggested_name: str) -> str:
    """
    Persiste los bytes de un PNG. Devuelve una referencia consultable
    (URL https si va a S3, ruta absoluta si es local).
    """
    s = get_settings()
    filename = f"{suggested_name}_{uuid.uuid4().hex[:8]}.png"

    if s.chart_storage == "s3":
        if not s.chart_s3_bucket:
            raise RuntimeError("CHART_STORAGE='s3' requiere CHART_S3_BUCKET configurado.")
        client = boto3.client("s3", region_name=s.aws_region)
        key = f"charts/{filename}"
        client.put_object(
            Bucket=s.chart_s3_bucket,
            Key=key,
            Body=image_bytes,
            ContentType="image/png",
        )
        # Pre-signed URL temporal (1 hora). Permite responder sin hacer público el bucket.
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": s.chart_s3_bucket, "Key": key},
            ExpiresIn=3600,
        )
        logger.info("Chart subido a s3://%s/%s", s.chart_s3_bucket, key)
        return url

    # Modo local
    s.chart_local_dir.mkdir(parents=True, exist_ok=True)
    out_path = s.chart_local_dir / filename
    out_path.write_bytes(image_bytes)
    logger.info("Chart guardado localmente en %s", out_path)
    return str(out_path)