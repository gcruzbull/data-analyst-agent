# This file defines the agent's graph structure, including nodes for loading data and analyzing it based on user questions.
# The graph is built using the StateGraph class from the langgraph library, and it utilizes various tools for data analysis and anomaly detection.

from typing import TypedDict, List
from langgraph.graph import StateGraph, END

from src.tools.retriever import retrieve
from src.llm.llm_factory import get_llm


# Estado del grafo
class AgentState(TypedDict):
    question: str
    docs: List
    prompt: str
    result: str


# Nodo 1: retrieve
def retrieve_node(state: AgentState):
    # Recuperar contexto
    docs = retrieve(state["question"])
    return {"docs": docs}


# Nodo 2: build prompt
def build_prompt_node(state: AgentState):
    context = "\n\n".join([doc.page_content for doc in state["docs"]])

    prompt = f"""
Eres un analista de datos.

Responde la pregunta usando SOLO la información del contexto.

Contexto:
{context}

Pregunta:
{state["question"]}

Respuesta:
"""
    return {"prompt": prompt}


# Nodo 3: LLM
def llm_node(state: AgentState):
    llm = get_llm()
    response = llm.generate(state["prompt"])
    return {"result": response}


# Construcción del grafo
def build_agent():

    graph = StateGraph(AgentState)

    graph.add_node("retrieve", retrieve_node)
    graph.add_node("build_prompt", build_prompt_node)
    graph.add_node("llm", llm_node)

    # flujo
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "build_prompt")
    graph.add_edge("build_prompt", "llm")
    graph.add_edge("llm", END)

    return graph.compile()