"""Tests del agente con un LLM mock — no requiere AWS ni Ollama."""
from __future__ import annotations

from typing import Any

import pytest

from src.agent.agent_graph import run_agent
from src.llm.llm_interface import LLMInterface, LLMResponse, ToolCall


class ScriptedLLM(LLMInterface):
    """LLM que devuelve respuestas predefinidas en orden, útil para tests."""

    def __init__(self, scripted_responses: list[LLMResponse]):
        self._responses = list(scripted_responses)
        self.calls: list[dict[str, Any]] = []

    def chat(self, messages, system=None, tools=None):
        self.calls.append({"messages": messages, "system": system, "tools": tools})
        if not self._responses:
            raise RuntimeError("ScriptedLLM se quedó sin respuestas")
        return self._responses.pop(0)


@pytest.fixture
def fake_dataset(tmp_path, monkeypatch):
    """Genera un CSV mínimo que mimetiza el esquema Online Retail."""
    import pandas as pd

    df = pd.DataFrame({
        "InvoiceNo": ["A1", "A2", "A3"],
        "StockCode": ["X1", "X2", "X1"],
        "Description": ["WIDGET A", "WIDGET B", "WIDGET A"],
        "Quantity": [10, 5, 7],
        "InvoiceDate": ["2024-01-15 10:00:00", "2024-02-20 11:00:00", "2024-02-25 12:00:00"],
        "UnitPrice": [2.5, 4.0, 2.5],
        "CustomerID": [1.0, 2.0, 1.0],
        "Country": ["Chile", "Argentina", "Chile"],
    })
    csv_path = tmp_path / "ds.csv"
    df.to_csv(csv_path, index=False)
    monkeypatch.setenv("DATA_PATH", str(csv_path))

    # Resetear cachés que ya hayan leído otra ruta.
    from src.config import settings as settings_mod
    from src.tools import data_loader

    settings_mod.get_settings.cache_clear()
    data_loader.load_data.cache_clear()


def test_agent_uses_top_products_tool(fake_dataset):
    """El agente debería llamar a `top_products` y luego responder con texto."""
    scripted = [
        # Turno 1: el modelo decide usar la tool top_products.
        LLMResponse(
            text="",
            tool_calls=[ToolCall(id="t1", name="top_products", input={"top_n": 3, "by": "quantity"})],
            stop_reason="tool_use",
            raw={},
        ),
        # Turno 2: el modelo recibe el resultado y produce la respuesta final.
        LLMResponse(
            text="El producto más vendido es WIDGET A con 17 unidades.",
            tool_calls=[],
            stop_reason="end_turn",
            raw={},
        ),
    ]
    llm = ScriptedLLM(scripted)

    result = run_agent("¿Cuál es el producto más vendido?", llm=llm)

    assert "WIDGET A" in result["answer"]
    assert result["n_iterations"] == 2
    # El modelo recibió en la 2da llamada un mensaje role=user con tool_result.
    assert len(llm.calls) == 2
    assert any(
        any(b.get("type") == "tool_result" for b in (m.get("content") if isinstance(m.get("content"), list) else []))
        for m in llm.calls[1]["messages"]
    )


def test_agent_handles_tool_error_gracefully(fake_dataset):
    """Si una tool falla, el modelo debe poder seguir."""
    scripted = [
        LLMResponse(
            text="",
            tool_calls=[ToolCall(id="t1", name="top_products", input={"top_n": -5})],
            stop_reason="tool_use",
            raw={},
        ),
        LLMResponse(
            text="Hubo un error, pero acá está la respuesta general.",
            tool_calls=[],
            stop_reason="end_turn",
            raw={},
        ),
    ]
    result = run_agent("Top productos", llm=ScriptedLLM(scripted))
    # Como pandas .head(-5) devuelve filas vacías, no hay excepción, solo
    # un dict vacío. Pero el flujo del agente debe completar.
    assert result["n_iterations"] == 2
    assert "respuesta" in result["answer"].lower()


def test_unknown_tool_does_not_crash(fake_dataset):
    """Si el LLM inventa una tool, el agente devuelve error como tool_result."""
    scripted = [
        LLMResponse(
            text="",
            tool_calls=[ToolCall(id="t1", name="tool_inexistente", input={})],
            stop_reason="tool_use",
            raw={},
        ),
        LLMResponse(text="No pude responder.", tool_calls=[], stop_reason="end_turn", raw={}),
    ]
    result = run_agent("?", llm=ScriptedLLM(scripted))
    assert result["n_iterations"] == 2