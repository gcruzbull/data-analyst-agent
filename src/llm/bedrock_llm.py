# This file implements the BedrockLLM class, which uses Amazon Bedrock to generate responses based on prompts in production environment.
import boto3
from src.llm.llm_interface import LLMInterface
from src.config.settings import CLAUDE_MODEL, AWS_REGION
import json

# This class implements the LLMInterface using Amazon Bedrock API to generate responses from the specified model.
class BedrockLLM(LLMInterface):

    def __init__(self, model_id: str = "anthropic.claude-3-5-sonnet-20240620"):

        self.model_id = model_id

        self.client = boto3.client(
            service_name="bedrock-runtime",
            region_name="us-east-1"
        )

    def generate(self, prompt: str) -> str:

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        })

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=body
        )

        response_body = json.loads(response["body"].read())

        return response_body["content"][0]["text"]