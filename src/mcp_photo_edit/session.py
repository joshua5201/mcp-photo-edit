"""Session lifecycle and persistence."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from .errors import SessionNotFoundError, ValidationError
from .interfaces import SessionRenderBackend
from .models import (
    ADJUSTMENT_SPECS,
    RESETTABLE_FIELDS,
    AdjustmentPatch,
    AdjustmentSpec,
    AdjustmentState,
    HistoryStep,
    PreviewArtifact,
    SessionState,
    SourceImageInfo,
    utc_now,
)


class SessionManager:
    """Manage edit sessions and their workspace artifacts."""

    def __init__(
        self,
        workspace_root: Path | None = None,
        backend: SessionRenderBackend | None = None,
    ) -> None:
        configured_workdir = os.environ.get("MCP_PHOTO_EDIT_WORKDIR") or os.environ.get(
            "MCP_DARKTABLE_WORKDIR"
        )
        default_root = Path(configured_workdir or ".mcp-photo-edit")
        self.workspace_root = (workspace_root or default_root).resolve()
        if backend is None:
            from .backend import ServiceRenderBackend

            backend = ServiceRenderBackend()
        self.backends: dict[str, SessionRenderBackend] = {backend.backend_id: backend}
        self.default_backend_id = backend.backend_id
        self.advanced_image_info_enabled = not _env_flag_enabled(
            os.environ.get("DISABLE_ADVANCED_IMAGE_INFO")
        )
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        input_path: str,
        *,
        preview_max_size: int = 1024,
        session_label: str | None = None,
    ) -> SessionState:
        """Create a new session and render its first preview."""

        source_path = self._resolve_source(input_path)
        session_id = uuid.uuid4().hex[:12]
        session_dir = self.workspace_root / session_id
        session_dir.mkdir(parents=True, exist_ok=False)
        backend = self.backends[self.default_backend_id]
        state_path = session_dir / backend.state_file_name
        initial_adjustments = AdjustmentState()
        initial_step = HistoryStep(
            step_id=self._next_step_id(0),
            kind="init",
            adjustments=initial_adjustments,
            state_path=str(self._history_state_path(session_dir, 1)),
        )

        session = SessionState(
            session_id=session_id,
            session_label=session_label,
            source=SourceImageInfo.from_path(source_path),
            workspace_dir=str(session_dir),
            state_path=str(state_path),
            preview_path="",
            preview_max_size=preview_max_size,
            adjustments=initial_adjustments,
            history=[initial_step],
            history_index=0,
            backend=backend.backend_id,
        )
        self._commit_step_artifacts(session, initial_step, render_preview=True)
        self._save_session(session)
        return session

    def get_session(self, session_id: str) -> SessionState:
        """Load a persisted session."""

        manifest_path = self._manifest_path(session_id)
        if not manifest_path.exists():
            raise SessionNotFoundError(session_id)
        session = SessionState.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        self._apply_advanced_image_info_gate(session)
        return session

    def apply_adjustments(
        self,
        session_id: str,
        patch: AdjustmentPatch,
        *,
        render_preview: bool = True,
    ) -> SessionState:
        """Update a session with a partial patch."""

        session = self.get_session(session_id)
        try:
            adjustments = session.adjustments.apply_patch(patch)
        except PydanticValidationError as exc:
            raise ValidationError(str(exc)) from exc
        return self._append_history_step(
            session,
            adjustments=adjustments,
            kind="apply_adjustments",
            render_preview=render_preview,
        )

    def reset_adjustments(
        self,
        session_id: str,
        fields: list[str] | None = None,
        *,
        render_preview: bool = True,
    ) -> SessionState:
        """Reset all or selected adjustment keys."""

        if fields:
            invalid = sorted(set(fields) - set(RESETTABLE_FIELDS))
            if invalid:
                supported = ", ".join(RESETTABLE_FIELDS)
                raise ValidationError(
                    f"Unsupported reset fields: {', '.join(invalid)}.",
                    hint=f"Supported resettable fields: {supported}.",
                )

        session = self.get_session(session_id)
        adjustments = session.adjustments.reset_fields(fields)
        return self._append_history_step(
            session,
            adjustments=adjustments,
            kind="reset_adjustments",
            render_preview=render_preview,
        )

    def export_image(self, session_id: str, output_path: str) -> Path:
        """Render the current session state to a final output path."""

        session = self.get_session(session_id)
        output = Path(output_path).expanduser().resolve()
        backend = self._backend_for_session(session)
        state_path = self._state_path(session)
        backend.render_export(Path(session.source.input_path), state_path, output)
        session.touch()
        session.last_rendered_at = utc_now()
        self._save_session(session)
        return output

    def render_preview(
        self,
        session_id: str,
        *,
        preview_max_size: int | None = None,
    ) -> SessionState:
        """Explicitly (re)render the current session preview."""

        session = self.get_session(session_id)
        if preview_max_size is not None:
            session.preview_max_size = preview_max_size

        self._render_preview(session)
        self._save_session(session)
        return session

    def undo_adjustment(
        self,
        session_id: str,
        *,
        render_preview: bool = False,
    ) -> SessionState:
        """Move the session cursor to the previous committed state."""

        session = self.get_session(session_id)
        if not session.can_undo:
            raise ValidationError(
                f"Session '{session_id}' has no earlier history step.",
                hint="Apply at least one edit before using undo.",
            )
        session.history_index -= 1
        self._restore_current_step(session, render_preview=render_preview)
        self._save_session(session)
        return session

    def redo_adjustment(
        self,
        session_id: str,
        *,
        render_preview: bool = False,
    ) -> SessionState:
        """Move the session cursor to the next committed state."""

        session = self.get_session(session_id)
        if not session.can_redo:
            raise ValidationError(
                f"Session '{session_id}' has no later history step.",
                hint="Undo to an earlier step before using redo.",
            )
        session.history_index += 1
        self._restore_current_step(session, render_preview=render_preview)
        self._save_session(session)
        return session

    def list_supported_adjustments(self) -> list[AdjustmentSpec]:
        """Return runtime-discoverable adjustment metadata."""

        backend = self.backends[self.default_backend_id]
        supported = set(backend.supported_adjustment_names)
        specs = [
            AdjustmentSpec(name=name, **spec)
            for name, spec in ADJUSTMENT_SPECS.items()
            if name in supported
        ]
        if "crop" in supported:
            specs.append(
                AdjustmentSpec(
                    name="crop",
                    minimum=0.0,
                    maximum=1.0,
                    default=None,
                    unit="normalized_box",
                    description="Normalized crop box with left, top, right, and bottom values.",
                    example={"left": 0.1, "top": 0.1, "right": 0.9, "bottom": 0.9},
                )
            )
        return specs

    def _resolve_source(self, input_path: str) -> Path:
        path = Path(input_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise ValidationError(
                f"Input file '{input_path}' does not exist.",
                hint="Provide an absolute path or a path relative to the server working directory.",
            )
        return path

    def _manifest_path(self, session_id: str) -> Path:
        return self.workspace_root / session_id / "session.json"

    def _write_state(self, session: SessionState) -> None:
        backend = self._backend_for_session(session)
        backend.write_state_file(
            session.source,
            session.adjustments,
            self._state_path(session),
        )

    def _write_state_to_path(
        self,
        session: SessionState,
        adjustments: AdjustmentState,
        state_path: Path,
    ) -> None:
        backend = self._backend_for_session(session)
        backend.write_state_file(
            session.source,
            adjustments,
            state_path,
        )

    def _render_preview(self, session: SessionState) -> None:
        backend = self._backend_for_session(session)
        sequence = len(session.preview_history) + 1
        target_path = Path(session.workspace_dir) / self._preview_filename(sequence)

        rendered_size = backend.render_preview(
            Path(session.source.input_path),
            self._state_path(session),
            target_path,
            max_size=session.preview_max_size,
        )

        session.preview_path = str(target_path)
        session.preview_history.append(
            PreviewArtifact(
                sequence=sequence,
                path=str(target_path),
            )
        )
        session.current_step.preview_path = str(target_path)
        session.current_step.preview_sequence = sequence
        self._sync_diagnostic_artifacts(session, sequence, target_path)

        if rendered_size is not None and (
            session.source.width is None
            or session.source.height is None
            or (session.adjustments.crop is None and session.adjustments.orientation == 0)
        ):
            session.source.width, session.source.height = rendered_size
        session.last_rendered_at = utc_now()

    def _sync_diagnostic_artifacts(
        self,
        session: SessionState,
        sequence: int,
        preview_path: Path,
    ) -> None:
        if not self.advanced_image_info_enabled:
            session.diagnostic_dashboard_path = None
            session.diagnostic_summary = None
            session.current_step.diagnostic_dashboard_path = None
            session.current_step.diagnostic_summary = None
            return

        backend = self._backend_for_session(session)
        try:
            diagnostic_summary = backend.diagnostics_for(preview_path)
        except Exception:
            diagnostic_summary = None
        session.diagnostic_dashboard_path = None
        session.diagnostic_summary = diagnostic_summary
        session.current_step.diagnostic_dashboard_path = None
        session.current_step.diagnostic_summary = (
            diagnostic_summary.model_copy(deep=True) if diagnostic_summary is not None else None
        )

    def _apply_advanced_image_info_gate(self, session: SessionState) -> None:
        """Keep advanced image info stable when the feature is disabled."""

        if not self.advanced_image_info_enabled:
            for step in session.history:
                step.diagnostic_dashboard_path = None
                step.diagnostic_summary = None
            session.diagnostic_dashboard_path = None
            session.diagnostic_summary = None

    def _state_path(self, session: SessionState) -> Path:
        if not session.state_path:
            raise ValidationError(
                f"Session '{session.session_id}' is missing backend state.",
                hint="Recreate the session or repair the session manifest.",
            )
        return Path(session.state_path)

    def _backend_for_session(self, session: SessionState) -> SessionRenderBackend:
        backend = self.backends.get(session.backend)
        if backend is None and session.backend == "rawtherapee-cli":
            backend = self.backends.get(self.default_backend_id)
            if backend is not None:
                session.backend = backend.backend_id
        if backend is None:
            supported = ", ".join(sorted(self.backends))
            raise ValidationError(
                f"Session backend '{session.backend}' is not configured.",
                hint=f"Available backends: {supported}.",
            )
        return backend

    def _preview_filename(self, sequence: int) -> str:
        return f"preview-{sequence:04d}.jpg"

    def _history_state_path(self, session_dir: Path, sequence: int) -> Path:
        suffix = Path(self.backends[self.default_backend_id].state_file_name).suffix
        return session_dir / "history" / f"step-{sequence:04d}{suffix}"

    def _next_step_id(self, sequence: int) -> str:
        return f"{sequence + 1:04d}"

    def _append_history_step(
        self,
        session: SessionState,
        *,
        adjustments: AdjustmentState,
        kind: str,
        render_preview: bool,
    ) -> SessionState:
        session.history = session.history[: session.history_index + 1]
        sequence = len(session.history) + 1
        step = HistoryStep(
            step_id=self._next_step_id(len(session.history)),
            kind=kind,
            adjustments=adjustments,
            state_path=str(self._history_state_path(Path(session.workspace_dir), sequence)),
        )
        session.history.append(step)
        session.history_index = len(session.history) - 1
        self._commit_step_artifacts(session, step, render_preview=render_preview)
        session.touch()
        self._save_session(session)
        return session

    def _commit_step_artifacts(
        self,
        session: SessionState,
        step: HistoryStep,
        *,
        render_preview: bool,
    ) -> None:
        step_state_path = Path(step.state_path) if step.state_path else self._state_path(session)
        self._write_state_to_path(session, step.adjustments, step_state_path)
        session.adjustments = step.adjustments.model_copy(deep=True)
        session.state_path = str(self._state_path(session))
        self._write_state(session)
        if render_preview:
            self._render_preview(session)
        else:
            session.preview_path = step.preview_path or session.preview_path
            session.diagnostic_dashboard_path = step.diagnostic_dashboard_path
            session.diagnostic_summary = step.diagnostic_summary
        session.touch()

    def _restore_current_step(
        self,
        session: SessionState,
        *,
        render_preview: bool,
    ) -> None:
        step = session.current_step
        session.adjustments = step.adjustments.model_copy(deep=True)
        self._write_state(session)
        if render_preview:
            self._render_preview(session)
        else:
            session.preview_path = step.preview_path or session.preview_path
            session.diagnostic_dashboard_path = step.diagnostic_dashboard_path
            session.diagnostic_summary = step.diagnostic_summary
        session.touch()

    def _save_session(self, session: SessionState) -> None:
        self._apply_advanced_image_info_gate(session)
        manifest_path = self._manifest_path(session.session_id)
        manifest_path.write_text(
            session.model_dump_json(indent=2),
            encoding="utf-8",
        )


def _env_flag_enabled(value: str | None) -> bool:
    """Interpret a boolean environment flag with stable defaults."""

    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}
