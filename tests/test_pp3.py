from __future__ import annotations

from mcp_photo_edit.models import AdjustmentState
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
