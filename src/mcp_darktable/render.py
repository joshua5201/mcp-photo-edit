"""darktable-cli rendering backend."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .errors import BackendUnavailableError, RenderFailedError


class DarktableCliRenderer:
    """Render previews and exports through darktable-cli."""

    def __init__(self, executable: str = "darktable-cli") -> None:
        self.executable = executable

    def ensure_available(self) -> None:
        """Ensure the renderer backend is installed."""

        if shutil.which(self.executable) is None:
            raise BackendUnavailableError(self.executable)

    def render(
        self,
        source_path: Path,
        xmp_path: Path | None,
        target_path: Path,
        *,
        max_size: int | None = None,
    ) -> None:
        """Render an image to the requested output path."""

        self.ensure_available()
        target_path = target_path.resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="darktable-render-", dir=target_path.parent) as temp_dir:
            temp_output_dir = Path(temp_dir)
            out_ext = target_path.suffix.lstrip(".") or "jpg"

            command = [self.executable, str(source_path)]
            if xmp_path is not None:
                command.append(str(xmp_path))
            command.extend([str(temp_output_dir), "--out-ext", out_ext])
            if max_size is not None:
                command.extend(["--width", str(max_size), "--height", str(max_size)])

            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                details = "\n".join(
                    part.strip()
                    for part in (completed.stdout, completed.stderr)
                    if part and part.strip()
                )
                raise RenderFailedError(
                    f"darktable-cli exited with status {completed.returncode}.",
                    hint=details or "Inspect darktable-cli output for more details.",
                )

            rendered_files = sorted(
                path for path in temp_output_dir.iterdir() if path.is_file()
            )
            if not rendered_files:
                raise RenderFailedError(
                    "darktable-cli completed without producing an output file.",
                    hint="Check whether the input file format is supported by the local darktable build.",
                )

            rendered_files[-1].replace(target_path)
