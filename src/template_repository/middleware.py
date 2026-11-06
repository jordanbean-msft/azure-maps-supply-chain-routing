import logging
import re
import time
from collections import deque
from contextvars import ContextVar
from uuid import uuid4

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from template_repository.config import Settings

request_id_context: ContextVar[str] = ContextVar("request_id", default="")
logger = logging.getLogger(__name__)


class GuardMiddleware:
    """Single-replica demo budgets, no trust in spoofable forwarded-client headers."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app, self.settings = app, settings
        self.requests: deque[float] = deque()
        self.expensive: deque[float] = deque()

    def _budget(self, values: deque[float], limit: int) -> bool:
        now = time.monotonic()
        while values and values[0] < now - 60:
            values.popleft()
        if len(values) >= limit:
            return False
        values.append(now)
        return True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", supplied) else uuid4().hex
        context = request_id_context.set(request_id)
        started = time.monotonic()
        response_status = 500

        async def send_with_context(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
                message["headers"].append((b"x-request-id", request_id.encode()))
                if scope["path"] == "/api/maps/token":
                    message["headers"] = [
                        (key, value)
                        for key, value in message["headers"]
                        if key.lower() != b"cache-control"
                    ]
                    message["headers"].append((b"cache-control", b"no-store"))
            await send(message)

        async def reject(status: int, detail: str) -> None:
            response = JSONResponse(
                {
                    "type": "about:blank",
                    "title": "Request rejected",
                    "status": status,
                    "detail": detail,
                    "instance": scope["path"],
                },
                status_code=status,
                media_type="application/problem+json",
                headers={"Retry-After": "60"} if status == 429 else None,
            )
            await response(scope, receive, send_with_context)

        try:
            if scope["path"].startswith("/health"):
                await self.app(scope, receive, send_with_context)
                return
            if not self._budget(self.requests, self.settings.requests_per_minute):
                await reject(429, "Request budget exceeded.")
                return
            expensive = scope["path"].endswith(
                ("/optimize", "/locations:geocode", "/seed", "/maps/token")
            ) or (request.method == "POST" and scope["path"] == "/api/scenarios")
            if expensive and not self._budget(
                self.expensive, self.settings.expensive_requests_per_minute
            ):
                await reject(429, "Maps/creation transaction budget exceeded.")
                return
            origin = request.headers.get("origin")
            same_origin = f"{request.url.scheme}://{request.url.netloc}"
            if (
                request.method not in {"GET", "HEAD", "OPTIONS"}
                and origin
                and origin not in [same_origin, *self.settings.maps_allowed_origins]
            ):
                await reject(403, "Origin is not allowed.")
                return
            chunks = []
            size = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                size += len(message.get("body", b""))
                if size > self.settings.max_request_bytes:
                    await reject(413, "Request body exceeds demo size limit.")
                    return
                chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            delivered = False

            async def replay() -> Message:
                nonlocal delivered
                if delivered:
                    return await receive()
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}

            await self.app(scope, replay, send_with_context)
        finally:
            logger.info(
                "http_request",
                extra={
                    "request_id": request_id,
                    "path": scope["path"],
                    "method": request.method,
                    "status_code": response_status,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                },
            )
            request_id_context.reset(context)
