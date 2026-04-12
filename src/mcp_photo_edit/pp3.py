"""Minimal RawTherapee PP3 generation."""

from __future__ import annotations

from .errors import ValidationError
from .models import AdjustmentState


def _fmt(value: float) -> str:
    return format(value, ".12g")


def build_pp3(
    adjustments: AdjustmentState,
    *,
    image_width: int | None = None,
    image_height: int | None = None,
) -> str:
    """Build a minimal partial PP3 profile for supported adjustments."""

    lines = [
        "[Exposure]",
        "Auto=false",
        f"Compensation={_fmt(adjustments.exposure)}",
        "Brightness=0",
        f"Contrast={_fmt(adjustments.contrast)}",
        f"Saturation={_fmt(adjustments.saturation)}",
        "Black=0",
        "HistogramMatching=false",
        "CurveFromHistogramMatching=false",
        "ClampOOG=false",
        "CurveMode=Standard",
        "CurveMode2=Standard",
    ]

    if adjustments.rgb_mixer is not None and not adjustments.rgb_mixer.is_identity():
        lines.extend(
            [
                "",
                "[Channel Mixer]",
                "Enabled=true",
                f"Red={_fmt_channel_mixer_row(adjustments.rgb_mixer.red)}",
                f"Green={_fmt_channel_mixer_row(adjustments.rgb_mixer.green)}",
                f"Blue={_fmt_channel_mixer_row(adjustments.rgb_mixer.blue)}",
            ]
        )

    if _has_denoise(adjustments):
        lines.extend(
            [
                "",
                "[Directional Pyramid Denoising]",
                "Enabled=true",
                "Enhance=false",
                "Median=false",
                f"Luma={_fmt(adjustments.denoise_luma)}",
                f"Ldetail={_fmt(adjustments.denoise_detail)}",
                f"Chroma={_fmt(adjustments.denoise_chroma)}",
                "Method=Lab",
                "LMethod=SLI",
                "CMethod=MAN",
                "C2Method=AUTO",
                "SMethod=shal",
                "MedMethod=soft",
                "RGBMethod=soft",
                "MethodMed=none",
                "Redchro=0",
                "Bluechro=0",
                "AutoGain=true",
                "Gamma=1.7",
                "Passes=1",
                "LCurve=0;",
                "CCCurve=0;",
            ]
        )

    if adjustments.color_temperature is not None or adjustments.green_balance is not None:
        lines.extend(
            [
                "",
                "[White Balance]",
                "Enabled=true",
                "Setting=Custom",
                f"Temperature={_fmt(adjustments.color_temperature if adjustments.color_temperature is not None else 6504.0)}",
                f"Green={_fmt(adjustments.green_balance if adjustments.green_balance is not None else 1.0)}",
                "Equal=1",
                "TemperatureBias=0",
                "CompatibilityVersion=2",
            ]
        )

    if adjustments.highlights != 0.0 or adjustments.shadows != 0.0:
        lines.extend(
            [
                "",
                "[Shadows & Highlights]",
                "Enabled=true",
                f"Highlights={_fmt(adjustments.highlights)}",
                "HighlightTonalWidth=70",
                f"Shadows={_fmt(adjustments.shadows)}",
                "ShadowTonalWidth=30",
                "Radius=40",
                "Lab=false",
            ]
        )

    if adjustments.orientation != 0:
        lines.extend(
            [
                "",
                "[Coarse Transformation]",
                f"Rotate={_coarse_rotation_value(adjustments.orientation)}",
            ]
        )

    if adjustments.crop is not None:
        x, y, w, h = _crop_box_pixels(
            adjustments,
            image_width=image_width,
            image_height=image_height,
        )
        lines.extend(
            [
                "",
                "[Crop]",
                "Enabled=true",
                f"X={x}",
                f"Y={y}",
                f"W={w}",
                f"H={h}",
                "FixedRatio=false",
                "Ratio=As Image",
                "Orientation=As Image",
                "Guide=Frame",
            ]
        )

    return "\n".join(lines) + "\n"


def _coarse_rotation_value(orientation: int) -> int:
    mapping = {
        -90: 270,
        0: 0,
        90: 90,
        180: 180,
    }
    return mapping[orientation]


def _fmt_channel_mixer_row(row: tuple[float, float, float]) -> str:
    values = [str(round(channel * 10)) for channel in row]
    return ";".join(values) + ";"


def _has_denoise(adjustments: AdjustmentState) -> bool:
    return any(
        value != 0.0
        for value in (
            adjustments.denoise_luma,
            adjustments.denoise_detail,
            adjustments.denoise_chroma,
        )
    )


def _crop_box_pixels(
    adjustments: AdjustmentState,
    *,
    image_width: int | None,
    image_height: int | None,
) -> tuple[int, int, int, int]:
    crop = adjustments.crop
    if crop is None:
        raise ValidationError("Crop values were requested without a crop box.")
    if image_width is None or image_height is None:
        raise ValidationError(
            "Image dimensions are required to generate crop settings.",
            hint="Create the session preview first so the backend can determine the developed image size.",
        )

    oriented_width, oriented_height = _oriented_dimensions(
        image_width,
        image_height,
        adjustments.orientation,
    )
    left = _clamp_int(round(crop.left * oriented_width), minimum=0, maximum=oriented_width - 1)
    top = _clamp_int(round(crop.top * oriented_height), minimum=0, maximum=oriented_height - 1)
    right = _clamp_int(round(crop.right * oriented_width), minimum=left + 1, maximum=oriented_width)
    bottom = _clamp_int(round(crop.bottom * oriented_height), minimum=top + 1, maximum=oriented_height)
    return left, top, right - left, bottom - top


def _oriented_dimensions(width: int, height: int, orientation: int) -> tuple[int, int]:
    if orientation in {-90, 90}:
        return height, width
    return width, height


def _clamp_int(value: int, *, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))
