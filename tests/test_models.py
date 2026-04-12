from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_photo_edit.models import AdjustmentPatch, AdjustmentState, CropAdjustment, RGBMixer


def test_crop_requires_positive_area() -> None:
    with pytest.raises(ValidationError):
        CropAdjustment(left=0.8, top=0.1, right=0.2, bottom=0.9)


def test_adjustment_patch_updates_only_supplied_fields() -> None:
    state = AdjustmentState()
    updated = state.apply_patch(AdjustmentPatch(exposure=1.25, saturation=8.0))

    assert updated.exposure == 1.25
    assert updated.saturation == 8.0
    assert updated.contrast == 0.0


def test_orientation_is_limited_to_quarter_turns() -> None:
    with pytest.raises(ValidationError):
        AdjustmentPatch(orientation=45)


def test_rgb_mixer_validates_channel_bounds() -> None:
    with pytest.raises(ValidationError):
        RGBMixer(red=(600.0, 0.0, 0.0))


def test_adjustment_patch_supports_new_rawtherapee_fields() -> None:
    state = AdjustmentState()
    updated = state.apply_patch(
        AdjustmentPatch(
            rgb_mixer=RGBMixer(
                red=(100.0, 0.0, 0.0),
                green=(0.0, 90.0, 10.0),
                blue=(0.0, 0.0, 100.0),
            ),
            denoise_luma=12.0,
            denoise_detail=18.0,
            denoise_chroma=24.0,
            color_temperature=5200.0,
            green_balance=1.03,
            highlights=15.0,
            shadows=22.0,
        )
    )

    assert updated.rgb_mixer is not None
    assert updated.rgb_mixer.green == (0.0, 90.0, 10.0)
    assert updated.denoise_luma == 12.0
    assert updated.denoise_detail == 18.0
    assert updated.denoise_chroma == 24.0
    assert updated.color_temperature == 5200.0
    assert updated.green_balance == 1.03
    assert updated.highlights == 15.0
    assert updated.shadows == 22.0
