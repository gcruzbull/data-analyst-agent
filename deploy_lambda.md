# Despliegue en Lambda + API Gateway

Alternativa serverless. **No es la opción recomendada** para este agente por las
razones que se explican abajo, pero queda documentada por completitud.

## Por qué Lambda no es ideal aquí

1. **Cold start con pandas + matplotlib + boto3**: el bundle pesa varios cientos
   de MB. La primera invocación puede tardar 5-10 segundos en inicializar.
2. **Timeout de 15 minutos**: suficiente para este agente, pero el loop ReAct
   con muchas iteraciones podría rozarlo si la KB es lenta.
3. **No hay caching en memoria entre invocaciones** garantizado. El singleton del
   agente solo sobrevive si el contenedor de Lambda se reusa (warm start).
4. **El dataset CSV (~44 MB)** debe vivir en S3 o EFS porque el zip de Lambda
   tiene límite de 250 MB descomprimido. Esto añade latencia.

Si aun así quieres serverless, **úsalo solo si**: tu tráfico es bursty/poco frecuente,
no necesitas latencia <2s en el peor caso, y aceptas refactorizar `data_loader.py`
para leer desde S3.

## Pasos

### 1. Adaptar el handler

Necesitas un adaptador entre API Gateway y FastAPI. La librería `mangum` lo hace:

```bash
pip install mangum
```

Crea `api/lambda_handler.py`:

```python
from mangum import Mangum
from api.main import app

handler = Mangum(app, lifespan="off")
```

Lifespan se desactiva porque no aplica en Lambda; en su lugar el agente se
construye lazy en la primera invocación (ya está manejado por el cache global).

### 2. Construir la imagen Docker para Lambda

Lambda soporta imágenes de contenedor de hasta 10 GB. Reusa el Dockerfile pero
cambia la base image y el `CMD`:

```dockerfile
FROM public.ecr.aws/lambda/python:3.11

COPY requirements.txt .
RUN pip install -r requirements.txt --target ${LAMBDA_TASK_ROOT}

COPY src ${LAMBDA_TASK_ROOT}/src
COPY api ${LAMBDA_TASK_ROOT}/api

# El dataset NO se incluye; debe leerse desde S3 (modificar data_loader.py).

CMD [ "api.lambda_handler.handler" ]
```

### 3. Mover el dataset a S3

Modifica `src/tools/data_loader.py` para detectar paths `s3://`:

```python
@lru_cache(maxsize=1)
def load_data() -> pd.DataFrame:
    path = str(get_settings().data_path)
    if path.startswith("s3://"):
        import s3fs  # noqa
        return pd.read_csv(path, parse_dates=["InvoiceDate"])
    return pd.read_csv(path, parse_dates=["InvoiceDate"])
```

Y añade `s3fs` a `requirements.txt`. Esta lectura ocurre una sola vez por contenedor
warm, así que el costo de latencia se amortiza.

### 4. Subir la imagen y crear la función

```bash
aws ecr create-repository --repository-name retail-agent-lambda
docker build -f Dockerfile.lambda -t retail-agent-lambda .
docker tag retail-agent-lambda:latest \
  $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/retail-agent-lambda:latest
docker push $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/retail-agent-lambda:latest

aws lambda create-function \
  --function-name retail-agent \
  --package-type Image \
  --code ImageUri=$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/retail-agent-lambda:latest \
  --role arn:aws:iam::$ACCOUNT:role/RetailAgentLambdaRole \
  --timeout 120 \
  --memory-size 2048 \
  --environment "Variables={LLM_PROVIDER=bedrock,BEDROCK_MODEL_ID=us.anthropic.claude-3-5-sonnet-20241022-v2:0,DATA_PATH=s3://mi-bucket/dataset_clean.csv,CHART_STORAGE=s3,CHART_S3_BUCKET=mi-bucket-charts}"
```

### 5. Exponerla por API Gateway

Crea una HTTP API (más barata que REST API) con una ruta `POST /ask` integrada
a la Lambda. API Gateway timeout máximo es 30 s, así que reduce
`MAX_AGENT_ITERATIONS` a 4-5 para evitar timeouts.

### 6. Provisioned concurrency (opcional)

Para mitigar cold starts, configura **Provisioned Concurrency** = 1-2. Costo extra
pero la latencia P99 baja drásticamente.

## Comparativa

| Aspecto                  | ECS Fargate (recomendado) | Lambda                    |
|--------------------------|---------------------------|---------------------------|
| Cold start               | 0 (siempre running)       | 3-10 s                    |
| Costo idle               | ~$36/mes/tarea            | $0                        |
| Costo bajo carga         | Más barato a >100k req/d  | Más barato a <10k req/d   |
| Timeout máximo           | Sin límite                | 15 min (API GW: 30 s)     |
| Cache en memoria         | Sí, persistente           | Solo entre warm starts    |
| Operación                | Más infra (ALB, autoscaling) | Mínima                 |
| Tamaño dataset           | Cualquiera                 | <250 MB descomprimido     |
