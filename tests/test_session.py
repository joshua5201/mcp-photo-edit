from __future__ import annotations

from pathlib import Path

from mcp_darktable.models import AdjustmentPatch
from mcp_darktable.session import SessionManager


class DummyBackend:
    backend_id = "dummy-backend"
    state_file_name = "session.state"
    supported_adjustment_names = ("exposure", "contrast", "saturation")

    def __init__(self) -> None:
        self.preview_calls: list[tuple[Path, Path, Path, int | None]] = []
        self.export_calls: list[tuple[Path, Path, Path]] = []

    def write_state_file(self, source_file_name: str, adjustments, state_path: Path) -> None:
        state_path.write_text(f"{source_file_name}:{adjustments.exposure}", encoding="utf-8")

    def render_preview(
        self,
        source_path: Path,
        state_path: Path,
        target_path: Path,
        *,
        max_size: int | None = None,
    ) -> None:
        self.preview_calls.append((source_path, state_path, target_path, max_size))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"preview")

    def render_export(self, source_path: Path, state_path: Path, target_path: Path) -> None:
        self.export_calls.append((source_path, state_path, target_path))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"export")


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
    assert backend.preview_calls[0][1] == Path(session.state_path)
    assert backend.preview_calls[0][3] == 512


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

    reset = manager.reset_adjustments(
        session.session_id,
        fields=["exposure"],
        render_preview=False,
    )
    assert reset.adjustments.exposure == 0.0
    assert reset.adjustments.saturation == 12.0
