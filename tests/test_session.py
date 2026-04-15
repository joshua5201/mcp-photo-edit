from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from mcp_photo_edit.errors import ValidationError
from mcp_photo_edit.models import AdjustmentPatch, SourceImageInfo
from mcp_photo_edit.session import SessionManager


class DummyBackend:
    backend_id = "dummy-backend"
    state_file_name = "session.state"
    supported_adjustment_names = ("exposure", "contrast", "saturation", "orientation", "crop")

    def __init__(self) -> None:
        self.preview_calls: list[tuple[Path, Path, Path, int | None]] = []
        self.export_calls: list[tuple[Path, Path, Path]] = []
        self.preview_size = (800, 600)

    def write_state_file(self, source: SourceImageInfo, adjustments, state_path: Path) -> None:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            f"{source.file_name}:{json.dumps(adjustments.model_dump(), sort_keys=True)}",
            encoding="utf-8",
        )

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
        self._write_test_image(target_path, self.preview_size)
        return self.preview_size

    def render_export(self, source_path: Path, state_path: Path, target_path: Path) -> tuple[int, int]:
        self.export_calls.append((source_path, state_path, target_path))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_test_image(target_path, (800, 600))
        return (800, 600)

    def _write_test_image(self, target_path: Path, size: tuple[int, int]) -> None:
        image = Image.new("RGB", size, "#0f172a")
        draw = ImageDraw.Draw(image)
        width, height = size
        draw.rectangle((0, 0, width // 2, height // 2), fill="#d14a4a")
        draw.rectangle((width // 2, 0, width, height // 2), fill="#4b7bd1")
        draw.rectangle((0, height // 2, width // 2, height), fill="#47a35d")
        draw.rectangle((width // 2, height // 2, width, height), fill="#f1c84c")
        image.save(target_path, quality=90)


def test_create_session_persists_initial_history_state_and_preview(tmp_path: Path) -> None:
    source = tmp_path / "source.ppm"
    source.write_text("P3\n1 1\n255\n255 0 0\n", encoding="utf-8")
    backend = DummyBackend()
    manager = SessionManager(workspace_root=tmp_path / "workspace", backend=backend)

    session = manager.create_session(str(source), preview_max_size=512, session_label="demo")

    session_dir = Path(session.workspace_dir)
    current_state = Path(session.state_path)
    history_state = session_dir / "history" / "step-0001.pp3"

    assert session_dir.exists()
    assert Path(session.preview_path).exists()
    assert current_state.read_text(encoding="utf-8")
    assert history_state.read_text(encoding="utf-8") == current_state.read_text(encoding="utf-8")
    assert (session_dir / "session.json").exists()
    assert session.backend == "dummy-backend"
    assert session.source.width == 800
    assert session.source.height == 600
    assert backend.preview_calls[0][1] == current_state
    assert backend.preview_calls[0][3] == 512
    assert session.diagnostic_dashboard_path is not None
    assert session.diagnostic_dashboard_path != session.preview_path
    assert Path(session.diagnostic_dashboard_path).exists()
    assert session.diagnostic_summary is not None
    assert session.diagnostic_summary.analysis_source == "current_rendered_state"
    assert session.diagnostic_summary.dimensions.width == 800
    assert session.diagnostic_summary.dimensions.height == 600
    assert session.history[0].diagnostic_dashboard_path == session.diagnostic_dashboard_path
    assert session.history[0].diagnostic_summary == session.diagnostic_summary
    assert len(session.preview_history) == 1
    assert len(session.history) == 1
    assert session.history_index == 0
    assert session.history_length == 1
    assert session.can_undo is False
    assert session.can_redo is False
    assert session.history[0].kind == "init"
    assert session.history[0].preview_path == session.preview_path
    assert session.history[0].preview_sequence == 1
    assert Path(session.history[0].state_path).name == "step-0001.pp3"


def test_apply_and_reset_adjustments_append_semantic_history(tmp_path: Path) -> None:
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
    assert len(updated.history) == 2
    assert updated.history_index == 1
    assert updated.can_undo is True
    assert updated.can_redo is False
    assert updated.history[-1].kind == "apply_adjustments"
    assert updated.history[-1].preview_sequence == 2
    assert updated.diagnostic_dashboard_path is not None
    assert updated.history[-1].diagnostic_dashboard_path == updated.diagnostic_dashboard_path
    assert updated.history[-1].diagnostic_summary == updated.diagnostic_summary
    assert reloaded.diagnostic_summary is not None

    reset = manager.reset_adjustments(
        session.session_id,
        fields=["exposure"],
        render_preview=False,
    )
    assert reset.adjustments.exposure == 0.0
    assert reset.adjustments.saturation == 12.0
    assert len(reset.history) == 3
    assert reset.history_index == 2
    assert reset.history[-1].kind == "reset_adjustments"
    assert reset.history[-1].preview_path is None
    assert reset.diagnostic_dashboard_path is None
    assert reset.diagnostic_summary is None
    assert reset.preview_path == updated.preview_path


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


def test_render_preview_appends_preview_history_without_semantic_history(tmp_path: Path) -> None:
    source = tmp_path / "source.ppm"
    source.write_text("P3\n1 1\n255\n255 0 0\n", encoding="utf-8")
    backend = DummyBackend()
    manager = SessionManager(workspace_root=tmp_path / "workspace", backend=backend)

    session = manager.create_session(str(source))
    first_preview = Path(session.preview_path)
    assert first_preview.name == "preview-0001.jpg"
    assert len(session.history) == 1

    session = manager.render_preview(session.session_id)
    second_preview = Path(session.preview_path)

    assert second_preview.name == "preview-0002.jpg"
    assert second_preview.exists()
    assert first_preview.exists()
    assert len(session.preview_history) == 2
    assert len(session.history) == 1
    assert session.history_index == 0
    assert [artifact.sequence for artifact in session.preview_history] == [1, 2]
    assert session.history[0].preview_sequence == 2
    assert session.history[0].preview_path == str(second_preview)
    assert session.diagnostic_dashboard_path is not None
    assert Path(session.diagnostic_dashboard_path).name == "dashboard-0002.png"
    assert Path(session.diagnostic_dashboard_path).exists()
    assert session.diagnostic_dashboard_path != session.preview_path
    assert session.history[0].diagnostic_dashboard_path == session.diagnostic_dashboard_path


def test_disabled_advanced_image_info_keeps_preview_flow_and_null_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.ppm"
    source.write_text("P3\n1 1\n255\n255 0 0\n", encoding="utf-8")
    backend = DummyBackend()
    monkeypatch.setenv("DISABLE_ADVANCED_IMAGE_INFO", "true")
    manager = SessionManager(workspace_root=tmp_path / "workspace", backend=backend)

    assert manager.advanced_image_info_enabled is False

    session = manager.create_session(str(source))
    first_preview = Path(session.preview_path)
    assert first_preview.exists()
    assert session.diagnostic_dashboard_path is None
    assert session.diagnostic_summary is None

    session = manager.render_preview(session.session_id)
    second_preview = Path(session.preview_path)

    assert second_preview.name == "preview-0002.jpg"
    assert second_preview.exists()
    assert len(session.preview_history) == 2
    assert session.diagnostic_dashboard_path is None
    assert session.diagnostic_summary is None
    assert session.history[0].diagnostic_dashboard_path is None
    assert session.history[0].diagnostic_summary is None


def test_advanced_image_info_fail_open_preserves_preview(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.ppm"
    source.write_text("P3\n1 1\n255\n255 0 0\n", encoding="utf-8")
    backend = DummyBackend()
    manager = SessionManager(workspace_root=tmp_path / "workspace", backend=backend)

    def fail_render(*args, **kwargs):  # noqa: ANN001, ANN002
        raise RuntimeError("diagnostics failed")

    monkeypatch.setattr(manager._advanced_image_info_renderer, "render", fail_render)

    session = manager.create_session(str(source))

    assert Path(session.preview_path).exists()
    assert session.diagnostic_dashboard_path is None
    assert session.diagnostic_summary is None
    assert session.history[0].diagnostic_dashboard_path is None
    assert session.history[0].diagnostic_summary is None


def test_undo_and_redo_move_cursor_without_creating_new_steps(tmp_path: Path) -> None:
    source = tmp_path / "source.ppm"
    source.write_text("P3\n1 1\n255\n255 0 0\n", encoding="utf-8")
    backend = DummyBackend()
    manager = SessionManager(workspace_root=tmp_path / "workspace", backend=backend)

    session = manager.create_session(str(source))
    session = manager.apply_adjustments(session.session_id, AdjustmentPatch(exposure=1.0), render_preview=True)
    session = manager.apply_adjustments(session.session_id, AdjustmentPatch(contrast=20.0), render_preview=True)

    preview_count = len(session.preview_history)
    undone = manager.undo_adjustment(session.session_id)
    assert undone.history_index == 1
    assert undone.adjustments.exposure == 1.0
    assert undone.adjustments.contrast == 0.0
    assert len(undone.history) == 3
    assert len(undone.preview_history) == preview_count
    assert undone.preview_path == undone.history[1].preview_path
    assert undone.diagnostic_dashboard_path == undone.history[1].diagnostic_dashboard_path
    assert undone.diagnostic_summary == undone.history[1].diagnostic_summary
    assert undone.can_undo is True
    assert undone.can_redo is True

    redone = manager.redo_adjustment(session.session_id)
    assert redone.history_index == 2
    assert redone.adjustments.exposure == 1.0
    assert redone.adjustments.contrast == 20.0
    assert len(redone.history) == 3
    assert len(redone.preview_history) == preview_count
    assert redone.preview_path == redone.history[2].preview_path
    assert redone.diagnostic_dashboard_path == redone.history[2].diagnostic_dashboard_path
    assert redone.diagnostic_summary == redone.history[2].diagnostic_summary


def test_apply_after_undo_truncates_redo_tail(tmp_path: Path) -> None:
    source = tmp_path / "source.ppm"
    source.write_text("P3\n1 1\n255\n255 0 0\n", encoding="utf-8")
    backend = DummyBackend()
    manager = SessionManager(workspace_root=tmp_path / "workspace", backend=backend)

    session = manager.create_session(str(source))
    session = manager.apply_adjustments(session.session_id, AdjustmentPatch(exposure=1.0), render_preview=True)
    session = manager.apply_adjustments(session.session_id, AdjustmentPatch(contrast=20.0), render_preview=True)

    undone = manager.undo_adjustment(session.session_id)
    branched = manager.apply_adjustments(
        undone.session_id,
        AdjustmentPatch(saturation=15.0),
        render_preview=False,
    )

    assert len(branched.history) == 3
    assert branched.history_index == 2
    assert branched.adjustments.exposure == 1.0
    assert branched.adjustments.contrast == 0.0
    assert branched.adjustments.saturation == 15.0
    assert branched.can_redo is False


def test_list_supported_adjustments_includes_new_rawtherapee_controls(tmp_path: Path) -> None:
    backend = DummyBackend()
    backend.supported_adjustment_names = (
        "exposure",
        "contrast",
        "saturation",
        "rgb_mixer",
        "denoise_luma",
        "denoise_detail",
        "denoise_chroma",
        "color_temperature",
        "green_balance",
        "highlights",
        "shadows",
        "sharpen_amount",
        "sharpen_radius",
        "sharpen_contrast",
        "orientation",
        "crop",
    )
    manager = SessionManager(workspace_root=tmp_path / "workspace", backend=backend)

    supported = {spec.name: spec for spec in manager.list_supported_adjustments()}

    assert "rgb_mixer" in supported
    assert supported["rgb_mixer"].unit == "percent_triplets"
    assert supported["rgb_mixer"].minimum is None
    assert supported["rgb_mixer"].maximum is None
    assert supported["rgb_mixer"].example["green"] == [0.0, 95.0, 5.0]
    assert supported["denoise_luma"].maximum == 100.0
    assert supported["denoise_detail"].maximum == 100.0
    assert supported["denoise_chroma"].maximum == 100.0
    assert supported["color_temperature"].minimum == 1500.0
    assert supported["green_balance"].default is None
    assert supported["highlights"].maximum == 100.0
    assert supported["shadows"].maximum == 100.0
    assert supported["sharpen_amount"].maximum == 1000.0
    assert supported["sharpen_radius"].default == 0.5
    assert supported["sharpen_contrast"].default == 20.0


def test_get_session_migrates_legacy_xmp_path_to_state_path(tmp_path: Path) -> None:
    session_dir = tmp_path / "workspace" / "legacy123"
    session_dir.mkdir(parents=True)
    manifest_path = session_dir / "session.json"

    manifest_path.write_text(
        """
{
  "session_id": "legacy123",
  "source": {
    "input_path": "/tmp/source.nef",
    "file_name": "source.nef",
    "suffix": ".nef",
    "width": 4000,
    "height": 3000
  },
  "workspace_dir": "/tmp/workspace/legacy123",
  "state_path": null,
  "xmp_path": "/tmp/workspace/legacy123/session.pp3",
  "preview_path": "/tmp/workspace/legacy123/preview-0001.jpg",
  "adjustments": {
    "exposure": 0.0,
    "contrast": 0.0,
    "saturation": 0.0,
    "rgb_mixer": null,
    "denoise_luma": 0.0,
    "denoise_detail": 0.0,
    "denoise_chroma": 0.0,
    "color_temperature": null,
    "green_balance": null,
    "highlights": 0.0,
    "shadows": 0.0,
    "orientation": 0,
    "crop": null
  },
  "history": [
    {
      "step_id": "step-0001",
      "kind": "init",
      "adjustments": {
        "exposure": 0.0,
        "contrast": 0.0,
        "saturation": 0.0,
        "rgb_mixer": null,
        "denoise_luma": 0.0,
        "denoise_detail": 0.0,
        "denoise_chroma": 0.0,
        "color_temperature": null,
        "green_balance": null,
        "highlights": 0.0,
        "shadows": 0.0,
        "orientation": 0,
        "crop": null
      },
      "state_path": "/tmp/workspace/legacy123/history/step-0001.pp3"
    }
  ],
  "history_index": 0,
  "backend": "rawtherapee-cli"
}
""".strip(),
        encoding="utf-8",
    )

    manager = SessionManager(workspace_root=tmp_path / "workspace", backend=DummyBackend())
    session = manager.get_session("legacy123")

    assert session.state_path == "/tmp/workspace/legacy123/session.pp3"


def test_export_uses_cursor_selected_state(tmp_path: Path) -> None:
    source = tmp_path / "source.ppm"
    source.write_text("P3\n1 1\n255\n255 0 0\n", encoding="utf-8")
    backend = DummyBackend()
    manager = SessionManager(workspace_root=tmp_path / "workspace", backend=backend)

    session = manager.create_session(str(source))
    session = manager.apply_adjustments(session.session_id, AdjustmentPatch(exposure=1.0), render_preview=False)
    session = manager.apply_adjustments(session.session_id, AdjustmentPatch(contrast=20.0), render_preview=False)
    session = manager.undo_adjustment(session.session_id)

    output = tmp_path / "output.jpg"
    manager.export_image(session.session_id, str(output))

    assert output.exists()
    assert backend.export_calls[-1][1] == Path(session.state_path)
    assert '"contrast": 0.0' in Path(session.state_path).read_text(encoding="utf-8")


def test_undo_and_redo_validate_bounds(tmp_path: Path) -> None:
    source = tmp_path / "source.ppm"
    source.write_text("P3\n1 1\n255\n255 0 0\n", encoding="utf-8")
    backend = DummyBackend()
    manager = SessionManager(workspace_root=tmp_path / "workspace", backend=backend)

    session = manager.create_session(str(source))
    with pytest.raises(ValidationError):
        manager.undo_adjustment(session.session_id)

    session = manager.apply_adjustments(session.session_id, AdjustmentPatch(exposure=1.0), render_preview=False)
    with pytest.raises(ValidationError):
        manager.redo_adjustment(session.session_id)
