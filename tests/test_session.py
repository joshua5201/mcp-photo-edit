from __future__ import annotations

import json
from pathlib import Path

from mcp_photo_edit.models import AdjustmentPatch, SourceImageInfo
from mcp_photo_edit.session import SessionManager


class DummyBackend:
    backend_id = "dummy-backend"
    state_file_name = "session.state"
    supported_adjustment_names = ("exposure", "contrast", "saturation")

    def __init__(self) -> None:
        self.preview_calls: list[tuple[Path, Path, Path, int | None]] = []
        self.export_calls: list[tuple[Path, Path, Path]] = []
        self.preview_size = (800, 600)

    def write_state_file(self, source: SourceImageInfo, adjustments, state_path: Path) -> None:
        state_path.write_text(f"{source.file_name}:{adjustments.exposure}", encoding="utf-8")

    def render_preview(
        self,
        source_path: Path,
        state_path: Path,
        target_path: Path,
        *,
        max_size: int | None = None,
    ) -> tuple[int, int]:
        self.preview_calls.append((source_path, state_path, target_path, max_size))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"preview")
        return self.preview_size

    def render_export(self, source_path: Path, state_path: Path, target_path: Path) -> tuple[int, int]:
        self.export_calls.append((source_path, state_path, target_path))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"export")
        return (800, 600)


def test_create_session_persists_manifest_state_and_preview(tmp_path: Path) -> None:
    source = tmp_path / "source.ppm"
    source.write_text("P3\n1 1\n255\n255 0 0\n", encoding="utf-8")
    backend = DummyBackend()
    manager = SessionManager(workspace_root=tmp_path / "workspace", backend=backend)

    session = manager.create_session(str(source), preview_max_size=512, session_label="demo")

    session_dir = Path(session.workspace_dir)
    assert session_dir.exists()
    assert Path(session.preview_path).exists()
    assert Path(session.state_path).read_text(encoding="utf-8")
    assert (session_dir / "session.json").exists()
    assert session.backend == "dummy-backend"
    assert session.source.width == 800
    assert session.source.height == 600
    assert backend.preview_calls[0][1] == Path(session.state_path)
    assert backend.preview_calls[0][3] == 512
    assert len(session.preview_history) == 1
    assert session.preview_history[0].sequence == 1
    assert session.preview_history[0].path == session.preview_path


def test_apply_and_reset_adjustments_updates_persisted_state(tmp_path: Path) -> None:
    source = tmp_path / "source.ppm"
    source.write_text("P3\n1 1\n255\n255 0 0\n", encoding="utf-8")
    backend = DummyBackend()
    manager = SessionManager(workspace_root=tmp_path / "workspace", backend=backend)

    session = manager.create_session(str(source))
    updated = manager.apply_adjustments(
        session.session_id,
        AdjustmentPatch(exposure=1.5, saturation=12.0, orientation=90),
        render_preview=True,
    )
    reloaded = manager.get_session(session.session_id)

    assert updated.adjustments.exposure == 1.5
    assert reloaded.adjustments.saturation == 12.0
    assert backend.preview_calls[-1][1] == Path(updated.state_path)
    assert len(updated.preview_history) == 2
    assert updated.preview_history[-1].sequence == 2

    reset = manager.reset_adjustments(
        session.session_id,
        fields=["exposure"],
        render_preview=False,
    )
    assert reset.adjustments.exposure == 0.0
    assert reset.adjustments.saturation == 12.0


def test_crop_preview_does_not_overwrite_canonical_source_dimensions(tmp_path: Path) -> None:
    source = tmp_path / "source.ppm"
    source.write_text("P3\n1 1\n255\n255 0 0\n", encoding="utf-8")
    backend = DummyBackend()
    manager = SessionManager(workspace_root=tmp_path / "workspace", backend=backend)

    session = manager.create_session(str(source))
    assert session.source.width == 800
    assert session.source.height == 600

    backend.preview_size = (400, 300)
    updated = manager.apply_adjustments(
        session.session_id,
        AdjustmentPatch(crop={"left": 0.1, "top": 0.1, "right": 0.9, "bottom": 0.9}),
        render_preview=True,
    )

    assert updated.source.width == 800
    assert updated.source.height == 600


def test_render_preview_appends_history_and_keeps_previous_files(tmp_path: Path) -> None:
    source = tmp_path / "source.ppm"
    source.write_text("P3\n1 1\n255\n255 0 0\n", encoding="utf-8")
    backend = DummyBackend()
    manager = SessionManager(workspace_root=tmp_path / "workspace", backend=backend)

    session = manager.create_session(str(source))
    first_preview = Path(session.preview_path)
    assert first_preview.name == "preview-0001.jpg"

    session = manager.render_preview(session.session_id)
    second_preview = Path(session.preview_path)

    assert second_preview.name == "preview-0002.jpg"
    assert second_preview.exists()
    assert first_preview.exists()
    assert len(session.preview_history) == 2
    assert [artifact.sequence for artifact in session.preview_history] == [1, 2]
    assert [Path(artifact.path).name for artifact in session.preview_history] == [
        "preview-0001.jpg",
        "preview-0002.jpg",
    ]


def test_manifest_backfills_preview_history_on_load(tmp_path: Path) -> None:
    source = tmp_path / "source.ppm"
    source.write_text("P3\n1 1\n255\n255 0 0\n", encoding="utf-8")
    backend = DummyBackend()
    manager = SessionManager(workspace_root=tmp_path / "workspace", backend=backend)

    session = manager.create_session(str(source))
    manifest_path = Path(session.workspace_dir) / "session.json"

    data = json.loads(session.model_dump_json())
    data.pop("preview_history", None)
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    reloaded = manager.get_session(session.session_id)
    assert len(reloaded.preview_history) == 1
    assert reloaded.preview_history[0].sequence == 1
    assert reloaded.preview_history[0].path == reloaded.preview_path
