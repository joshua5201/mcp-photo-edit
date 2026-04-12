from __future__ import annotations

from mcp_photo_edit.models import AdjustmentState, RGBMixer
from mcp_photo_edit.pp3 import build_pp3


def test_build_pp3_contains_supported_exposure_fields() -> None:
    pp3 = build_pp3(
        AdjustmentState(
            exposure=1.25,
            contrast=10.0,
            saturation=8.0,
        ),
        image_width=4032,
        image_height=6056,
    )

    assert "[Exposure]" in pp3
    assert "Compensation=1.25" in pp3
    assert "Contrast=10" in pp3
    assert "Saturation=8" in pp3


def test_build_pp3_contains_rotation_and_crop_blocks() -> None:
    pp3 = build_pp3(
        AdjustmentState(
            orientation=-90,
            crop={"left": 0.25, "top": 0.25, "right": 0.75, "bottom": 0.75},
        ),
        image_width=4032,
        image_height=6056,
    )

    assert "[Coarse Transformation]" in pp3
    assert "Rotate=270" in pp3
    assert "[Crop]" in pp3
    assert "X=1514" in pp3
    assert "Y=1008" in pp3
    assert "W=3028" in pp3
    assert "H=2016" in pp3


def test_build_pp3_contains_rgb_mixer_denoise_white_balance_and_tone_blocks() -> None:
    pp3 = build_pp3(
        AdjustmentState(
            rgb_mixer=RGBMixer(
                red=(100.0, 0.0, 0.0),
                green=(0.0, 92.5, 7.5),
                blue=(5.0, 0.0, 95.0),
            ),
            denoise_luma=10.0,
            denoise_detail=20.0,
            denoise_chroma=30.0,
            color_temperature=5400.0,
            green_balance=1.02,
            highlights=12.0,
            shadows=18.0,
        ),
        image_width=4032,
        image_height=6056,
    )

    assert "[Channel Mixer]" in pp3
    assert "Enabled=true" in pp3
    assert "Red=1000;0;0;" in pp3
    assert "Green=0;925;75;" in pp3
    assert "Blue=50;0;950;" in pp3
    assert "[Directional Pyramid Denoising]" in pp3
    assert "Luma=10" in pp3
    assert "Ldetail=20" in pp3
    assert "Chroma=30" in pp3
    assert "[White Balance]" in pp3
    assert "Setting=Custom" in pp3
    assert "Temperature=5400" in pp3
    assert "Green=1.02" in pp3
    assert "[Shadows & Highlights]" in pp3
    assert "Highlights=12" in pp3
    assert "Shadows=18" in pp3


def test_build_pp3_uses_normalized_manual_white_balance_defaults() -> None:
    pp3 = build_pp3(
        AdjustmentState(green_balance=1.08),
        image_width=4032,
        image_height=6056,
    )

    assert "[White Balance]" in pp3
    assert "Setting=Custom" in pp3
    assert "Temperature=6504" in pp3
    assert "Green=1.08" in pp3


def test_build_pp3_contains_sharpening_block() -> None:
    pp3 = build_pp3(
        AdjustmentState(
            sharpen_amount=180.0,
            sharpen_radius=0.8,
            sharpen_contrast=30.0,
        ),
        image_width=4032,
        image_height=6056,
    )

    assert "[Sharpening]" in pp3
    assert "Enabled=true" in pp3
    assert "Method=usm" in pp3
    assert "Amount=180" in pp3
    assert "Radius=0.8" in pp3
    assert "Contrast=30" in pp3
    assert "BlurRadius=0.2" in pp3
