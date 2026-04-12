from __future__ import annotations

from mcp_darktable.models import AdjustmentState, CropAdjustment
from mcp_darktable.xmp import build_sidecar


def test_build_sidecar_contains_native_darktable_history() -> None:
    xmp = build_sidecar(
        "source.ppm",
        AdjustmentState(
            exposure=1.25,
            contrast=10.0,
            saturation=8.0,
            orientation=90,
            crop=CropAdjustment(left=0.1, top=0.2, right=0.9, bottom=0.95),
        ),
    )

    assert 'xmlns:darktable="http://darktable.sf.net/"' in xmp
    assert 'darktable:operation="exposure"' in xmp
    assert 'darktable:operation="colorbalance"' in xmp
    assert 'darktable:operation="flip"' in xmp
    assert 'darktable:operation="crop"' in xmp
