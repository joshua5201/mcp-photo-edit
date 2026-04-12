"""Backend integrations for RawTherapee and darktable."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from .errors import BackendUnavailableError, RenderFailedError, ValidationError
from .models import AdjustmentState, RenderMode, SourceImageInfo
from .pp3 import build_pp3
from .xmp import build_sidecar

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional at import time, required at runtime for resizing
    Image = None


class RenderBackend(Protocol):
    """Backend contract used by the session layer."""

    backend_id: str
    state_file_name: str
    supported_adjustment_names: tuple[str, ...]

    def ensure_available(self) -> None:
        """Ensure the backend executable is installed."""

    def write_state_file(
        self,
        source: SourceImageInfo,
        adjustments: AdjustmentState,
        state_path: Path,
    ) -> None:
        """Persist backend-native session state."""

    def render_preview(
        self,
        source_path: Path,
        state_path: Path | None,
        target_path: Path,
        *,
        max_size: int | None = None,
        mode: RenderMode = RenderMode.CURRENT,
    ) -> tuple[int, int] | None:
        """Render a preview image."""

    def render_export(
        self,
        source_path: Path,
        state_path: Path,
        target_path: Path,
    ) -> tuple[int, int] | None:
        """Render a final export."""


class DarktableBackend:
    """Render previews and exports through darktable-cli."""

    backend_id = "darktable-cli"
    state_file_name = "session.xmp"
    supported_adjustment_names = (
        "exposure",
        "contrast",
        "saturation",
        "orientation",
        "crop",
    )

    def __init__(self, executable: str = "darktable-cli") -> None:
        self.executable = executable

    def ensure_available(self) -> None:
        if shutil.which(self.executable) is None:
            raise BackendUnavailableError(self.executable)

    def write_state_file(
        self,
        source: SourceImageInfo,
        adjustments: AdjustmentState,
        state_path: Path,
    ) -> None:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            build_sidecar(source.file_name, adjustments),
            encoding="utf-8",
        )

    def render_preview(
        self,
        source_path: Path,
        state_path: Path | None,
        target_path: Path,
        *,
        max_size: int | None = None,
        mode: RenderMode = RenderMode.CURRENT,
    ) -> tuple[int, int] | None:
        # Darktable support is deprecated; only CURRENT mode is supported.
        # We ignore other modes to minimize legacy code maintenance.
        return self._render(source_path, state_path, target_path, max_size=max_size)

    def render_export(
        self,
        source_path: Path,
        state_path: Path,
        target_path: Path,
    ) -> tuple[int, int] | None:
        return self._render(source_path, state_path, target_path)

    def _render(
        self,
        source_path: Path,
        state_path: Path | None,
        target_path: Path,
        *,
        max_size: int | None = None,
    ) -> tuple[int, int] | None:
        self.ensure_available()
        target_path = target_path.resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="darktable-render-", dir=target_path.parent) as temp_dir:
            temp_output_dir = Path(temp_dir)
            out_ext = target_path.suffix.lstrip(".") or "jpg"

            command = [
                self.executable,
                str(source_path),
            ]
            if state_path is not None:
                command.append(str(state_path))

            command.extend(
                [
                    str(temp_output_dir),
                    "--out-ext",
                    out_ext,
                ]
            )
            if max_size is not None:
                command.extend(["--width", str(max_size), "--height", str(max_size)])

            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                raise RenderFailedError(
                    f"{self.executable} exited with status {completed.returncode}.",
                    hint=_render_details(completed.stdout, completed.stderr),
                )

            rendered_files = sorted(path for path in temp_output_dir.iterdir() if path.is_file())
            if not rendered_files:
                raise RenderFailedError(
                    f"{self.executable} completed without producing an output file.",
                    hint="Check whether the input file format is supported by the local darktable build.",
                )

            rendered_files[-1].replace(target_path)
            return _image_dimensions(target_path)


class RawTherapeeBackend:
    """Render previews and exports through rawtherapee-cli."""

    backend_id = "rawtherapee-cli"
    state_file_name = "session.pp3"
    supported_adjustment_names = ("exposure", "contrast", "saturation", "orientation", "crop")

    def __init__(
        self,
        executable: str = "rawtherapee-cli",
        *,
        preview_quality: int = 70,
        export_quality: int = 92,
    ) -> None:
        self.executable = executable
        self.preview_quality = preview_quality
        self.export_quality = export_quality

    def ensure_available(self) -> None:
        if shutil.which(self.executable) is None:
            raise BackendUnavailableError(self.executable)

    def write_state_file(
        self,
        source: SourceImageInfo,
        adjustments: AdjustmentState,
        state_path: Path,
    ) -> None:
        self._validate_adjustments(adjustments, source)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            build_pp3(
                adjustments,
                image_width=source.width,
                image_height=source.height,
            ),
            encoding="utf-8",
        )

    def render_preview(
        self,
        source_path: Path,
        state_path: Path | None,
        target_path: Path,
        *,
        max_size: int | None = None,
        mode: RenderMode = RenderMode.CURRENT,
    ) -> tuple[int, int] | None:
        self.ensure_available()
        target_path = target_path.resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="rawtherapee-preview-", dir=target_path.parent) as temp_dir:
            temp_output = Path(temp_dir) / target_path.name
            command = self._base_command(
                source_path,
                state_path,
                temp_output,
                quality=self.preview_quality,
                mode=mode,
            )
            self._run(command)
            rendered_size = _image_dimensions(temp_output)

            if max_size is not None:
                self._resize_preview(temp_output, target_path, max_size=max_size)
            else:
                temp_output.replace(target_path)
            return rendered_size

    def render_export(
        self,
        source_path: Path,
        state_path: Path,
        target_path: Path,
    ) -> tuple[int, int] | None:
        self.ensure_available()
        target_path = target_path.resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        command = self._base_command(
            source_path,
            state_path,
            target_path,
            quality=self.export_quality,
            mode=RenderMode.CURRENT,
        )
        self._run(command)
        return _image_dimensions(target_path)

    def _validate_adjustments(self, adjustments: AdjustmentState, source: SourceImageInfo) -> None:
        unsupported: list[str] = []
        if adjustments.crop is not None and (source.width is None or source.height is None):
            unsupported.append("crop")
        if unsupported:
            raise ValidationError(
                f"Adjustments not yet supported by {self.backend_id}: {', '.join(unsupported)}.",
                hint="Create a session preview first so the backend can determine the developed image dimensions.",
            )

    def _base_command(
        self,
        source_path: Path,
        state_path: Path | None,
        target_path: Path,
        *,
        quality: int,
        mode: RenderMode = RenderMode.CURRENT,
    ) -> list[str]:
        output_args = self._output_args(target_path, quality)
        command = [
            self.executable,
            "-o",
            str(target_path),
            "-Y",
            *output_args,
        ]

        if mode == RenderMode.CURRENT and state_path is not None:
            command.extend(["-p", str(state_path)])
        elif mode == RenderMode.RAWTHERAPEE_DEFAULT:
            command.append("-d")

        command.extend(["-c", str(source_path)])
        return command

    def _output_args(self, target_path: Path, quality: int) -> list[str]:
        suffix = target_path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return [f"-j{quality}"]
        if suffix == ".png":
            return ["-n"]
        if suffix in {".tif", ".tiff"}:
            return ["-t"]
        raise ValidationError(
            f"Unsupported export format '{suffix or '<none>'}' for {self.backend_id}.",
            hint="Use .jpg, .jpeg, .png, .tif, or .tiff outputs.",
        )

    def _run(self, command: list[str]) -> None:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RenderFailedError(
                f"{self.executable} exited with status {completed.returncode}.",
                hint=_render_details(completed.stdout, completed.stderr),
            )

    def _resize_preview(self, source_path: Path, target_path: Path, *, max_size: int) -> None:
        if Image is None:
            source_path.replace(target_path)
            return

        with Image.open(source_path) as image:
            resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
            image.thumbnail((max_size, max_size), resampling)
            image.save(
                target_path,
                quality=self.preview_quality,
                optimize=True,
            )


def build_backend_registry() -> dict[str, RenderBackend]:
    """Return the supported backend instances keyed by backend id."""

    backends: dict[str, RenderBackend] = {}
    for backend in (RawTherapeeBackend(), DarktableBackend()):
        backends[backend.backend_id] = backend
    return backends


def normalize_backend_name(name: str) -> str:
    """Map aliases to supported backend ids."""

    lowered = name.strip().lower()
    aliases = {
        "darktable": "darktable-cli",
        "darktable-cli": "darktable-cli",
        "rawtherapee": "rawtherapee-cli",
        "rawtherapee-cli": "rawtherapee-cli",
    }
    return aliases.get(lowered, lowered)


def _render_details(stdout: str, stderr: str) -> str:
    details = "\n".join(
        part.strip()
        for part in (stdout, stderr)
        if part and part.strip()
    )
    return details or "Inspect backend output for more details."


def _image_dimensions(path: Path) -> tuple[int, int] | None:
    if Image is None:
        return None
    try:
        with Image.open(path) as image:
            return image.size
    except OSError:
        return None
