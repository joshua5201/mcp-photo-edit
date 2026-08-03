"""Local-file EditBackend backed by the in-process RAW edit service."""

from __future__ import annotations

import hashlib
import mimetypes
import uuid
from pathlib import Path

from pydantic import BaseModel
from raw_edit_contracts import (
    AdjustmentState as ContractAdjustmentState,
)
from raw_edit_contracts import (
    CropRect,
    DocumentState,
    GeometryState,
    RenderKind,
    RenderRequest,
    SourceAsset,
)
from raw_edit_service import RawEditService

from .errors import RenderFailedError
from .interfaces import SessionRenderBackend
from .models import AdjustmentState, DiagnosticSummary, SourceImageInfo
from .session import SessionManager


class _StoredRenderState(BaseModel):
    """Workspace-only bridge between session history and typed render commands."""

    source: SourceImageInfo
    adjustments: AdjustmentState


class ServiceRenderBackend:
    """Translate session artifacts to in-process raw-edit-service calls."""

    backend_id: str = "raw-edit-service"
    state_file_name: str = "state.json"

    def __init__(self, service: RawEditService | None = None) -> None:
        self.service = service or RawEditService()
        self.supported_adjustment_names: tuple[str, ...] = tuple(
            self.service.capabilities().supported_adjustments
        )
        self._diagnostics: dict[Path, DiagnosticSummary] = {}

    def write_state_file(
        self,
        source: SourceImageInfo,
        adjustments: AdjustmentState,
        state_path: Path,
    ) -> None:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            _StoredRenderState(source=source, adjustments=adjustments).model_dump_json(indent=2),
            encoding="utf-8",
        )

    def render_preview(
        self,
        source_path: Path,
        state_path: Path,
        target_path: Path,
        *,
        max_size: int | None = None,
    ) -> tuple[int, int] | None:
        return self._render(
            source_path,
            state_path,
            target_path,
            kind=RenderKind.PREVIEW,
            preview_max_size=max_size,
        )

    def render_export(
        self,
        source_path: Path,
        state_path: Path,
        target_path: Path,
    ) -> tuple[int, int] | None:
        return self._render(
            source_path,
            state_path,
            target_path,
            kind=RenderKind.EXPORT,
        )

    def diagnostics_for(self, output_path: Path) -> DiagnosticSummary | None:
        """Return diagnostics emitted for one exact output artifact."""

        return self._diagnostics.get(output_path.resolve())

    def _render(
        self,
        source_path: Path,
        state_path: Path,
        target_path: Path,
        *,
        kind: RenderKind,
        preview_max_size: int | None = None,
    ) -> tuple[int, int] | None:
        stored = _StoredRenderState.model_validate_json(state_path.read_text(encoding="utf-8"))
        document = _document_state(source_path, stored)
        command_id = uuid.uuid4().hex
        response = self.service.execute(
            RenderRequest(
                command_id=command_id,
                revision_id=state_path.stem,
                kind=kind,
                source_path=str(source_path),
                output_path=str(target_path),
                document_state=document,
                preview_max_size=preview_max_size,
            )
        )
        if response.error is not None:
            raise RenderFailedError(
                response.error.message,
                hint=str(response.error.details.get("hint", "")) or None,
            )
        result = response.result
        if result is None:
            raise RenderFailedError("RAW edit service returned no result.")
        if result.diagnostics is not None:
            self._diagnostics[target_path.resolve()] = DiagnosticSummary.model_validate(
                result.diagnostics.summary.model_dump()
            )
        artifact = result.artifact
        if artifact.width is None or artifact.height is None:
            return None
        return artifact.width, artifact.height


class LocalFileBackend(SessionManager):
    """Public local implementation of EditBackend."""

    def __init__(
        self,
        workspace_root: Path | None = None,
        *,
        service: RawEditService | None = None,
    ) -> None:
        super().__init__(
            workspace_root=workspace_root,
            backend=ServiceRenderBackend(service),
        )


def _document_state(source_path: Path, stored: _StoredRenderState) -> DocumentState:
    source_hash = _sha256(source_path)
    adjustments = stored.adjustments
    contract_adjustments = ContractAdjustmentState.model_validate(
        adjustments.model_dump(exclude={"orientation", "crop"})
    )
    crop = (
        CropRect.model_validate(adjustments.crop.model_dump())
        if adjustments.crop is not None
        else None
    )
    return DocumentState(
        document_id=source_hash,
        source=SourceAsset(
            asset_id=source_hash,
            content_hash=source_hash,
            media_type=mimetypes.guess_type(source_path.name)[0] or "application/octet-stream",
            pixel_width=stored.source.width,
            pixel_height=stored.source.height,
        ),
        geometry=GeometryState.model_validate(
            {"orientation": adjustments.orientation, "crop": crop}
        ),
        adjustments=contract_adjustments,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def as_session_backend(backend: ServiceRenderBackend) -> SessionRenderBackend:
    """Expose a static protocol assertion for strict type checking."""

    return backend
