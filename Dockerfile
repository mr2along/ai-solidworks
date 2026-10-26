# Hugging Face Docker Space: frontend + FastAPI + headless FreeCAD
FROM node:20-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Keep Debian FreeCAD and its embedded Python paired with Debian's system Python.
FROM debian:bookworm-slim AS runtime
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FREECAD_CMD=/usr/lib/freecad/bin/freecadcmd-python3 \
    CAD_MAX_RUNTIME_SECONDS=90
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip python3-venv \
      freecad freecad-python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv --system-site-packages \
    && useradd --create-home --uid 1000 appuser
ENV PATH="/opt/venv/bin:${PATH}"
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=appuser:appuser backend/ ./backend/
COPY --chown=appuser:appuser cad/ ./cad/
COPY --from=frontend-build --chown=appuser:appuser /build/frontend/dist ./frontend/dist
USER appuser
RUN "$FREECAD_CMD" /app/cad/freecad_smoke.py
EXPOSE 7860
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
