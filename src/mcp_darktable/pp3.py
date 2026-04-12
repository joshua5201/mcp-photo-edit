"""Minimal RawTherapee PP3 generation."""

from __future__ import annotations

from .models import AdjustmentState


def _fmt(value: float) -> str:
    return format(value, ".12g")


def build_pp3(adjustments: AdjustmentState) -> str:
    """Build a minimal partial PP3 profile for supported adjustments."""

    exposure_lines = [
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
    return "\n".join(exposure_lines) + "\n"
