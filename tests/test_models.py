from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_photo_edit.models import (
    AdjustmentPatch,
    AdjustmentState,
    CropAdjustment,
    HistoryStep,
    PreviewResult,
    RGBMixer,
    SessionState,
    SourceImageInfo,
)


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
            sharpen_amount=180,
            sharpen_radius=0.8,
            sharpen_contrast=28.0,
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
    assert updated.sharpen_amount == 180.0
    assert updated.sharpen_radius == 0.8
    assert updated.sharpen_contrast == 28.0


def test_manual_white_balance_normalizes_missing_pair_value() -> None:
    updated = AdjustmentState().apply_patch(AdjustmentPatch(green_balance=1.08))

    assert updated.green_balance == 1.08
    assert updated.color_temperature == 6504.0


def test_manual_white_balance_reset_keeps_other_field_independent() -> None:
    state = AdjustmentState(color_temperature=5200.0, green_balance=1.08)

    reset = state.reset_fields(["green_balance"])

    assert reset.color_temperature == 5200.0
    assert reset.green_balance is None


def test_sharpening_fields_validate_ranges() -> None:
    with pytest.raises(ValidationError):
        AdjustmentPatch(sharpen_radius=0.2)

    with pytest.raises(ValidationError):
        AdjustmentPatch.model_validate({"sharpen_amount": 0.5})


def test_session_and_preview_models_include_nullable_advanced_image_info_fields() -> None:
    history_step = HistoryStep(
        step_id="0001",
        kind="init",
        adjustments=AdjustmentState(),
    )
    session = SessionState(
        session_id="session-123",
        source=SourceImageInfo(
            input_path="/tmp/source.jpg",
            file_name="source.jpg",
            suffix=".jpg",
        ),
        workspace_dir="/tmp/workspace/session-123",
        preview_path="/tmp/workspace/session-123/preview-0001.jpg",
        history=[
            HistoryStep(
                step_id="0001",
                kind="init",
                adjustments=AdjustmentState(),
            )
        ],
        history_index=0,
    )
    preview = PreviewResult(preview_path="/tmp/workspace/session-123/preview-0001.jpg")

    assert session.diagnostic_dashboard_path is None
    assert session.diagnostic_summary is None
    assert preview.diagnostic_dashboard_path is None
    assert preview.diagnostic_summary is None
    assert history_step.diagnostic_dashboard_path is None
    assert history_step.diagnostic_summary is None
    assert session.model_dump()["diagnostic_dashboard_path"] is None
    assert preview.model_dump()["diagnostic_summary"] is None
