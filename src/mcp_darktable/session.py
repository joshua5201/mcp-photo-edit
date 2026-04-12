"""Session lifecycle and persistence."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from .errors import SessionNotFoundError, ValidationError
from .models import (
    ADJUSTMENT_SPECS,
    RESETTABLE_FIELDS,
    AdjustmentPatch,
    AdjustmentSpec,
    SessionState,
    SourceImageInfo,
    utc_now,
)
from .render import DarktableCliRenderer
from .xmp import build_sidecar


class SessionManager:
    """Manage edit sessions and their workspace artifacts."""

    def __init__(
        self,
        workspace_root: Path | None = None,
        renderer: DarktableCliRenderer | None = None,
    ) -> None:
        default_root = Path(os.environ.get("MCP_DARKTABLE_WORKDIR", ".mcp-darktable"))
        self.workspace_root = (workspace_root or default_root).resolve()
        self.renderer = renderer or DarktableCliRenderer()
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

        session = SessionState(
            session_id=session_id,
            session_label=session_label,
            source=SourceImageInfo.from_path(source_path),
            workspace_dir=str(session_dir),
            xmp_path=str(session_dir / "session.xmp"),
            preview_path=str(session_dir / "preview.jpg"),
            preview_max_size=preview_max_size,
        )
        self._write_sidecar(session)
        self._render_preview(session)
        self._save_session(session)
        return session

    def get_session(self, session_id: str) -> SessionState:
        """Load a persisted session."""

        manifest_path = self._manifest_path(session_id)
        if not manifest_path.exists():
            raise SessionNotFoundError(session_id)
        return SessionState.model_validate_json(manifest_path.read_text(encoding="utf-8"))

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
            session.adjustments = session.adjustments.apply_patch(patch)
        except PydanticValidationError as exc:
            raise ValidationError(str(exc)) from exc
        session.touch()
        self._write_sidecar(session)
        if render_preview:
            self._render_preview(session)
        self._save_session(session)
        return session

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
        session.adjustments = session.adjustments.reset_fields(fields)
        session.touch()
        self._write_sidecar(session)
        if render_preview:
            self._render_preview(session)
        self._save_session(session)
        return session

    def export_image(self, session_id: str, output_path: str) -> Path:
        """Render the current session state to a final output path."""

        session = self.get_session(session_id)
        output = Path(output_path).expanduser().resolve()
        xmp_path = Path(session.xmp_path) if session.adjustments != session.adjustments.__class__() else None
        self.renderer.render(Path(session.source.input_path), xmp_path, output)
        session.touch()
        session.last_rendered_at = utc_now()
        self._save_session(session)
        return output

    def list_supported_adjustments(self) -> list[AdjustmentSpec]:
        """Return runtime-discoverable adjustment metadata."""

        specs = [
            AdjustmentSpec(name=name, **spec)
            for name, spec in ADJUSTMENT_SPECS.items()
        ]
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

    def _write_sidecar(self, session: SessionState) -> None:
        sidecar_path = Path(session.xmp_path)
        sidecar_path.write_text(
            build_sidecar(session.source.file_name, session.adjustments),
            encoding="utf-8",
        )

    def _render_preview(self, session: SessionState) -> None:
        xmp_path = Path(session.xmp_path) if session.adjustments != session.adjustments.__class__() else None
        self.renderer.render(
            Path(session.source.input_path),
            xmp_path,
            Path(session.preview_path),
            max_size=session.preview_max_size,
        )
        session.last_rendered_at = utc_now()

    def _save_session(self, session: SessionState) -> None:
        manifest_path = self._manifest_path(session.session_id)
        manifest_path.write_text(
            session.model_dump_json(indent=2),
            encoding="utf-8",
        )
