"""Pure ASGI middleware preserves future SSE delivery without buffering responses."""

import logging
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from server.app.errors import error_response

logger = logging.getLogger("constellations.app")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Request-Id"] = request_id
                headers["X-Content-Type-Options"] = "nosniff"
                if scope["path"].startswith("/api/"):
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_headers)


class SanitizedErrorsMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def track_start(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, track_start)
        except Exception:
            # No exception text, request URL/body, transcript, tokens, or traceback in logs.
            logger.error("Request failed; requestId=%s", scope["state"]["request_id"])
            if started:
                # A stream has already begun. Do not send a second header/body envelope.
                raise
            await error_response(Request(scope), "PROVIDER_UNAVAILABLE")(scope, receive, send)
