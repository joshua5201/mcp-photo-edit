"""Backend integrations for RawTherapee."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from .errors import BackendUnavailableError, RenderFailedError, ValidationError
from .models import AdjustmentState, SourceImageInfo
from .pp3 import build_pp3
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
        state_path: Path,
        target_path: Path,
        *,
        max_size: int | None = None,
    ) -> tuple[int, int] | None:
        """Render a preview image."""

    def render_export(
        self,
        source_path: Path,
        state_path: Path,
        target_path: Path,
    ) -> tuple[int, int] | None:
        """Render a final export."""


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
        state_path: Path,
        target_path: Path,
        *,
        max_size: int | None = None,
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
        state_path: Path,
        target_path: Path,
        *,
        quality: int,
    ) -> list[str]:
        output_args = self._output_args(target_path, quality)
        return [
            self.executable,
            "-o",
            str(target_path),
            "-Y",
            *output_args,
            "-p",
            str(state_path),
            "-c",
            str(source_path),
        ]

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

    backend = RawTherapeeBackend()
    return {backend.backend_id: backend}


def normalize_backend_name(name: str) -> str:
    """Map aliases to supported backend ids."""

    lowered = name.strip().lower()
    aliases = {
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
