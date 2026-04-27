# Knowledge Base de Bedrock

Esta KB alimenta el RAG del agente con conocimiento cualitativo del sector retail
(definiciones de KPIs, frameworks como RFM, benchmarks, glosarios, best practices).

## Recomendación de contenido

El RAG **no debe** contener el dataset transaccional — para eso ya tenemos las
tools de pandas. Lo que debe vivir aquí es información que el LLM no puede calcular:

- Definiciones de métricas: AOV, CLTV, churn, repeat purchase rate, etc.
- Documentos de industria: benchmarks de NRF, Nielsen, Statista.
- Frameworks: RFM, cohort analysis, market basket analysis.
- Manuales internos de la empresa (políticas de descuento, taxonomía de productos).
- FAQs.

Formatos soportados por Bedrock KB: PDF, TXT, MD, HTML, DOC, DOCX, CSV, XLSX, JSON.

## Opción 1: Crear desde la consola (más fácil)

1. Sube tus documentos a un bucket S3.
2. Bedrock Console → **Knowledge bases** → **Create knowledge base**.
3. Elige **Quick create** para que AWS cree la colección OpenSearch Serverless
   automáticamente. Esto evita la fricción de provisionarla a mano.
4. Embedding model: **Titan Text Embeddings v2** (1024 dim, multilingüe).
5. Chunking: **Hierarchical** (mejor que fixed-size para documentos estructurados).
6. Sync. Espera a que termine la ingesta (puede tardar varios minutos).
7. Copia el `knowledgeBaseId` y ponlo en `.env`:
   ```
   KNOWLEDGE_BASE_ID=ABC123XYZ
   ```

## Opción 2: Programáticamente

Usa el script provisto:

```bash
python scripts/setup_knowledge_base.py \
  --name retail-kb \
  --role-arn arn:aws:iam::ACCOUNT:role/BedrockKBRole \
  --collection-arn arn:aws:aoss:us-east-1:ACCOUNT:collection/COLLECTION_ID \
  --index-name retail-vector-index \
  --s3-bucket mi-bucket-retail-docs \
  --region us-east-1
```

Esto requiere haber creado de antemano:
- El IAM role para la KB (ver [`iam_policies.md`](./iam_policies.md)).
- La colección OpenSearch Serverless con un índice vector compatible.

## Verificar la KB

```bash
KB_ID=ABC123XYZ aws bedrock-agent-runtime retrieve \
  --knowledge-base-id $KB_ID \
  --retrieval-query '{"text": "qué es customer lifetime value"}' \
  --retrieval-configuration '{"vectorSearchConfiguration": {"numberOfResults": 3, "overrideSearchType": "HYBRID"}}'
```

## Costos

- **OpenSearch Serverless**: mínimo 2 OCUs (1 índice + 1 search) = ~$350/mes
  ejecutándose 24/7. Si tu corpus es chico (<10k docs), considera alternativas
  más baratas conectables a Bedrock KB:
  - **Aurora PostgreSQL con pgvector**: pagas por uso real.
  - **Pinecone Serverless**: pay-per-use, ~$0.06/GB-mes.
- **Titan Embed v2**: $0.02 / 1M tokens. Coste de ingesta despreciable.
- **Retrieve API**: gratis (solo pagas el cómputo subyacente del vector store).

## Tuning de relevancia

Si los resultados no son los esperados:

1. Cambia `chunkingStrategy` a `SEMANTIC` en lugar de `HIERARCHICAL` para texto
   muy denso o conversacional.
2. Activa el **Bedrock reranker** (Cohere Rerank o Amazon Rerank) en
   `retrievalConfiguration.vectorSearchConfiguration.rerankingConfiguration`.
   Mejora la precisión a costa de latencia (~200 ms extra) y costo.
3. Sube `numberOfResults` de 5 a 10-15 si el agente reporta "no encontré info".
