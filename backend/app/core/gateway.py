"""Authenticate HTTPS transport attestations; never interpret forwarded headers.

The gateway signs only after receiving HTTPS and uses HTTPS to this origin.
The shared credential attests transport, not the user's identity. Owner login
and all existing authorization remain mandatory. v1 supports explicitly configured disposable and online modes.
"""

import hashlib
import hmac
import re
import time

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

MAX_BODY = 65536
PROOF_SECONDS = 120  # Permit the usual Free-instance wake-up before verification.
SIGNED_HEADERS = (b"authorization", b"content-type", b"origin", b"x-csrf-token")
PROOF_HEADERS = (
    b"x-maritime-gateway-time",
    b"x-maritime-gateway-nonce",
    b"x-maritime-gateway-signature",
)


def canonical_message(scope, headers, body):
    """ASCII HTTP fields, LF-separated; header values cannot contain CR/LF."""
    fields = [
        b"maritime-gateway-v1-https",
        headers[PROOF_HEADERS[0]],
        headers[PROOF_HEADERS[1]],
        scope["method"].encode("ascii"),
        headers[b"host"],
        scope["raw_path"],
        scope["query_string"],
        *(headers.get(name, b"") for name in SIGNED_HEADERS),
        hashlib.sha256(body).hexdigest().encode("ascii"),
    ]
    if any(b"\n" in value or b"\r" in value for value in fields):
        raise ValueError("Ambiguous gateway field")
    return b"\n".join(fields)


def consume_nonce(engine, nonce, now):
    # Reuse the existing durable security-window table; retention exceeds proof TTL.
    with engine.begin() as connection:
        connection.execute(
            text(
                "DELETE FROM rate_windows WHERE key LIKE 'gateway:%' AND \"window\" < :old"
            ),
            {"old": int(now) // 60 - 2},
        )
        result = connection.execute(
            text(
                'INSERT INTO rate_windows(key,"window",count) VALUES (:key,:window,1) ON CONFLICT DO NOTHING'
            ),
            # The existing auth-window cleanup must retain this beyond TTL + skew.
            {"key": "gateway:" + nonce, "window": int(now) // 60 + 1},
        )
        return result.rowcount == 1


class SignedGatewayMiddleware:
    def __init__(self, app, engine, secret, upload_limit=MAX_BODY):
        self.app, self.engine, self.key = app, engine, bytes.fromhex(secret)
        self.upload_limit = upload_limit

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)
        if scope["type"] != "http":
            return await send({"type": "websocket.close", "code": 1008})
        try:
            protected = {b"host", *SIGNED_HEADERS, *PROOF_HEADERS}
            headers = {}
            for name, value in scope["headers"]:
                name = name.lower()
                if name in protected:
                    if name in headers:
                        raise ValueError("Duplicate gateway field")
                    headers[name] = value
            stamp = headers[PROOF_HEADERS[0]].decode("ascii")
            nonce = headers[PROOF_HEADERS[1]].decode("ascii")
            signature = headers[PROOF_HEADERS[2]].decode("ascii")
            now = time.time()
            if (
                not re.fullmatch(r"[0-9]{10}", stamp)
                or not -5 <= now - int(stamp) <= PROOF_SECONDS
                or not re.fullmatch(r"[0-9a-f]{32}", nonce)
                or not re.fullmatch(r"[0-9a-f]{64}", signature)
            ):
                raise ValueError("Invalid or expired proof")
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                part = message.get("body", b"")
                limit = (
                    self.upload_limit
                    if scope["method"] == "POST" and scope["path"] == "/api/documents"
                    else MAX_BODY
                )
                if len(body) + len(part) > limit:
                    raise ValueError("Gateway body too large")
                body.extend(part)
                if not message.get("more_body", False):
                    break
            expected = hmac.new(
                self.key, canonical_message(scope, headers, body), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError("Invalid gateway proof")
            if not await run_in_threadpool(consume_nonce, self.engine, nonce, now):
                raise ValueError("Replayed gateway proof")
        except (ValueError, KeyError, UnicodeError, SQLAlchemyError):
            response = JSONResponse(
                {
                    "detail": {
                        "code": "gateway_authentication_required",
                        "message": "Secure connection could not be verified. Try again shortly.",
                    }
                },
                status_code=401,
                headers={
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                },
            )
            return await response(scope, receive, send)

        authenticated = dict(scope)
        authenticated["scheme"] = "https"
        authenticated["headers"] = [
            (name, value)
            for name, value in scope["headers"]
            if name.lower()
            not in {
                *PROOF_HEADERS,
                b"forwarded",
                b"x-forwarded-proto",
                b"x-forwarded-for",
                b"x-forwarded-host",
            }
        ]
        replayed = False

        async def replay_body():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        return await self.app(authenticated, replay_body, send)
