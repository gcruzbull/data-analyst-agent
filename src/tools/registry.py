"""
Registry central de herramientas del agente.

Cada herramienta expone:
- name: nombre que el LLM verá
- description: cómo y cuándo usarla
- input_schema: JSON Schema de los parámetros
- handler: función Python que la ejecuta y devuelve un str (lo que ve el LLM)

Esto desacopla las funciones de negocio (pandas_tools, chart_tools, etc.) de
cómo se exponen al agente. Si mañana cambiamos a otra librería de orquestación
basta con remapear los handlers.
"""
from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")  # backend sin display, obligatorio en contenedores
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.ensemble import IsolationForest

from src.config.settings import get_settings
from src.tools.data_loader import load_data
from src.tools.kb_retriever import retrieve_from_kb
from src.tools.storage import save_chart_bytes

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _filter_returns(df: pd.DataFrame, exclude_returns: bool = True) -> pd.DataFrame:
    """El dataset Online Retail trae devoluciones con Quantity<0.
    Para 'ventas' las excluimos por defecto."""
    return df[df["Quantity"] > 0] if exclude_returns else df


def _serialize(obj: Any) -> str:
    """Convierte cualquier resultado a string JSON legible para el LLM."""
    if isinstance(obj, (pd.Series, pd.DataFrame)):
        return obj.to_json(orient="table", date_format="iso", indent=2)
    return json.dumps(obj, default=str, ensure_ascii=False, indent=2)


def _save_current_plot(name: str) -> str:
    """Serializa la figura actual de matplotlib a PNG y la persiste."""
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close()
    buf.seek(0)
    return save_chart_bytes(buf.read(), name)


# --------------------------------------------------------------------------- #
# Handlers de cada tool
# --------------------------------------------------------------------------- #
def _h_top_products(top_n: int = 10, by: str = "quantity") -> str:
    df = _filter_returns(load_data())
    metric = "Quantity" if by == "quantity" else "TotalPrice"
    result = (
        df.groupby("Description")[metric]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
        .round(2)
    )
    return _serialize(result.to_dict())


def _h_sales_by_country(top_n: int = 10, metric: str = "revenue") -> str:
    df = _filter_returns(load_data())
    col = "TotalPrice" if metric == "revenue" else "Quantity"
    result = df.groupby("Country")[col].sum().sort_values(ascending=False).head(top_n).round(2)
    return _serialize(result.to_dict())


def _h_monthly_sales(country: str | None = None, metric: str = "revenue") -> str:
    df = _filter_returns(load_data())
    if country:
        df = df[df["Country"].str.lower() == country.lower()]
        if df.empty:
            return json.dumps({"error": f"No hay datos para Country='{country}'"})

    col = "TotalPrice" if metric == "revenue" else "Quantity"
    monthly = df.groupby(df["InvoiceDate"].dt.to_period("M"))[col].sum().round(2)
    monthly.index = monthly.index.astype(str)
    return _serialize(monthly.to_dict())


def _h_describe_dataset() -> str:
    """Resumen estadístico del dataset, útil para preguntas exploratorias."""
    df = load_data()
    summary = {
        "n_rows": int(len(df)),
        "date_range": {
            "min": str(df["InvoiceDate"].min()),
            "max": str(df["InvoiceDate"].max()),
        },
        "n_unique_products": int(df["Description"].nunique()),
        "n_unique_customers": int(df["CustomerID"].nunique()),
        "n_countries": int(df["Country"].nunique()),
        "total_revenue": round(float(_filter_returns(df)["TotalPrice"].sum()), 2),
        "columns": list(df.columns),
    }
    return _serialize(summary)


def _h_detect_anomalies(contamination: float = 0.01) -> str:
    df = _filter_returns(load_data())
    model = IsolationForest(n_estimators=100, contamination=contamination, random_state=42)
    df = df.copy()
    df["anomaly"] = model.fit_predict(df[["Quantity", "UnitPrice"]])
    anomalies = df[df["anomaly"] == -1]
    summary = {
        "n_anomalies": int(len(anomalies)),
        "pct_of_total": round(100 * len(anomalies) / len(df), 3),
        "examples": anomalies.head(10)[
            ["InvoiceNo", "Description", "Quantity", "UnitPrice", "TotalPrice", "Country"]
        ].to_dict(orient="records"),
    }
    return _serialize(summary)


def _h_plot_top_products(top_n: int = 10, by: str = "quantity") -> str:
    df = _filter_returns(load_data())
    metric = "Quantity" if by == "quantity" else "TotalPrice"
    series = df.groupby("Description")[metric].sum().sort_values(ascending=False).head(top_n)

    plt.figure(figsize=(10, 6))
    series.plot(kind="barh")
    plt.gca().invert_yaxis()
    plt.title(f"Top {top_n} productos por {metric}")
    plt.xlabel(metric)
    url = _save_current_plot("top_products")
    return _serialize({"chart_url": url, "n_items": len(series)})


def _h_plot_sales_by_country(top_n: int = 10, metric: str = "revenue") -> str:
    df = _filter_returns(load_data())
    col = "TotalPrice" if metric == "revenue" else "Quantity"
    series = df.groupby("Country")[col].sum().sort_values(ascending=False).head(top_n)

    plt.figure(figsize=(10, 6))
    series.plot(kind="bar")
    plt.title(f"Top {top_n} países por {col}")
    plt.ylabel(col)
    plt.xticks(rotation=45, ha="right")
    url = _save_current_plot("sales_by_country")
    return _serialize({"chart_url": url})


def _h_plot_monthly_sales(country: str | None = None, metric: str = "revenue") -> str:
    df = _filter_returns(load_data())
    if country:
        df = df[df["Country"].str.lower() == country.lower()]
        if df.empty:
            return json.dumps({"error": f"No hay datos para Country='{country}'"})

    col = "TotalPrice" if metric == "revenue" else "Quantity"
    monthly = df.groupby(df["InvoiceDate"].dt.to_period("M"))[col].sum()
    monthly.index = monthly.index.to_timestamp()

    plt.figure(figsize=(11, 5))
    monthly.plot(kind="line", marker="o")
    title_suffix = f" — {country}" if country else ""
    plt.title(f"Ventas mensuales ({col}){title_suffix}")
    plt.ylabel(col)
    plt.grid(alpha=0.3)
    url = _save_current_plot("monthly_sales")
    return _serialize({"chart_url": url})


def _h_search_knowledge_base(query: str, num_results: int = 5) -> str:
    """RAG sobre la Knowledge Base de Bedrock para conocimiento del sector retail."""
    s = get_settings()
    if not s.knowledge_base_id:
        return json.dumps({
            "error": "Knowledge Base no configurada. Define KNOWLEDGE_BASE_ID en el entorno.",
            "fallback": "Responde con conocimiento general o usa las otras herramientas de pandas.",
        })
    chunks = retrieve_from_kb(query=query, num_results=num_results)
    return _serialize({"query": query, "results": chunks})


# --------------------------------------------------------------------------- #
# Definiciones de tools (formato Anthropic)
# --------------------------------------------------------------------------- #
@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., str]

    def to_anthropic_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


TOOLS: list[Tool] = [
    Tool(
        name="describe_dataset",
        description=(
            "Devuelve un resumen general del dataset de retail: rango de fechas, "
            "número de filas, productos, clientes, países, revenue total. "
            "Úsalo SIEMPRE como primer paso si no sabes qué hay en los datos."
        ),
        input_schema={"type": "object", "properties": {}},
        handler=_h_describe_dataset,
    ),
    Tool(
        name="top_products",
        description=(
            "Top productos por cantidad vendida o por revenue. Devuelve un dict "
            "{producto: valor}. Para preguntas tipo '¿cuáles son los productos "
            "más vendidos?' o '¿qué genera más ingresos?'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "top_n": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
                "by": {"type": "string", "enum": ["quantity", "revenue"], "default": "quantity"},
            },
        },
        handler=_h_top_products,
    ),
    Tool(
        name="sales_by_country",
        description="Ventas agregadas por país. Útil para preguntas de distribución geográfica.",
        input_schema={
            "type": "object",
            "properties": {
                "top_n": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
                "metric": {"type": "string", "enum": ["revenue", "quantity"], "default": "revenue"},
            },
        },
        handler=_h_sales_by_country,
    ),
    Tool(
        name="monthly_sales",
        description="Serie temporal mensual de ventas. Acepta filtro opcional por país.",
        input_schema={
            "type": "object",
            "properties": {
                "country": {"type": "string", "description": "Filtra por país (opcional)"},
                "metric": {"type": "string", "enum": ["revenue", "quantity"], "default": "revenue"},
            },
        },
        handler=_h_monthly_sales,
    ),
    Tool(
        name="detect_anomalies",
        description=(
            "Detecta transacciones anómalas con Isolation Forest sobre Quantity y "
            "UnitPrice. Útil para preguntas sobre outliers, fraude potencial o "
            "patrones inusuales."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "contamination": {
                    "type": "number",
                    "minimum": 0.001,
                    "maximum": 0.1,
                    "default": 0.01,
                    "description": "Proporción esperada de anomalías",
                }
            },
        },
        handler=_h_detect_anomalies,
    ),
    Tool(
        name="plot_top_products",
        description=(
            "Genera un gráfico de barras horizontales con los top productos. "
            "Devuelve una URL al PNG. Úsalo cuando el usuario pida 'gráfico', "
            "'visualización', 'chart' o 'gráfico'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "top_n": {"type": "integer", "minimum": 1, "maximum": 30, "default": 10},
                "by": {"type": "string", "enum": ["quantity", "revenue"], "default": "quantity"},
            },
        },
        handler=_h_plot_top_products,
    ),
    Tool(
        name="plot_sales_by_country",
        description="Gráfico de barras con ventas por país. Devuelve URL al PNG.",
        input_schema={
            "type": "object",
            "properties": {
                "top_n": {"type": "integer", "minimum": 1, "maximum": 30, "default": 10},
                "metric": {"type": "string", "enum": ["revenue", "quantity"], "default": "revenue"},
            },
        },
        handler=_h_plot_sales_by_country,
    ),
    Tool(
        name="plot_monthly_sales",
        description="Gráfico de línea con la evolución mensual de ventas. Devuelve URL al PNG.",
        input_schema={
            "type": "object",
            "properties": {
                "country": {"type": "string"},
                "metric": {"type": "string", "enum": ["revenue", "quantity"], "default": "revenue"},
            },
        },
        handler=_h_plot_monthly_sales,
    ),
    Tool(
        name="search_knowledge_base",
        description=(
            "Busca en la base de conocimiento del sector retail información "
            "cualitativa: definiciones, frameworks, benchmarks de industria, "
            "best practices, glosario. Úsala cuando la pregunta NO se puede "
            "responder con cálculos sobre el dataset (ej: '¿qué es churn rate?', "
            "'¿qué KPIs son típicos en retail?', '¿cómo se calcula el customer "
            "lifetime value?')."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Consulta semántica"},
                "num_results": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
            },
            "required": ["query"],
        },
        handler=_h_search_knowledge_base,
    ),
]


# --------------------------------------------------------------------------- #
# Dispatcher
# --------------------------------------------------------------------------- #
_TOOL_BY_NAME = {t.name: t for t in TOOLS}


def get_tool_specs() -> list[dict[str, Any]]:
    """Devuelve la lista de tools en formato Anthropic para pasar al LLM."""
    return [t.to_anthropic_dict() for t in TOOLS]


def execute_tool(name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
    """
    Ejecuta una tool por nombre. Devuelve (resultado_string, is_error).
    No deja escapar excepciones: las captura y las devuelve como tool_result
    de error, así el LLM puede recuperarse.
    """
    tool = _TOOL_BY_NAME.get(name)
    if tool is None:
        return json.dumps({"error": f"Tool desconocida: {name}"}), True

    try:
        logger.info("Ejecutando tool %s con input=%s", name, tool_input)
        result = tool.handler(**(tool_input or {}))
        return result, False
    except Exception as exc:  # noqa: BLE001 — queremos capturar todo para el agente
        logger.exception("Error ejecutando tool %s", name)
        return json.dumps({"error": str(exc), "type": type(exc).__name__}), True