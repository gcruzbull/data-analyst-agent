# Resumen del Refactor

Documento que explica los cambios respecto al repo original
[`gcruzbull/data-analyst-agent`](https://github.com/gcruzbull/data-analyst-agent).

## Tabla de cambios

| Aspecto                     | Original                              | Refactor                                                       |
|-----------------------------|---------------------------------------|----------------------------------------------------------------|
| LLM provider                | Ollama (llama3) hardcodeado           | Factory ollama / bedrock con interfaz unificada                |
| API LLM                     | `invoke_model` raw                    | **Converse API** (tool-use nativo + cross-region inference)    |
| Modelo                      | claude-3-5-sonnet-20240620 (antiguo)  | `us.anthropic.claude-3-5-sonnet-20241022-v2:0` (v2 + profile)  |
| Patrón de agente            | RAG lineal de 3 nodos                 | **ReAct** loop con tool-use multi-turno                        |
| Tools                       | Existían pero **nunca se invocaban**  | Registry central, schema JSON, dispatcher con manejo de errores|
| RAG                         | FAISS local + OllamaEmbeddings        | **Bedrock Knowledge Bases** (S3 + OpenSearch Serverless gestionado) |
| Configuración Bedrock       | Hardcoded, ignoraba env vars          | `Settings` dataclass cacheada, todo via env                    |
| API duplicada               | `ask_agent` declarada 2 veces         | Endpoint único + `/health` + `/readiness`                      |
| Vectorstore                 | Variable global mutable               | Cliente boto3 con cache local                                  |
| Storage de gráficos         | PNG en `cwd` con nombres fijos        | S3 con presigned URLs o `/tmp` (configurable)                  |
| Backend matplotlib          | Default (rompe en headless)           | `Agg` explícito                                                |
| Manejo de devoluciones      | No                                    | Filtrado de `Quantity < 0` por defecto                         |
| Tests                       | Scripts manuales con `print`          | pytest + LLM mock (`ScriptedLLM`), 3 tests verdes              |
| Logging                     | `print()`                             | JSON estructurado para CloudWatch                              |
| Docker                      | No                                    | Dockerfile multi-stage + `.dockerignore` + healthcheck         |
| Despliegue                  | No                                    | Docs ECS Fargate + Lambda + IAM policies                       |
| `settings.py` raíz          | Vacío (residuo)                       | Eliminado                                                      |

## Bugs corregidos del original

1. `BedrockLLM` hardcodeaba `region_name="us-east-1"` ignorando `AWS_REGION`.
2. `BedrockLLM` usaba un model_id obsoleto (Sonnet v1).
3. `api/main.py` declaraba `ask_agent` dos veces; la segunda usaba `Request`
   sin importarlo y sobrescribía la primera.
4. `retriever.build_vectorstore` cortaba a 50 filas con un comentario que
   decía "500" — bug de copy/paste.
5. `chart_tools` reutilizaba la figura activa de matplotlib sin `plt.figure()`,
   acumulando ejes entre llamadas en producción.
6. `data_loader.py` tenía dos implementaciones de `load_data` superpuestas y
   una de ellas era código muerto comentado.

## Lo que se mantuvo

- La idea base del **patrón Factory + Interface** para LLMs (estaba bien
  diseñada, solo le faltaba implementación de tool-use).
- El uso de **LangGraph** como motor de orquestación (decisión correcta).
- La separación modular `agent / llm / tools / api`.
- La estructura del dataset (Online Retail UCI).

## Cobertura del objetivo del usuario

- ✅ El agente actúa como data analyst de retail (system prompt + tools temáticas).
- ✅ Responde preguntas relacionadas con el sector (RAG vía KB para conceptos +
  pandas para datos).
- ✅ Genera gráficos a demanda y los expone como URLs.
- ✅ Corre en AWS Bedrock con Sonnet 3.5 v2.
- ✅ Tests automatizados que no requieren credenciales.
- ✅ Listo para ECS Fargate (Dockerfile + docs) y documentado para Lambda.

## Próximos pasos sugeridos

1. **Streaming**: añadir `/ask/stream` con `ConverseStream` y SSE para mejorar UX.
2. **Memoria**: persistir conversaciones por `session_id` (DynamoDB + LangGraph
   checkpointer).
3. **Guardrails**: integrar Bedrock Guardrails para PII y temas sensibles.
4. **Más tools**: cohort analysis, RFM segmentation, forecasting con Prophet.
5. **Evals**: suite de evaluación con preguntas-doradas y un juez LLM.