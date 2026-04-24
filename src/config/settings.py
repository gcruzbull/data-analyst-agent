import os
from dotenv import load_dotenv

load_dotenv()

# Change this variable to switch between LLM providers
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
#LLM_PROVIDER = os.getenv("LLM_PROVIDER", "bedrock")

# Model names and other settings
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet")

DATA_PATH = os.getenv("DATA_PATH", "data/dataset_clean.csv")

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
