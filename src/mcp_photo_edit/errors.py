"""Structured error types for MCP tool responses."""

from __future__ import annotations


class PhotoEditError(Exception):
    """Base error carrying an agent-readable code and hint."""

    def __init__(self, code: str, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


class SessionNotFoundError(PhotoEditError):
    """Raised when a session id cannot be resolved."""

    def __init__(self, session_id: str) -> None:
        super().__init__(
            code="invalid_session",
            message=f"Session '{session_id}' was not found.",
            hint="Create a new session first or verify the session_id.",
        )


class ValidationError(PhotoEditError):
    """Raised for invalid user-supplied values."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(code="validation_error", message=message, hint=hint)


class BackendUnavailableError(PhotoEditError):
    """Raised when a configured backend executable cannot be executed."""

    def __init__(self, executable: str) -> None:
        super().__init__(
            code="backend_unavailable",
            message=f"Required backend executable '{executable}' is not available.",
            hint=f"Install {executable} and ensure it is on PATH.",
        )


class RenderFailedError(PhotoEditError):
    """Raised when a backend returns a non-zero status or no file."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(code="render_failed", message=message, hint=hint)
