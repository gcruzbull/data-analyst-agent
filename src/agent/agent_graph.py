# This file defines the agent's graph structure, including nodes for loading data and analyzing it based on user questions.
# The graph is built using the StateGraph class from the langgraph library, and it utilizes various tools for data analysis and anomaly detection.

"""
Agente ReAct sobre LangGraph.

Diseño:
- StateGraph con dos nodos: `agent` (llama al LLM) y `tools` (ejecuta tool_use).
- Edge condicional: si la respuesta del LLM contiene tool_calls → ir a `tools`,
  si no → END.
- Loop natural: tools → agent → tools → ... hasta que el modelo decida terminar
  o se alcance `max_iterations`.

Ventaja de LangGraph aquí: trazabilidad, checkpointing y posibilidad de extender
a multi-agente sin reescribir el core.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from src.agent.prompts import SYSTEM_PROMPT

def _append_messages(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reducer simple: concatena nuevos mensajes preservando el formato dict.
    Evitamos `add_messages` de LangGraph porque convierte a `AIMessage`/`HumanMessage`,
    lo cual destruye el formato Anthropic con bloques (text, tool_use, tool_result)
    que necesitamos para tool-use multi-turno."""
    if not isinstance(left, list):
        left = [left] if left else []
    if not isinstance(right, list):
        right = [right] if right else []
    return left + right
from src.config.settings import get_settings
from src.llm.llm_factory import get_llm
from src.llm.llm_interface import LLMInterface
from src.tools.registry import execute_tool, get_tool_specs

logger = logging.getLogger(__name__)


# Estado del grafo
class AgentState(TypedDict):
    """Estado del grafo. `messages` se acumula con un reducer custom que
    preserva el formato dict-Anthropic (necesario para tool_use/tool_result)."""
    messages: Annotated[list[dict[str, Any]], _append_messages]
    iterations: int
    chart_urls: list[str]


def _agent_node(state: AgentState, llm: LLMInterface) -> dict[str, Any]:
    """Llama al LLM con el historial actual y las tools disponibles."""
    iterations = state.get("iterations", 0)
    max_iter = get_settings().max_agent_iterations

    if iterations >= max_iter:
        logger.warning("Límite de iteraciones (%d) alcanzado", max_iter)
        msg = {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "He alcanzado el límite de iteraciones sin llegar a una respuesta "
                        "completa. ¿Puedes reformular la pregunta o desglosarla?"
                    ),
                }
            ],
        }
        return {"messages": [msg], "iterations": iterations + 1}

    response = llm.chat(
        messages=state["messages"],
        system=SYSTEM_PROMPT,
        tools=get_tool_specs(),
    )

    # Reconstruir el assistant message en formato Anthropic-block.
    content_blocks: list[dict[str, Any]] = []
    if response.text:
        content_blocks.append({"type": "text", "text": response.text})
    for tc in response.tool_calls:
        content_blocks.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input})

    return {
        "messages": [{"role": "assistant", "content": content_blocks}],
        "iterations": iterations + 1,
    }


def _tools_node(state: AgentState) -> dict[str, Any]:
    """Ejecuta los tool_use del último mensaje del assistant."""
    last_message = state["messages"][-1]
    tool_results: list[dict[str, Any]] = []
    new_chart_urls = list(state.get("chart_urls", []))

    for block in last_message["content"]:
        if block.get("type") != "tool_use":
            continue

        result_str, is_error = execute_tool(block["name"], block.get("input", {}))

        # Capturamos URLs de gráficos para devolverlas estructuradas en la API.
        if not is_error and "chart_url" in result_str:
            try:
                import json
                parsed = json.loads(result_str)
                if isinstance(parsed, dict) and "chart_url" in parsed:
                    new_chart_urls.append(parsed["chart_url"])
            except json.JSONDecodeError:
                pass

        tool_results.append({
            "type": "tool_result",
            "tool_use_id": block["id"],
            "content": result_str,
            "is_error": is_error,
        })

    return {
        "messages": [{"role": "user", "content": tool_results}],
        "chart_urls": new_chart_urls,
    }


def _should_continue(state: AgentState) -> str:
    """Edge condicional: ¿el último mensaje del assistant pidió tools?"""
    last = state["messages"][-1]
    if last.get("role") != "assistant":
        return END
    content = last.get("content", [])
    if not isinstance(content, list):
        return END
    has_tool_use = any(b.get("type") == "tool_use" for b in content)
    return "tools" if has_tool_use else END


def build_agent(llm: LLMInterface | None = None):
    """Compila el grafo. Permite inyectar un LLM mock para testing."""
    llm_instance = llm or get_llm()

    graph = StateGraph(AgentState)
    graph.add_node("agent", lambda s: _agent_node(s, llm_instance))
    graph.add_node("tools", _tools_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


def run_agent(question: str, llm: LLMInterface | None = None) -> dict[str, Any]:
    """
    Ejecuta el agente para una pregunta y devuelve un dict con:
      - answer: texto final del assistant
      - chart_urls: URLs de gráficos producidos durante la conversación
      - n_iterations: cuántas vueltas dio el loop
    """
    agent = build_agent(llm=llm)
    initial_state: AgentState = {
        "messages": [{"role": "user", "content": question}],
        "iterations": 0,
        "chart_urls": [],
    }
    final_state = agent.invoke(initial_state)

    last = final_state["messages"][-1]
    answer_text = ""
    if isinstance(last.get("content"), list):
        answer_text = "".join(b.get("text", "") for b in last["content"] if b.get("type") == "text")
    elif isinstance(last.get("content"), str):
        answer_text = last["content"]

    return {
        "answer": answer_text,
        "chart_urls": final_state.get("chart_urls", []),
        "n_iterations": final_state.get("iterations", 0),
    }