# pyright: reportUnusedFunction=false
"""FastMCP server registration."""

from __future__ import annotations

from typing import TypeVar

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from .backend import LocalFileBackend
from .errors import PhotoEditError
from .interfaces import SessionEditBackend
from .models import (
    AdjustmentPatch,
    ErrorInfo,
    ExportResult,
    PreviewResult,
    SessionEnvelope,
    SupportedAdjustmentsResult,
)

SessionResultT = TypeVar("SessionResultT", bound=BaseModel)


def create_server(backend: SessionEditBackend | None = None) -> FastMCP:
    """Create the FastMCP server instance."""

    edit_backend = backend or LocalFileBackend()
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
            session = edit_backend.create_session(
                input_path,
                preview_max_size=preview_max_size,
                session_label=session_label,
            )
            return SessionEnvelope(session=session)
        except PhotoEditError as exc:
            return _session_error(exc)

    @mcp.tool()
    def get_edit_session(session_id: str) -> SessionEnvelope:
        """Fetch the current state for an existing session."""

        try:
            return SessionEnvelope(session=edit_backend.get_session(session_id))
        except PhotoEditError as exc:
            return _session_error(exc)

    @mcp.tool()
    def render_preview(
        session_id: str,
        preview_max_size: int | None = None,
    ) -> PreviewResult:
        """Explicitly (re)render the current session preview."""

        try:
            session = edit_backend.render_preview(
                session_id,
                preview_max_size=preview_max_size,
            )
            return PreviewResult(
                session_id=session.session_id,
                preview_path=session.preview_path,
                diagnostic_dashboard_path=session.diagnostic_dashboard_path,
                diagnostic_summary=session.diagnostic_summary,
                preview_count=len(session.preview_history),
                preview_history=session.preview_history,
                history_index=session.history_index,
                history_length=session.history_length,
                can_undo=session.can_undo,
                can_redo=session.can_redo,
                last_rendered_at=session.last_rendered_at,
            )
        except PhotoEditError as exc:
            return PreviewResult(ok=False, error=_error_info(exc))

    @mcp.tool()
    def apply_adjustments(
        session_id: str,
        adjustments: AdjustmentPatch,
        render_preview: bool = True,
    ) -> SessionEnvelope:
        """Apply a partial adjustment patch to a session."""

        try:
            session = edit_backend.apply_adjustments(
                session_id,
                adjustments,
                render_preview=render_preview,
            )
            return SessionEnvelope(session=session)
        except PhotoEditError as exc:
            return _session_error(exc)

    @mcp.tool()
    def reset_adjustments(
        session_id: str,
        fields: list[str] | None = None,
        render_preview: bool = True,
    ) -> SessionEnvelope:
        """Reset all or selected adjustment keys back to defaults."""

        try:
            session = edit_backend.reset_adjustments(
                session_id,
                fields,
                render_preview=render_preview,
            )
            return SessionEnvelope(session=session)
        except PhotoEditError as exc:
            return _session_error(exc)

    @mcp.tool()
    def export_image(session_id: str, output_path: str) -> ExportResult:
        """Export the current session state to a final output path."""

        try:
            session = edit_backend.get_session(session_id)
            output = edit_backend.export_image(session_id, output_path)
            return ExportResult(
                session_id=session_id,
                output_path=str(output),
                format=output.suffix.lstrip(".").lower(),
                backend=session.backend,
            )
        except PhotoEditError as exc:
            return ExportResult(ok=False, error=_error_info(exc))

    @mcp.tool()
    def undo_adjustment(
        session_id: str,
        render_preview: bool = False,
    ) -> SessionEnvelope:
        """Move the current session to the previous committed adjustment state."""

        try:
            session = edit_backend.undo_adjustment(
                session_id,
                render_preview=render_preview,
            )
            return SessionEnvelope(session=session)
        except PhotoEditError as exc:
            return _session_error(exc)

    @mcp.tool()
    def redo_adjustment(
        session_id: str,
        render_preview: bool = False,
    ) -> SessionEnvelope:
        """Move the current session to the next committed adjustment state."""

        try:
            session = edit_backend.redo_adjustment(
                session_id,
                render_preview=render_preview,
            )
            return SessionEnvelope(session=session)
        except PhotoEditError as exc:
            return _session_error(exc)

    @mcp.tool()
    def list_supported_adjustments() -> SupportedAdjustmentsResult:
        """List supported adjustments, ranges, defaults, and examples."""

        return SupportedAdjustmentsResult(adjustments=edit_backend.list_supported_adjustments())

    return mcp


def _error_info(error: PhotoEditError) -> ErrorInfo:
    return ErrorInfo(code=error.code, message=error.message, hint=error.hint)


def _session_error(error: PhotoEditError) -> SessionEnvelope:
    return SessionEnvelope(ok=False, error=_error_info(error))
