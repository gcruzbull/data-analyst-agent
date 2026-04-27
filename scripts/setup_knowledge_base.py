"""
Script para provisionar la Knowledge Base en Bedrock + OpenSearch Serverless.

Por simplicidad, este script asume que ya tienes:
1. Un bucket S3 con los documentos del dominio retail (PDFs, Markdown, etc.)
2. Un IAM role con permisos para Bedrock KB, OpenSearch Serverless y ese S3.
3. (Opcional) Una colección de OpenSearch Serverless creada con un índice vector.

Si quieres que AWS cree todo automáticamente, usa la consola de Bedrock con
"Quick create vector store" — es lo más sencillo. Este script es la versión
programática para CI/CD.

USO:
    python scripts/setup_knowledge_base.py \\
        --name retail-kb \\
        --role-arn arn:aws:iam::123:role/BedrockKBRole \\
        --collection-arn arn:aws:aoss:us-east-1:123:collection/abc \\
        --index-name retail-vector-index \\
        --s3-bucket mi-bucket-retail-docs

Documentación de referencia:
    https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
import uuid

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Titan Text Embeddings v2: 1024 dimensiones, multilingüe, recomendado para casos
# generales. Cohere Embed v3 también es válido si necesitas mejor reranking.
EMBEDDING_MODEL_ARN_TEMPLATE = "arn:aws:bedrock:{region}::foundation-model/amazon.titan-embed-text-v2:0"


def create_kb(
    name: str,
    role_arn: str,
    collection_arn: str,
    index_name: str,
    region: str,
    description: str = "Retail domain knowledge base",
) -> str:
    bedrock_agent = boto3.client("bedrock-agent", region_name=region)

    payload = {
        "name": name,
        "description": description,
        "roleArn": role_arn,
        "knowledgeBaseConfiguration": {
            "type": "VECTOR",
            "vectorKnowledgeBaseConfiguration": {
                "embeddingModelArn": EMBEDDING_MODEL_ARN_TEMPLATE.format(region=region),
            },
        },
        "storageConfiguration": {
            "type": "OPENSEARCH_SERVERLESS",
            "opensearchServerlessConfiguration": {
                "collectionArn": collection_arn,
                "vectorIndexName": index_name,
                "fieldMapping": {
                    "vectorField": "vector",
                    "textField": "text",
                    "metadataField": "metadata",
                },
            },
        },
        "clientToken": str(uuid.uuid4()),
    }

    response = bedrock_agent.create_knowledge_base(**payload)
    kb_id = response["knowledgeBase"]["knowledgeBaseId"]
    logger.info("Knowledge Base creada: %s", kb_id)
    return kb_id


def attach_s3_data_source(kb_id: str, s3_bucket: str, region: str, prefix: str = "") -> str:
    bedrock_agent = boto3.client("bedrock-agent", region_name=region)

    response = bedrock_agent.create_data_source(
        knowledgeBaseId=kb_id,
        name=f"{kb_id}-s3-source",
        dataSourceConfiguration={
            "type": "S3",
            "s3Configuration": {
                "bucketArn": f"arn:aws:s3:::{s3_bucket}",
                "inclusionPrefixes": [prefix] if prefix else [],
            },
        },
        # Chunking jerárquico funciona mejor que fixed-size para documentos
        # con secciones (whitepapers, manuales, glosarios).
        vectorIngestionConfiguration={
            "chunkingConfiguration": {
                "chunkingStrategy": "HIERARCHICAL",
                "hierarchicalChunkingConfiguration": {
                    "levelConfigurations": [
                        {"maxTokens": 1500},
                        {"maxTokens": 300},
                    ],
                    "overlapTokens": 60,
                },
            }
        },
    )
    ds_id = response["dataSource"]["dataSourceId"]
    logger.info("Data source S3 conectado: %s", ds_id)
    return ds_id


def start_ingestion(kb_id: str, ds_id: str, region: str) -> None:
    bedrock_agent = boto3.client("bedrock-agent", region_name=region)
    job = bedrock_agent.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)
    job_id = job["ingestionJob"]["ingestionJobId"]
    logger.info("Ingestion job lanzado: %s", job_id)

    # Polling hasta completar.
    while True:
        status = bedrock_agent.get_ingestion_job(
            knowledgeBaseId=kb_id, dataSourceId=ds_id, ingestionJobId=job_id
        )["ingestionJob"]["status"]
        logger.info("Ingestion status=%s", status)
        if status in {"COMPLETE", "FAILED", "STOPPED"}:
            break
        time.sleep(15)

    if status != "COMPLETE":
        raise RuntimeError(f"Ingestion terminó con status={status}")
    logger.info("Ingestion completada")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--role-arn", required=True)
    p.add_argument("--collection-arn", required=True)
    p.add_argument("--index-name", required=True)
    p.add_argument("--s3-bucket", required=True)
    p.add_argument("--s3-prefix", default="")
    p.add_argument("--region", default="us-east-1")
    args = p.parse_args()

    try:
        kb_id = create_kb(
            name=args.name,
            role_arn=args.role_arn,
            collection_arn=args.collection_arn,
            index_name=args.index_name,
            region=args.region,
        )
        ds_id = attach_s3_data_source(
            kb_id=kb_id, s3_bucket=args.s3_bucket, region=args.region, prefix=args.s3_prefix,
        )
        start_ingestion(kb_id=kb_id, ds_id=ds_id, region=args.region)

        print(f"\n✅ Listo. Configura en tu .env:\n  KNOWLEDGE_BASE_ID={kb_id}\n")
        return 0
    except ClientError as exc:
        logger.error("Error de AWS: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
