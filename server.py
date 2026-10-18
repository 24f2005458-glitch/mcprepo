import hashlib
import os
from contextvars import ContextVar

import uvicorn
from mcp.server.fastmcp import FastMCP

# Configure this with the email address expected by the grader.
NORMALIZED_EMAIL = os.environ["EXAM_EMAIL"].strip().lower()

# One value per incoming HTTP request.
request_challenge: ContextVar[str | None] = ContextVar(
    "request_challenge", default=None
)

mcp = FastMCP("exam-challenge-server")


@mcp.tool()
def solve_challenge() -> str:
    """Solve the current exam challenge using the HTTP request headers."""
    challenge = request_challenge.get()

    if challenge is None:
        raise ValueError("Missing X-Exam-Challenge request header")

    message = f"{challenge}:{NORMALIZED_EMAIL}"
    digest = hashlib.sha256(message.encode("utf-8")).hexdigest()

    # Return the required 16 lowercase hexadecimal characters.
    return digest[:16]


class ChallengeHeaderMiddleware:
    """Capture the challenge separately for every HTTP request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            key.lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }

        challenge = headers.get("x-exam-challenge")
        token = request_challenge.set(challenge)

        try:
            await self.app(scope, receive, send)
        finally:
            request_challenge.reset(token)


app = ChallengeHeaderMiddleware(mcp.streamable_http_app())

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
    )


