"""FastMCP server registration."""

from __future__ import annotations

from typing import TypeVar

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from .errors import DarktableMcpError
from .models import (
    AdjustmentPatch,
    ErrorInfo,
    ExportResult,
    PreviewResult,
    RenderMode,
    SessionEnvelope,
    SupportedAdjustmentsResult,
)
from .session import SessionManager

SessionResultT = TypeVar("SessionResultT", bound=BaseModel)


def create_server() -> FastMCP:
    """Create the FastMCP server instance."""

    session_manager = SessionManager()
    mcp = FastMCP(
        "mcp-photo-edit",
        instructions=(
            "Create edit sessions, apply structured photo adjustments, "
            "inspect previews, and export final images."
        ),
    )

    @mcp.tool()
    def create_edit_session(
        input_path: str,
        preview_max_size: int = 1024,
        session_label: str | None = None,
    ) -> SessionEnvelope:
        """Create an edit session from an input image path."""

        try:
            session = session_manager.create_session(
                input_path,
                preview_max_size=preview_max_size,
                session_label=session_label,
            )
            return SessionEnvelope(session=session)
        except DarktableMcpError as exc:
            return _session_error(exc)

    @mcp.tool()
    def get_edit_session(session_id: str) -> SessionEnvelope:
        """Fetch the current state for an existing session."""

        try:
            return SessionEnvelope(session=session_manager.get_session(session_id))
        except DarktableMcpError as exc:
            return _session_error(exc)

    @mcp.tool()
    def render_preview(
        session_id: str,
        mode: RenderMode = RenderMode.CURRENT,
        preview_max_size: int | None = None,
    ) -> PreviewResult:
        """Explicitly (re)render a session preview."""

        try:
            session = session_manager.render_preview(
                session_id,
                mode=mode,
                preview_max_size=preview_max_size,
            )
            return PreviewResult(
                session_id=session.session_id,
                preview_path=session.preview_path,
                mode=session.preview_mode,
                last_rendered_at=session.last_rendered_at,
            )
        except DarktableMcpError as exc:
            return PreviewResult(ok=False, error=_error_info(exc))

    @mcp.tool()
    def apply_adjustments(
        session_id: str,
        adjustments: AdjustmentPatch,
        render_preview: bool = True,
    ) -> SessionEnvelope:
        """Apply a partial adjustment patch to a session."""

        try:
            session = session_manager.apply_adjustments(
                session_id,
                adjustments,
                render_preview=render_preview,
            )
            return SessionEnvelope(session=session)
        except DarktableMcpError as exc:
            return _session_error(exc)

    @mcp.tool()
    def reset_adjustments(
        session_id: str,
        fields: list[str] | None = None,
        render_preview: bool = True,
    ) -> SessionEnvelope:
        """Reset all or selected adjustment keys back to defaults."""

        try:
            session = session_manager.reset_adjustments(
                session_id,
                fields,
                render_preview=render_preview,
            )
            return SessionEnvelope(session=session)
        except DarktableMcpError as exc:
            return _session_error(exc)

    @mcp.tool()
    def export_image(session_id: str, output_path: str) -> ExportResult:
        """Export the current session state to a final output path."""

        try:
            session = session_manager.get_session(session_id)
            output = session_manager.export_image(session_id, output_path)
            return ExportResult(
                session_id=session_id,
                output_path=str(output),
                format=output.suffix.lstrip(".").lower(),
                backend=session.backend,
            )
        except DarktableMcpError as exc:
            return ExportResult(ok=False, error=_error_info(exc))

    @mcp.tool()
    def list_supported_adjustments() -> SupportedAdjustmentsResult:
        """List supported adjustments, ranges, defaults, and examples."""

        return SupportedAdjustmentsResult(
            adjustments=session_manager.list_supported_adjustments()
        )

    return mcp


def _error_info(error: DarktableMcpError) -> ErrorInfo:
    return ErrorInfo(code=error.code, message=error.message, hint=error.hint)


def _session_error(error: DarktableMcpError) -> SessionEnvelope:
    return SessionEnvelope(ok=False, error=_error_info(error))
