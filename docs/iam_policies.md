# IAM Policies

Mínimas necesarias para que el agente funcione en producción.

## TaskRole (ECS) / ExecutionRole (Lambda)

Permite invocar Bedrock, consultar la KB, leer/escribir charts en S3 y
opcionalmente leer parámetros de SSM.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockInvokeModel",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:Converse",
        "bedrock:ConverseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
        "arn:aws:bedrock:*:ACCOUNT:inference-profile/us.anthropic.claude-3-5-sonnet-20241022-v2:0"
      ]
    },
    {
      "Sid": "BedrockKnowledgeBase",
      "Effect": "Allow",
      "Action": [
        "bedrock:Retrieve",
        "bedrock:RetrieveAndGenerate"
      ],
      "Resource": "arn:aws:bedrock:*:ACCOUNT:knowledge-base/KB_ID"
    },
    {
      "Sid": "S3Charts",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::mi-bucket-charts/charts/*"
    },
    {
      "Sid": "SSMSecrets",
      "Effect": "Allow",
      "Action": ["ssm:GetParameter", "ssm:GetParameters"],
      "Resource": "arn:aws:ssm:*:ACCOUNT:parameter/retail-agent/*"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:ACCOUNT:log-group:/ecs/retail-agent:*"
    }
  ]
}
```

## Por qué dos ARNs en BedrockInvokeModel

Cuando usas un cross-region inference profile (recomendado para Sonnet 3.5 v2),
Bedrock necesita permiso para invocar **tanto el inference profile como el
foundation model subyacente**. Si solo das uno de los dos, fallará con
`AccessDeniedException`.

## Role para la Knowledge Base

Adicionalmente, la propia KB requiere su propio role (lo configuras una vez al
crearla). Debe poder:
- Leer del bucket S3 con los documentos.
- Invocar el modelo de embeddings (Titan v2).
- Leer/escribir en la colección OpenSearch Serverless.

Trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "bedrock.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
```

Permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3Read",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::mi-bucket-retail-docs",
        "arn:aws:s3:::mi-bucket-retail-docs/*"
      ]
    },
    {
      "Sid": "BedrockEmbeddings",
      "Effect": "Allow",
      "Action": "bedrock:InvokeModel",
      "Resource": "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0"
    },
    {
      "Sid": "AOSSAccess",
      "Effect": "Allow",
      "Action": "aoss:APIAccessAll",
      "Resource": "arn:aws:aoss:*:ACCOUNT:collection/COLLECTION_ID"
    }
  ]
}
```
