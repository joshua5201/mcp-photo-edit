"""Backend integrations for RawTherapee."""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from .errors import BackendUnavailableError, RenderFailedError, ValidationError
from .models import (
    AdjustmentState,
    DiagnosticDimensions,
    DiagnosticLumaSummary,
    DiagnosticRGBBalanceSummary,
    DiagnosticSaturationSummary,
    DiagnosticSummary,
    SourceImageInfo,
)
from .pp3 import build_pp3
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - optional at import time, required at runtime for resizing
    Image = None
    ImageDraw = None
    ImageFont = None


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
    supported_adjustment_names = (
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
            self._require_output(temp_output)
            rendered_size = _image_dimensions(temp_output)

            if max_size is not None:
                self._resize_preview(temp_output, target_path, max_size=max_size)
            else:
                temp_output.replace(target_path)
            self._require_output(target_path)
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
        self._require_output(target_path)
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

    def _require_output(self, target_path: Path) -> None:
        if target_path.exists():
            return
        raise RenderFailedError(
            f"{self.executable} completed without producing '{target_path.name}'.",
            hint="Inspect backend output and verify the source file, PP3 profile, and output format.",
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


class AdvancedImageInfoRenderer:
    """Generate a truthful dashboard and summary from a preview raster."""

    def __init__(
        self,
        *,
        dashboard_size: tuple[int, int] = (1280, 1024),
    ) -> None:
        self.dashboard_width, self.dashboard_height = dashboard_size

    def render(self, preview_path: Path, dashboard_path: Path) -> DiagnosticSummary:
        if Image is None or ImageDraw is None or ImageFont is None:
            raise RenderFailedError(
                "Pillow is required to generate advanced image info.",
                hint="Install the Pillow dependency to enable the diagnostic dashboard.",
            )

        with Image.open(preview_path) as preview_image:
            rgb_image = preview_image.convert("RGB")
            summary = self._summarize(rgb_image)
            dashboard_path = dashboard_path.resolve()
            dashboard_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = dashboard_path.with_name(f".{dashboard_path.name}.tmp")
            self._draw_dashboard(rgb_image, summary, temp_path)
            temp_path.replace(dashboard_path)
            return summary

    def _summarize(self, image: Image.Image) -> DiagnosticSummary:
        width, height = image.size
        pixels = image.getdata()
        pixel_count = width * height
        if pixel_count <= 0:
            raise RenderFailedError("The preview image is empty.")

        red_hist = [0] * 256
        green_hist = [0] * 256
        blue_hist = [0] * 256
        luma_hist = [0] * 256
        saturation_hist = [0] * 101
        red_sum = 0.0
        green_sum = 0.0
        blue_sum = 0.0

        for red, green, blue in pixels:
            red_hist[red] += 1
            green_hist[green] += 1
            blue_hist[blue] += 1
            red_sum += red
            green_sum += green
            blue_sum += blue

            luma = 0.2126 * red + 0.7152 * green + 0.0722 * blue
            luma_hist[min(255, max(0, int(round(luma))))] += 1

            saturation = _rgb_saturation(red, green, blue)
            saturation_hist[min(100, max(0, int(round(saturation * 100.0))))] += 1

        luma_stats = _histogram_percentiles(luma_hist, [1.0, 50.0, 99.0])
        saturation_stats = _histogram_percentiles(saturation_hist, [50.0, 95.0])
        clipped_black_pct = _histogram_tail_pct(luma_hist, upper_bound=1)
        clipped_white_pct = _histogram_tail_pct(luma_hist, lower_bound=254)

        red_mean = red_sum / pixel_count
        green_mean = green_sum / pixel_count
        blue_mean = blue_sum / pixel_count

        temperature_hint = _temperature_hint(red_mean, blue_mean)
        tint_hint = _tint_hint(red_mean, green_mean, blue_mean)

        high_saturation_pct = _histogram_tail_pct(saturation_hist, lower_bound=75)

        return DiagnosticSummary(
            dimensions=DiagnosticDimensions(width=width, height=height),
            luma=DiagnosticLumaSummary(
                p01=luma_stats[1.0],
                p50=luma_stats[50.0],
                p99=luma_stats[99.0],
                clipped_black_pct=clipped_black_pct,
                clipped_white_pct=clipped_white_pct,
            ),
            rgb_balance=DiagnosticRGBBalanceSummary(
                red_mean=red_mean,
                green_mean=green_mean,
                blue_mean=blue_mean,
                temperature_hint=temperature_hint,
                tint_hint=tint_hint,
            ),
            saturation=DiagnosticSaturationSummary(
                p50=saturation_stats[50.0],
                p95=saturation_stats[95.0],
                high_saturation_pct=high_saturation_pct,
            ),
        )

    def _draw_dashboard(self, image: Image.Image, summary: DiagnosticSummary, output_path: Path) -> None:
        canvas = Image.new("RGB", (self.dashboard_width, self.dashboard_height), "#f5f2eb")
        draw = ImageDraw.Draw(canvas)
        title_font = self._font(28)
        heading_font = self._font(20)
        body_font = self._font(15)
        small_font = self._font(13)

        margin = 32
        draw.text((margin, 18), "Advanced Image Info", fill="#1a1a1a", font=title_font)
        draw.text(
            (margin, 56),
            f"analysis source: {summary.analysis_source}",
            fill="#555555",
            font=body_font,
        )
        draw.text(
            (self.dashboard_width - 360, 56),
            f"{summary.dimensions.width} x {summary.dimensions.height} px",
            fill="#555555",
            font=body_font,
        )

        histogram_box = (margin, 92, self.dashboard_width - margin, 596)
        self._draw_histogram_panel(draw, histogram_box, image, summary, heading_font, body_font, small_font)

        card_top = 630
        card_gap = 20
        card_width = (self.dashboard_width - margin * 2 - card_gap * 2) // 3
        card_height = 340
        self._draw_luma_card(
            canvas,
            draw,
            (margin, card_top, margin + card_width, card_top + card_height),
            summary,
            heading_font,
            body_font,
            small_font,
        )
        self._draw_rgb_card(
            canvas,
            draw,
            (margin + card_width + card_gap, card_top, margin + card_width * 2 + card_gap, card_top + card_height),
            summary,
            heading_font,
            body_font,
            small_font,
        )
        self._draw_saturation_card(
            canvas,
            draw,
            (
                margin + card_width * 2 + card_gap * 2,
                card_top,
                self.dashboard_width - margin,
                card_top + card_height,
            ),
            summary,
            heading_font,
            body_font,
            small_font,
        )

        canvas.save(output_path, format="PNG")

    def _draw_histogram_panel(
        self,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        image: Image.Image,
        summary: DiagnosticSummary,
        heading_font,
        body_font,
        small_font,
    ) -> None:
        left, top, right, bottom = box
        draw.rounded_rectangle(box, radius=18, fill="#ffffff", outline="#d5d0c7", width=2)
        draw.text((left + 20, top + 14), "Histogram", fill="#1f1f1f", font=heading_font)
        draw.text(
            (right - 240, top + 18),
            f"clipped black {summary.luma.clipped_black_pct:.2f}% | clipped white {summary.luma.clipped_white_pct:.2f}%",
            fill="#555555",
            font=small_font,
        )

        plot_left = left + 24
        plot_top = top + 60
        plot_right = right - 24
        plot_bottom = bottom - 28
        draw.rectangle((plot_left, plot_top, plot_right, plot_bottom), fill="#f7f7f3", outline="#e4dfd5")

        histograms = _channel_histograms(image)
        luma_hist = _luma_histogram(image)
        max_value = max(max(channel) for channel in histograms + [luma_hist])
        if max_value <= 0:
            max_value = 1

        for fraction in (0.25, 0.5, 0.75):
            y = plot_bottom - int((plot_bottom - plot_top) * fraction)
            draw.line((plot_left, y, plot_right, y), fill="#ece6dc", width=1)

        self._draw_histogram_curve(draw, histograms[0], plot_left, plot_top, plot_right, plot_bottom, max_value, "#d33c3c")
        self._draw_histogram_curve(draw, histograms[1], plot_left, plot_top, plot_right, plot_bottom, max_value, "#3d9a49")
        self._draw_histogram_curve(draw, histograms[2], plot_left, plot_top, plot_right, plot_bottom, max_value, "#3b6fd8")
        self._draw_histogram_curve(draw, luma_hist, plot_left, plot_top, plot_right, plot_bottom, max_value, "#333333")

        draw.text((plot_left + 4, plot_bottom + 4), "0", fill="#666666", font=small_font)
        draw.text((plot_right - 12, plot_bottom + 4), "255", fill="#666666", font=small_font)

    def _draw_histogram_curve(
        self,
        draw: ImageDraw.ImageDraw,
        values: list[int],
        left: int,
        top: int,
        right: int,
        bottom: int,
        maximum: int,
        color: str,
    ) -> None:
        width = right - left
        height = bottom - top
        if width <= 1 or height <= 1:
            return
        points: list[tuple[int, int]] = []
        for index, value in enumerate(values):
            x = left + int((index / max(1, len(values) - 1)) * width)
            y = bottom - int((value / maximum) * height)
            points.append((x, y))
        draw.line(points, fill=color, width=2)

    def _draw_luma_card(
        self,
        canvas: Image.Image,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        summary: DiagnosticSummary,
        heading_font,
        body_font,
        small_font,
    ) -> None:
        self._draw_card_shell(draw, box, "Luma", heading_font)
        left, top, right, bottom = box
        lines = [
            f"p01: {summary.luma.p01:.1f}",
            f"p50: {summary.luma.p50:.1f}",
            f"p99: {summary.luma.p99:.1f}",
            f"clipped black: {summary.luma.clipped_black_pct:.2f}%",
            f"clipped white: {summary.luma.clipped_white_pct:.2f}%",
        ]
        self._draw_key_value_block(draw, left + 18, top + 52, lines, body_font)
        self._draw_bar(draw, (left + 18, bottom - 72, right - 18, bottom - 46), summary.luma.p50 / 255.0, "#4a6fa5")
        draw.text((left + 18, bottom - 40), "median luma", fill="#666666", font=small_font)

    def _draw_rgb_card(
        self,
        canvas: Image.Image,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        summary: DiagnosticSummary,
        heading_font,
        body_font,
        small_font,
    ) -> None:
        self._draw_card_shell(draw, box, "RGB balance", heading_font)
        left, top, right, bottom = box
        lines = [
            f"red mean: {summary.rgb_balance.red_mean:.1f}",
            f"green mean: {summary.rgb_balance.green_mean:.1f}",
            f"blue mean: {summary.rgb_balance.blue_mean:.1f}",
            f"temperature hint: {summary.rgb_balance.temperature_hint}",
            f"tint hint: {summary.rgb_balance.tint_hint}",
        ]
        self._draw_key_value_block(draw, left + 18, top + 52, lines, body_font)

        max_mean = max(summary.rgb_balance.red_mean, summary.rgb_balance.green_mean, summary.rgb_balance.blue_mean, 1.0)
        bar_left = left + 18
        bar_right = right - 18
        bar_top = bottom - 104
        bar_height = 18
        self._draw_bar(draw, (bar_left, bar_top, bar_right, bar_top + bar_height), summary.rgb_balance.red_mean / max_mean, "#d33c3c")
        self._draw_bar(draw, (bar_left, bar_top + 24, bar_right, bar_top + 24 + bar_height), summary.rgb_balance.green_mean / max_mean, "#3d9a49")
        self._draw_bar(draw, (bar_left, bar_top + 48, bar_right, bar_top + 48 + bar_height), summary.rgb_balance.blue_mean / max_mean, "#3b6fd8")
        draw.text((bar_left, bottom - 28), "relative channel means", fill="#666666", font=small_font)

    def _draw_saturation_card(
        self,
        canvas: Image.Image,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        summary: DiagnosticSummary,
        heading_font,
        body_font,
        small_font,
    ) -> None:
        self._draw_card_shell(draw, box, "Saturation", heading_font)
        left, top, right, bottom = box
        lines = [
            f"p50: {summary.saturation.p50:.1f}%",
            f"p95: {summary.saturation.p95:.1f}%",
            f"high saturation: {summary.saturation.high_saturation_pct:.2f}%",
        ]
        self._draw_key_value_block(draw, left + 18, top + 52, lines, body_font)
        self._draw_bar(draw, (left + 18, bottom - 72, right - 18, bottom - 46), summary.saturation.p95 / 100.0, "#a3682b")
        draw.text((left + 18, bottom - 40), "saturation percentile range", fill="#666666", font=small_font)

    def _draw_card_shell(
        self,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        title: str,
        heading_font,
    ) -> None:
        draw.rounded_rectangle(box, radius=18, fill="#ffffff", outline="#d5d0c7", width=2)
        left, top, *_ = box
        draw.text((left + 18, top + 14), title, fill="#1f1f1f", font=heading_font)

    def _draw_key_value_block(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        lines: list[str],
        font,
    ) -> None:
        line_height = _text_line_height(font)
        for index, line in enumerate(lines):
            draw.text((x, y + index * line_height), line, fill="#404040", font=font)

    def _draw_bar(
        self,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        fraction: float,
        color: str,
    ) -> None:
        left, top, right, bottom = box
        draw.rounded_rectangle(box, radius=8, fill="#ece7de")
        fraction = max(0.0, min(1.0, fraction))
        fill_right = left + int((right - left) * fraction)
        draw.rounded_rectangle((left, top, fill_right, bottom), radius=8, fill=color)

    def _font(self, size: int):
        if ImageFont is None:
            raise RenderFailedError("Pillow fonts are unavailable.")
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size=size)
        except OSError:
            return ImageFont.load_default()


def _channel_histograms(image: Image.Image) -> list[list[int]]:
    red_hist = [0] * 256
    green_hist = [0] * 256
    blue_hist = [0] * 256
    for red, green, blue in image.getdata():
        red_hist[red] += 1
        green_hist[green] += 1
        blue_hist[blue] += 1
    return [red_hist, green_hist, blue_hist]


def _luma_histogram(image: Image.Image) -> list[int]:
    luma_hist = [0] * 256
    for red, green, blue in image.getdata():
        luma = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        luma_hist[min(255, max(0, int(round(luma))))] += 1
    return luma_hist


def _histogram_percentiles(histogram: list[int], percentiles: list[float]) -> dict[float, float]:
    total = sum(histogram)
    if total <= 0:
        return {percentile: 0.0 for percentile in percentiles}

    result: dict[float, float] = {}
    for percentile in percentiles:
        threshold = total * (percentile / 100.0)
        cumulative = 0
        for index, count in enumerate(histogram):
            cumulative += count
            if cumulative >= threshold:
                result[percentile] = float(index)
                break
        else:
            result[percentile] = float(len(histogram) - 1)
    return result


def _histogram_tail_pct(
    histogram: list[int],
    *,
    lower_bound: int | None = None,
    upper_bound: int | None = None,
) -> float:
    total = sum(histogram)
    if total <= 0:
        return 0.0

    if lower_bound is not None:
        count = sum(histogram[lower_bound:])
    elif upper_bound is not None:
        count = sum(histogram[: upper_bound + 1])
    else:
        count = 0
    return (count / total) * 100.0


def _rgb_saturation(red: int, green: int, blue: int) -> float:
    maximum = max(red, green, blue)
    minimum = min(red, green, blue)
    if maximum <= 0:
        return 0.0
    return (maximum - minimum) / maximum


def _temperature_hint(red_mean: float, blue_mean: float) -> str:
    delta = red_mean - blue_mean
    if delta > 12.0:
        return "warm"
    if delta < -12.0:
        return "cool"
    return "neutral"


def _tint_hint(red_mean: float, green_mean: float, blue_mean: float) -> str:
    neutral_green = (red_mean + blue_mean) / 2.0
    delta = green_mean - neutral_green
    if delta > 8.0:
        return "green"
    if delta < -8.0:
        return "magenta"
    return "neutral"


def _text_line_height(font) -> int:
    bbox = font.getbbox("Ag")
    return int(math.ceil((bbox[3] - bbox[1]) * 1.25))


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
