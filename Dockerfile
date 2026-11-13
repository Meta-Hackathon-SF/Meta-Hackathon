# Reconstructed from the Railway build log of the deployed image (2026-11-13).
# Start command lives in the Railway service settings:
#   python -m uvicorn server.app.bootstrap:create_configured_app --factory --host 0.0.0.0 --port 8000 --workers 1 --no-access-log
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY server ./server
COPY db ./db
COPY contracts ./contracts
RUN python -m pip install --no-cache-dir .
