from __future__ import annotations

import subprocess
from pathlib import Path

from mcp_darktable.models import AdjustmentState, CropAdjustment, SourceImageInfo
from mcp_darktable.render import DarktableBackend, RawTherapeeBackend


def test_darktable_render_invokes_cli_and_moves_output(monkeypatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_which(name: str) -> str:
        assert name == "darktable-cli"
        return "/usr/bin/darktable-cli"

    def fake_run(command: list[str], check: bool, capture_output: bool, text: bool):
        commands.append(command)
        output_dir = Path(command[3])
        (output_dir / "rendered.jpg").write_bytes(b"jpg")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("mcp_darktable.render.shutil.which", fake_which)
    monkeypatch.setattr("mcp_darktable.render.subprocess.run", fake_run)

    source = tmp_path / "source.ppm"
    sidecar = tmp_path / "session.xmp"
    target = tmp_path / "preview.jpg"
    source.write_text("P3\n1 1\n255\n255 0 0\n", encoding="utf-8")
    sidecar.write_text("<xmp />", encoding="utf-8")

    backend = DarktableBackend()
    backend.render_preview(source, sidecar, target, max_size=256)

    assert target.read_bytes() == b"jpg"
    assert commands[0][0] == "darktable-cli"
    assert str(sidecar) in commands[0]
    assert "--width" in commands[0]
    assert "256" in commands[0]


def test_rawtherapee_render_invokes_cli_with_pp3(monkeypatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_which(name: str) -> str:
        assert name == "rawtherapee-cli"
        return "/usr/bin/rawtherapee-cli"

    def fake_run(command: list[str], check: bool, capture_output: bool, text: bool):
        commands.append(command)
        output_path = Path(command[2])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"jpg")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("mcp_darktable.render.shutil.which", fake_which)
    monkeypatch.setattr("mcp_darktable.render.subprocess.run", fake_run)

    source = tmp_path / "source.nef"
    profile = tmp_path / "session.pp3"
    target = tmp_path / "preview.jpg"
    source.write_text("raw", encoding="utf-8")
    profile.write_text("[Exposure]\nCompensation=0\n", encoding="utf-8")

    backend = RawTherapeeBackend()
    backend.render_preview(source, profile, target, max_size=None)

    assert target.read_bytes() == b"jpg"
    assert commands[0][0] == "rawtherapee-cli"
    assert "-p" in commands[0]
    assert str(profile) in commands[0]
    assert any(part.startswith("-j") for part in commands[0])


def test_rawtherapee_rejects_unsupported_geometry_adjustments(tmp_path: Path) -> None:
    backend = RawTherapeeBackend()
    profile = tmp_path / "session.pp3"
    source = SourceImageInfo(
        input_path=str(tmp_path / "source.nef"),
        file_name="source.nef",
        suffix=".nef",
        width=None,
        height=None,
    )

    try:
        backend.write_state_file(
            source,
            AdjustmentState(
                crop=CropAdjustment(left=0.1, top=0.1, right=0.9, bottom=0.9),
            ),
            profile,
        )
    except Exception as exc:  # noqa: BLE001
        assert "Create a session preview first" in str(exc) or "Create a session preview first" in (getattr(exc, "hint", "") or "")
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected crop without dimensions to be rejected for RawTherapee")


def test_rawtherapee_write_state_file_includes_rotation_and_crop(tmp_path: Path) -> None:
    backend = RawTherapeeBackend()
    profile = tmp_path / "session.pp3"
    source = SourceImageInfo(
        input_path=str(tmp_path / "source.nef"),
        file_name="source.nef",
        suffix=".nef",
        width=4032,
        height=6056,
    )

    backend.write_state_file(
        source,
        AdjustmentState(
            exposure=1.0,
            contrast=10.0,
            saturation=5.0,
            orientation=90,
            crop=CropAdjustment(left=0.25, top=0.25, right=0.75, bottom=0.75),
        ),
        profile,
    )

    pp3 = profile.read_text(encoding="utf-8")
    assert "[Coarse Transformation]" in pp3
    assert "Rotate=90" in pp3
    assert "[Crop]" in pp3
    assert "X=1514" in pp3
    assert "Y=1008" in pp3
    assert "W=3028" in pp3
    assert "H=2016" in pp3
