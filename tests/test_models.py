from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_darktable.models import AdjustmentPatch, AdjustmentState, CropAdjustment


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
