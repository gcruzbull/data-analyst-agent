# syntax=docker/dockerfile:1.7
# Multi-stage build para minimizar el tamaño final.
# Etapa builder: compila las wheels. Etapa runtime: solo lo necesario para correr.

# ---------- builder ---------- #
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Dependencias de sistema solo para compilación
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Construir wheels en /build/wheels para copiarlos a la etapa final.
RUN pip wheel --wheel-dir=/build/wheels -r requirements.txt


# ---------- runtime ---------- #
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

# libgomp es requerido por scikit-learn en runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r app && useradd -r -g app app

WORKDIR /app

# Instalar dependencias desde wheels precompiladas.
COPY --from=builder /build/wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# Copiar el código.
COPY src ./src
COPY api ./api

# Copiar el dataset SOLO si existe; en producción es preferible montarlo
# desde S3/EFS o descargarlo en el entrypoint.
COPY data ./data

# Permisos.
RUN chown -R app:app /app
USER app

EXPOSE 8000

# Healthcheck contra el endpoint /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:${PORT}/health || exit 1

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --workers 2"]