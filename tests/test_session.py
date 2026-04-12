from __future__ import annotations

from pathlib import Path

from mcp_darktable.models import AdjustmentPatch
from mcp_darktable.session import SessionManager


class DummyRenderer:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, Path | None, Path, int | None]] = []

    def render(
        self,
        source_path: Path,
        xmp_path: Path | None,
        target_path: Path,
        *,
        max_size: int | None = None,
    ) -> None:
        self.calls.append((source_path, xmp_path, target_path, max_size))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"preview")


def test_create_session_persists_manifest_sidecar_and_preview(tmp_path: Path) -> None:
    source = tmp_path / "source.ppm"
    source.write_text("P3\n1 1\n255\n255 0 0\n", encoding="utf-8")
    renderer = DummyRenderer()
    manager = SessionManager(workspace_root=tmp_path / "workspace", renderer=renderer)

    session = manager.create_session(str(source), preview_max_size=512, session_label="demo")

    session_dir = Path(session.workspace_dir)
    assert session_dir.exists()
    assert Path(session.preview_path).exists()
    assert Path(session.xmp_path).read_text(encoding="utf-8")
    assert (session_dir / "session.json").exists()
    assert renderer.calls[0][1] is None
    assert renderer.calls[0][3] == 512


def test_apply_and_reset_adjustments_updates_persisted_state(tmp_path: Path) -> None:
    source = tmp_path / "source.ppm"
    source.write_text("P3\n1 1\n255\n255 0 0\n", encoding="utf-8")
    renderer = DummyRenderer()
    manager = SessionManager(workspace_root=tmp_path / "workspace", renderer=renderer)

    session = manager.create_session(str(source))
    updated = manager.apply_adjustments(
        session.session_id,
        AdjustmentPatch(exposure=1.5, saturation=12.0, orientation=90),
        render_preview=True,
    )
    reloaded = manager.get_session(session.session_id)

    assert updated.adjustments.exposure == 1.5
    assert reloaded.adjustments.saturation == 12.0
    assert renderer.calls[-1][1] == Path(updated.xmp_path)

    reset = manager.reset_adjustments(
        session.session_id,
        fields=["exposure"],
        render_preview=False,
    )
    assert reset.adjustments.exposure == 0.0
    assert reset.adjustments.saturation == 12.0
