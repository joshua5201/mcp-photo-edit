from __future__ import annotations

from mcp_darktable.models import AdjustmentState
from mcp_darktable.pp3 import build_pp3


def test_build_pp3_contains_supported_exposure_fields() -> None:
    pp3 = build_pp3(
        AdjustmentState(
            exposure=1.25,
            contrast=10.0,
            saturation=8.0,
        )
    )

    assert "[Exposure]" in pp3
    assert "Compensation=1.25" in pp3
    assert "Contrast=10" in pp3
    assert "Saturation=8" in pp3
