"""LOCAL PRIVACY DEV HARNESS - not the Group Quests server.

Kai owns server composition (server/app/). Until it exists, this mounts only the
privacy router so the privacy UI and other owners can exercise sessions,
consent and intents locally:

    db/privacy/dev-db.sh up
    GQ_DATABASE_URL=postgresql://gq_api_login@127.0.0.1:54329/postgres \
    GQ_COOKIE_INSECURE_DEV=1 \
    server/.venv/bin/uvicorn --app-dir server privacy.devapp:app --port 8787
"""

import os

from fastapi import FastAPI

from privacy import Database, PrivacyService, build_router, install_error_handlers

app = FastAPI(title="Group Quests privacy dev harness (local only)")
install_error_handlers(app)
_service = PrivacyService(Database(os.environ["GQ_DATABASE_URL"]))
app.include_router(build_router(_service), prefix="/api/v1")


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "scope": "privacy-dev-harness"}
