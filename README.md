# Retail Data Analyst Agent

Agente conversacional que actúa como data analyst del sector retail. Combina
**Claude 3.5 Sonnet v2 en Bedrock**, un loop **ReAct sobre LangGraph**, herramientas
de pandas/scikit-learn/matplotlib, y **RAG vía Bedrock Knowledge Bases**.

## Arquitectura

```
┌──────────────┐    POST /ask     ┌──────────────────────────┐
│  Cliente     │ ───────────────► │  FastAPI (api/main.py)   │
└──────────────┘                  └────────────┬─────────────┘
                                               │
                                  ┌────────────▼─────────────┐
                                  │   LangGraph: ReAct loop  │
                                  │   ┌──────┐    ┌───────┐  │
                                  │   │agent │──►│ tools │  │
                                  │   └──┬───┘    └───┬───┘  │
                                  │      └────────────┘      │
                                  └────────────┬─────────────┘
                                               │
                ┌──────────────────┬───────────┼─────────────┬─────────────┐
                ▼                  ▼           ▼             ▼             ▼
        ┌──────────────┐  ┌──────────────┐  ┌─────────┐ ┌──────────┐ ┌──────────┐
        │ Bedrock      │  │ Bedrock KB   │  │ pandas  │ │ matplotlib│ │ sklearn  │
        │ Claude 3.5   │  │ + OpenSearch │  │ tools   │ │ plot tools│ │ Iso For. │
        │ Sonnet v2    │  │ Serverless   │  └─────────┘ └─────┬─────┘ └──────────┘
        └──────────────┘  └──────────────┘                    │
                                                              ▼
                                                          ┌────────┐
                                                          │   S3   │
                                                          │ charts │
                                                          └────────┘
```

## Ejecutar localmente

### 1. Modo Bedrock (requiere credenciales AWS)

```bash
cp .env.example .env
# Edita .env con tus valores; mínimo:
#   LLM_PROVIDER=bedrock
#   AWS_REGION=us-east-1
#   AWS_PROFILE=mi-perfil  (o exporta AWS_ACCESS_KEY_ID/SECRET)

pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

Probarlo:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "¿Cuáles son los 5 productos más vendidos? Muéstrame también un gráfico."}'
```

### 2. Modo local sin AWS (Ollama)

```bash
ollama pull llama3.1   # importante: 3.1 o superior, soporta tool-use
LLM_PROVIDER=ollama uvicorn api.main:app --reload
```

### 3. Tests

```bash
pip install pytest
pytest tests/ -v
```

Los tests usan un LLM mock (`ScriptedLLM`), por lo que no requieren AWS ni Ollama.

## Deployment

Documentación detallada en [`docs/`](./docs):

- [`docs/deploy_ecs.md`](./docs/deploy_ecs.md) — despliegue en ECS Fargate (recomendado)
- [`docs/deploy_lambda.md`](./docs/deploy_lambda.md) — despliegue serverless en Lambda
- [`docs/iam_policies.md`](./docs/iam_policies.md) — políticas IAM mínimas necesarias
- [`docs/knowledge_base.md`](./docs/knowledge_base.md) — cómo crear y poblar la KB

## Estructura del proyecto

```
.
├── api/main.py                  # FastAPI app
├── src/
│   ├── agent/
│   │   ├── agent_graph.py       # ReAct loop sobre LangGraph
│   │   └── prompts.py           # System prompt
│   ├── config/settings.py       # Configuración con dataclass
│   ├── llm/
│   │   ├── llm_interface.py     # ABC + LLMResponse + ToolCall
│   │   ├── llm_factory.py       # Factory ollama/bedrock
│   │   ├── bedrock_llm.py       # Cliente Converse API
│   │   └── ollama_llm.py        # Cliente Ollama
│   └── tools/
│       ├── data_loader.py       # Carga del dataset
│       ├── kb_retriever.py      # Cliente Bedrock KB
│       ├── registry.py          # Registry central de tools del agente
│       └── storage.py           # S3 / disco para gráficos
├── scripts/
│   └── setup_knowledge_base.py  # Provisiona KB desde S3
├── tests/test_agent.py
├── Dockerfile
└── requirements.txt
```

## Decisiones de diseño relevantes

- **Converse API en lugar de invoke_model**: API unificada y soporte nativo para
  tool-use e inference profiles cross-region.
- **Cross-region inference profile** (`us.anthropic...`): exigido por Bedrock para
  Sonnet 3.5 v2 en muchas regiones.
- **Knowledge Bases gestionado**: elimina la necesidad de mantener FAISS local +
  embeddings; soporta ingesta incremental y reranking.
- **Reducer custom de `messages`**: preservamos el formato dict-Anthropic con
  bloques (`text`, `tool_use`, `tool_result`) en lugar del `add_messages` de
  LangGraph, que convierte todo a `AIMessage`/`HumanMessage` y rompe el ciclo
  multi-turno con tool-use.
- **Charts a S3 con presigned URLs**: la API devuelve URLs, no base64; mantiene
  los payloads pequeños y permite caching en CloudFront si se requiere.
