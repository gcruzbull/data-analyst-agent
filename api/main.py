# This is the main entry point for the FastAPI application. 
# It defines the API endpoints and integrates the agent built in src.agent.agent_graph.

from fastapi import FastAPI, requests
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel

from src.agent.agent_graph import build_agent
#from src.tools.data_loader import load_data
from src.tools.retriever import init_vectorstore


import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    init_vectorstore()
    print("Vectorstore inicializado")

    yield

    # shutdown (opcional)
    print("App cerrándose")

app = FastAPI(lifespan=lifespan)

# --- inicialización (se ejecuta una vez) ---
#df = load_data("data/dataset.csv")
agent = build_agent()

# --- request schema ---
class Query(BaseModel):
    question: str

# --- endpoint ---

@app.post("/ask")
def ask_agent(query: Query):

    state = {
        "question": query.question,
    }

    result = agent.invoke(state)

    return JSONResponse(
        content={"answer": result["result"]},
        media_type="application/json; charset=utf-8"
    )

async def ask_agent(request: Request):
    raw = await request.body()
    print("RAW BODY:", raw)  # debug
    
    data = await request.json()
    print("PARSED JSON:", data)  # debug
    
    return {"ok": True}  
