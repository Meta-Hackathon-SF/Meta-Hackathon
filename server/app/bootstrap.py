"""Explicit configured backend entrypoint, never an in-memory production fallback.

Run uvicorn server.app.bootstrap:create_configured_app --factory --no-access-log.
No provider is called during construction or readiness checks.
"""

import os
from contextlib import asynccontextmanager

from server.app.main import create_app
from server.app.weekly import build_weekly_app
from server.orchestration.storage import PostgresWorkflowRepository
from server.privacy import PrivacyStore


def create_configured_app():
    dsn = os.getenv("CONSTELLATIONS_WORKFLOW_DSN")
    privacy_path = os.getenv("CST_PRIVACY_DB")
    if not dsn or not privacy_path:
        return create_app()  # explicit not-ready baseline, no fake sessions/routes
    if privacy_path == ":memory:":
        raise ValueError("Configured backend requires a durable privacy database file")
    repository = PostgresWorkflowRepository(dsn)
    if not repository.ready():
        repository.close()
        return create_app()
    store = PrivacyStore(privacy_path)
    try:
        app = build_weekly_app(repository=repository, privacy_store=store)
    except Exception:
        store.close()
        repository.close()
        raise
    previous = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        try:
            async with previous(application):
                yield
        finally:
            store.close()
            repository.close()

    app.router.lifespan_context = lifespan
    return app
