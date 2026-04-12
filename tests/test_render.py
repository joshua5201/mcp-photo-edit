from __future__ import annotations

import subprocess
from pathlib import Path

from mcp_darktable.render import DarktableCliRenderer


def test_render_invokes_darktable_cli_and_moves_output(
    monkeypatch,
    tmp_path: Path,
) -> None:
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

    renderer = DarktableCliRenderer()
    renderer.render(source, sidecar, target, max_size=256)

    assert target.read_bytes() == b"jpg"
    assert commands
    assert commands[0][0] == "darktable-cli"
    assert str(sidecar) in commands[0]
    assert "--width" in commands[0]
    assert "256" in commands[0]


def test_render_without_sidecar_omits_xmp_argument(monkeypatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_which(name: str) -> str:
        return "/usr/bin/darktable-cli"

    def fake_run(command: list[str], check: bool, capture_output: bool, text: bool):
        commands.append(command)
        output_dir = Path(command[2])
        (output_dir / "rendered.jpg").write_bytes(b"jpg")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("mcp_darktable.render.shutil.which", fake_which)
    monkeypatch.setattr("mcp_darktable.render.subprocess.run", fake_run)

    source = tmp_path / "source.ppm"
    target = tmp_path / "preview.jpg"
    source.write_text("P3\n1 1\n255\n255 0 0\n", encoding="utf-8")

    renderer = DarktableCliRenderer()
    renderer.render(source, None, target, max_size=256)

    assert commands
    assert commands[0][1] == str(source)
    assert commands[0][2].startswith(str(tmp_path))
