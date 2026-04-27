# Despliegue en ECS Fargate

Esta es la opción recomendada: contenedor persistente, sin cold starts, con autoscaling
horizontal y stateful en memoria (cache de pandas).

## 1. Construir y subir la imagen a ECR

```bash
# Variables
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1
export REPO_NAME=retail-agent
export IMAGE_TAG=v1

# Crear el repo
aws ecr create-repository --repository-name $REPO_NAME --region $AWS_REGION

# Login
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build + push
docker build -t $REPO_NAME:$IMAGE_TAG .
docker tag $REPO_NAME:$IMAGE_TAG \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO_NAME:$IMAGE_TAG
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO_NAME:$IMAGE_TAG
```

## 2. IAM roles necesarios

Necesitas dos roles:

- **TaskExecutionRole**: para que ECS pueda hacer pull de la imagen y enviar logs
  a CloudWatch. Adjunta la policy gestionada `AmazonECSTaskExecutionRolePolicy`.
- **TaskRole**: para que el contenedor en runtime pueda invocar Bedrock y la KB.
  Ver [`iam_policies.md`](./iam_policies.md).

## 3. Task Definition (resumen)

```json
{
  "family": "retail-agent",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/RetailAgentTaskRole",
  "containerDefinitions": [
    {
      "name": "agent",
      "image": "ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/retail-agent:v1",
      "portMappings": [{"containerPort": 8000, "protocol": "tcp"}],
      "environment": [
        {"name": "LLM_PROVIDER",      "value": "bedrock"},
        {"name": "AWS_REGION",        "value": "us-east-1"},
        {"name": "BEDROCK_MODEL_ID",  "value": "us.anthropic.claude-3-5-sonnet-20241022-v2:0"},
        {"name": "CHART_STORAGE",     "value": "s3"},
        {"name": "CHART_S3_BUCKET",   "value": "mi-bucket-charts"}
      ],
      "secrets": [
        {"name": "KNOWLEDGE_BASE_ID", "valueFrom": "arn:aws:ssm:us-east-1:ACCOUNT:parameter/retail-agent/kb-id"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/retail-agent",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "agent"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -fsS http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 20
      }
    }
  ]
}
```

Registra:
```bash
aws ecs register-task-definition --cli-input-json file://taskdef.json
```

## 4. Service + ALB

- Crea un **Application Load Balancer** con un target group apuntando al puerto 8000.
- El health check del TG debe pegarle a `/health`.
- Crea el ECS Service con `desired_count=2` para HA y `assign_public_ip=DISABLED`
  detrás de subnets privadas con NAT Gateway.

```bash
aws ecs create-service \
  --cluster retail-cluster \
  --service-name retail-agent \
  --task-definition retail-agent \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=DISABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=agent,containerPort=8000"
```

## 5. Autoscaling

Configura autoscaling sobre la métrica `ECSServiceAverageCPUUtilization` o sobre
una métrica custom de RPS desde el ALB. Por ejemplo, target = 60% CPU, min=2, max=10.

## 6. Observabilidad

- Logs en CloudWatch en formato JSON (ya configurado en `api/main.py`).
- Métricas Bedrock en CloudWatch namespace `AWS/Bedrock` (latencia, throttling, tokens).
- Trazas: si quieres OpenTelemetry, añade `opentelemetry-instrumentation-fastapi` y
  un exporter ADOT.

## 7. Costos a vigilar

- Bedrock Sonnet 3.5 v2: ~$3 / 1M tokens input, ~$15 / 1M tokens output.
- OpenSearch Serverless: mínimo ~$175/mes por OCU. Para volúmenes pequeños evalúa
  Pinecone o Aurora pgvector como alternativas conectables a Bedrock KB.
- Fargate: ~$36/mes por tarea (1 vCPU, 2 GB) running 24/7.