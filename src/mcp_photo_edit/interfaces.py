"""Typed backend protocols for MCP orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import (
    AdjustmentPatch,
    AdjustmentSpec,
    AdjustmentState,
    DiagnosticSummary,
    SessionState,
    SourceImageInfo,
)


class SessionRenderBackend(Protocol):
    """Internal adapter used by session persistence and artifact orchestration."""

    backend_id: str
    state_file_name: str
    supported_adjustment_names: tuple[str, ...]

    def write_state_file(
        self,
        source: SourceImageInfo,
        adjustments: AdjustmentState,
        state_path: Path,
    ) -> None: ...

    def render_preview(
        self,
        source_path: Path,
        state_path: Path,
        target_path: Path,
        *,
        max_size: int | None = None,
    ) -> tuple[int, int] | None: ...

    def render_export(
        self,
        source_path: Path,
        state_path: Path,
        target_path: Path,
    ) -> tuple[int, int] | None: ...

    def diagnostics_for(self, output_path: Path) -> DiagnosticSummary | None: ...


class EditBackend(Protocol):
    """Use-case API consumed by the MCP transport."""

    def create_session(
        self,
        input_path: str,
        *,
        preview_max_size: int = 1024,
        session_label: str | None = None,
    ) -> SessionState: ...

    def get_session(self, session_id: str) -> SessionState: ...

    def apply_adjustments(
        self,
        session_id: str,
        patch: AdjustmentPatch,
        *,
        render_preview: bool = True,
    ) -> SessionState: ...

    def reset_adjustments(
        self,
        session_id: str,
        fields: list[str] | None = None,
        *,
        render_preview: bool = True,
    ) -> SessionState: ...

    def render_preview(
        self,
        session_id: str,
        *,
        preview_max_size: int | None = None,
    ) -> SessionState: ...

    def undo_adjustment(
        self,
        session_id: str,
        *,
        render_preview: bool = False,
    ) -> SessionState: ...

    def redo_adjustment(
        self,
        session_id: str,
        *,
        render_preview: bool = False,
    ) -> SessionState: ...

    def export_image(self, session_id: str, output_path: str) -> Path: ...

    def list_supported_adjustments(self) -> list[AdjustmentSpec]: ...
