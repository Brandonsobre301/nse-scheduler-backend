# NSE Scheduler — AI Microservice (FastAPI)
# Internal service only — not exposed to the public internet.
# All traffic routes through the Node.js backend on app-net.

FROM python:3.12-slim

WORKDIR /app

# Install CPU-only PyTorch first so sentence-transformers binds to it
# instead of the larger CUDA build (~500 MB vs ~2 GB).
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining runtime deps (Phase 1 + Phase 2 sentence-transformers).
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# Copy application source
COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
