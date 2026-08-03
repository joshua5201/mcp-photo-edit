"""Integration tests for EditBackend to in-process service wiring."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from raw_edit_service.models import AdjustmentState, SourceImageInfo
from raw_edit_service.service import RawEditService

from mcp_photo_edit.backend import LocalFileBackend


class FakeRenderer:
    """Small renderer exercising the real service and LocalFileBackend layers."""

    backend_id: str = "fake-renderer"
    state_file_name: str = "state.txt"
    supported_adjustment_names: tuple[str, ...] = ("exposure", "orientation", "crop")

    def ensure_available(self) -> None:
        return None

    def write_state_file(
        self,
        source: SourceImageInfo,
        adjustments: AdjustmentState,
        state_path: Path,
    ) -> None:
        state_path.write_text(f"{source.file_name}:{adjustments.exposure}", encoding="utf-8")

    def render_preview(
        self,
        source_path: Path,
        state_path: Path,
        target_path: Path,
        *,
        max_size: int | None = None,
    ) -> tuple[int, int] | None:
        del source_path, state_path, max_size
        Image.new("RGB", (640, 480), "#334155").save(target_path)
        return (640, 480)

    def render_export(
        self,
        source_path: Path,
        state_path: Path,
        target_path: Path,
    ) -> tuple[int, int] | None:
        del source_path, state_path
        Image.new("RGB", (1600, 1200), "#334155").save(target_path)
        return (1600, 1200)


def test_local_file_backend_calls_raw_edit_service_in_process(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (640, 480), "#0f172a").save(source)
    service = RawEditService(FakeRenderer(), diagnostics_enabled=False)
    backend = LocalFileBackend(tmp_path / "workspace", service=service)

    session = backend.create_session(str(source))
    output = backend.export_image(session.session_id, str(tmp_path / "export.jpg"))

    assert session.backend == "raw-edit-service"
    assert session.state_path is not None
    assert Path(session.state_path).name == "state.json"
    assert output.exists()
    with Image.open(output) as exported:
        assert exported.size == (1600, 1200)
