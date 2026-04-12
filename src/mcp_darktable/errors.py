"""Structured error types for MCP tool responses."""

from __future__ import annotations


class DarktableMcpError(Exception):
    """Base error carrying an agent-readable code and hint."""

    def __init__(self, code: str, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


class SessionNotFoundError(DarktableMcpError):
    """Raised when a session id cannot be resolved."""

    def __init__(self, session_id: str) -> None:
        super().__init__(
            code="invalid_session",
            message=f"Session '{session_id}' was not found.",
            hint="Create a new session first or verify the session_id.",
        )


class ValidationError(DarktableMcpError):
    """Raised for invalid user-supplied values."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(code="validation_error", message=message, hint=hint)


class BackendUnavailableError(DarktableMcpError):
    """Raised when darktable-cli cannot be executed."""

    def __init__(self, executable: str) -> None:
        super().__init__(
            code="backend_unavailable",
            message=f"Required backend executable '{executable}' is not available.",
            hint="Install darktable-cli and ensure it is on PATH.",
        )


class RenderFailedError(DarktableMcpError):
    """Raised when darktable-cli returns a non-zero status or no file."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(code="render_failed", message=message, hint=hint)
