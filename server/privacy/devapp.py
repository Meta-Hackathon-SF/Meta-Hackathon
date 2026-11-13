"""LOCAL PRIVACY DEV HARNESS - not the Facebook Space server.

Kai owns API composition (server/app/). Until it is restored on main, this
mounts only the privacy router so the consent UI and other owners can exercise
join, sessions and consent locally. No database server needed:

    CST_PRIVACY_DB=/tmp/constellations-privacy.db CST_COOKIE_INSECURE_DEV=1 \
    server/.venv/bin/uvicorn server.privacy.devapp:app --port 8787
"""

import os

from fastapi import FastAPI

from server.privacy import PrivacyService, PrivacyStore, build_router, install_error_handlers

app = FastAPI(title="Facebook Space privacy dev harness (local only)")
install_error_handlers(app)
_service = PrivacyService(PrivacyStore(os.environ.get("CST_PRIVACY_DB", ":memory:")))
app.include_router(build_router(_service), prefix="/api/v1")


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok" if _service.ready() else "unavailable", "scope": "privacy-dev-harness"}
