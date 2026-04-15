from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mcp_photo_edit.models import AdjustmentState, CropAdjustment, RGBMixer, SourceImageInfo
from mcp_photo_edit.render import RawTherapeeBackend


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

    monkeypatch.setattr("mcp_photo_edit.render.shutil.which", fake_which)
    monkeypatch.setattr("mcp_photo_edit.render.subprocess.run", fake_run)

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


def test_rawtherapee_render_preview_fails_when_backend_produces_no_file(
    monkeypatch, tmp_path: Path
) -> None:
    def fake_which(name: str) -> str:
        assert name == "rawtherapee-cli"
        return "/usr/bin/rawtherapee-cli"

    def fake_run(command: list[str], check: bool, capture_output: bool, text: bool):
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("mcp_photo_edit.render.shutil.which", fake_which)
    monkeypatch.setattr("mcp_photo_edit.render.subprocess.run", fake_run)

    source = tmp_path / "source.nef"
    profile = tmp_path / "session.pp3"
    target = tmp_path / "preview.jpg"
    source.write_text("raw", encoding="utf-8")
    profile.write_text("[Exposure]\nCompensation=0\n", encoding="utf-8")

    backend = RawTherapeeBackend()

    with pytest.raises(Exception, match="without producing"):
        backend.render_preview(source, profile, target, max_size=None)


def test_rawtherapee_render_export_fails_when_backend_produces_no_file(
    monkeypatch, tmp_path: Path
) -> None:
    def fake_which(name: str) -> str:
        assert name == "rawtherapee-cli"
        return "/usr/bin/rawtherapee-cli"

    def fake_run(command: list[str], check: bool, capture_output: bool, text: bool):
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("mcp_photo_edit.render.shutil.which", fake_which)
    monkeypatch.setattr("mcp_photo_edit.render.subprocess.run", fake_run)

    source = tmp_path / "source.nef"
    profile = tmp_path / "session.pp3"
    target = tmp_path / "export.jpg"
    source.write_text("raw", encoding="utf-8")
    profile.write_text("[Exposure]\nCompensation=0\n", encoding="utf-8")

    backend = RawTherapeeBackend()

    with pytest.raises(Exception, match="without producing"):
        backend.render_export(source, profile, target)


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


def test_rawtherapee_write_state_file_includes_new_adjustment_blocks(tmp_path: Path) -> None:
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
            rgb_mixer=RGBMixer(
                red=(100.0, 0.0, 0.0),
                green=(0.0, 95.0, 5.0),
                blue=(0.0, 0.0, 100.0),
            ),
            denoise_luma=8.0,
            denoise_detail=12.0,
            denoise_chroma=16.0,
            color_temperature=5100.0,
            green_balance=0.98,
            highlights=14.0,
            shadows=20.0,
            sharpen_amount=160.0,
            sharpen_radius=0.9,
            sharpen_contrast=26.0,
        ),
        profile,
    )

    pp3 = profile.read_text(encoding="utf-8")
    assert "[Channel Mixer]" in pp3
    assert "[Directional Pyramid Denoising]" in pp3
    assert "[White Balance]" in pp3
    assert "[Shadows & Highlights]" in pp3
    assert "[Sharpening]" in pp3
