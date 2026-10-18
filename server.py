
import hashlib
import os
import re
from contextvars import ContextVar

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings


# Set EXAM_EMAIL in Render's environment variables.
NORMALIZED_EMAIL = os.environ["EXAM_EMAIL"].strip().lower()

# Store the challenge independently for each request/task.
request_challenge: ContextVar[str | None] = ContextVar(
    "request_challenge",
    default=None,
)

# Create the MCP 2.x server.
mcp = MCPServer("exam-challenge-server")


@mcp.tool()
def solve_challenge() -> str:
    """Return the required hash for the challenge in the HTTP headers."""

    challenge = request_challenge.get()

    if challenge is None:
        raise ValueError("Missing X-Exam-Challenge header")

    # The grader sends 32 lowercase hexadecimal characters.
    if not re.fullmatch(r"[0-9a-f]{32}", challenge):
        raise ValueError("Invalid X-Exam-Challenge header")

    message = f"{challenge}:{NORMALIZED_EMAIL}"
    digest = hashlib.sha256(message.encode("utf-8")).hexdigest()

    return digest[:16]


class ChallengeHeaderMiddleware:
    """Capture the challenge from each incoming HTTP request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            # Forward lifespan and other ASGI scopes unchanged.
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


# Render sets this environment variable for deployed services.
render_host = os.environ.get(
    "RENDER_EXTERNAL_HOSTNAME",
    "localhost",
)

# Explicitly allow the public Render hostname to prevent HTTP 421.
security = TransportSecuritySettings(
    allowed_hosts=[
        render_host,
        f"{render_host}:*",
        "localhost",
        "localhost:*",
        "127.0.0.1",
        "127.0.0.1:*",
    ],
)

# Build the Streamable HTTP application.
mcp_app = mcp.streamable_http_app(
    transport_security=security,
)

# Export the ASGI application for Gunicorn.
app = ChallengeHeaderMiddleware(mcp_app)


