"""Translate the normalized edit schema into native darktable XMP sidecars."""

from __future__ import annotations

import struct

from .models import AdjustmentState

DEFAULT_BLENDOP_VERSION = 10
DEFAULT_BLENDOP_PARAMS = "gz14eJxjYIAACQYYOOHEgAYY0QVwggZ7CB6pfNoAAEkgGQQ="
ORIENTATION_MAP = {
    0: 0,
    90: 6,
    -90: 5,
    180: 3,
}


def _hex_pack(fmt: str, *values: int | float) -> str:
    """Pack native darktable module params as lower-case hex."""

    return struct.pack(f"<{fmt}", *values).hex()


def _history_item(num: int, operation: str, modversion: int, params: str) -> str:
    """Render one darktable history entry."""

    return (
        "     <rdf:li "
        f'darktable:num="{num}" '
        f'darktable:operation="{operation}" '
        'darktable:enabled="1" '
        f'darktable:modversion="{modversion}" '
        f'darktable:params="{params}" '
        'darktable:multi_name="" '
        'darktable:multi_priority="0" '
        f'darktable:blendop_version="{DEFAULT_BLENDOP_VERSION}" '
        f'darktable:blendop_params="{DEFAULT_BLENDOP_PARAMS}"/>\n'
    )


def build_sidecar(source_file_name: str, adjustments: AdjustmentState) -> str:
    """Render a native darktable history stack for the supported MVP adjustments."""

    history: list[str] = []

    if adjustments.exposure != 0.0:
        history.append(
            _history_item(
                len(history),
                "exposure",
                7,
                _hex_pack("iffffii", 0, 0.0, adjustments.exposure, 50.0, -4.0, 0, 1),
            )
        )

    if adjustments.contrast != 0.0 or adjustments.saturation != 0.0:
        contrast = max(0.01, min(1.99, 1.0 + adjustments.contrast / 100.0))
        saturation = max(0.0, min(2.0, 1.0 + adjustments.saturation / 100.0))
        history.append(
            _history_item(
                len(history),
                "colorbalance",
                3,
                _hex_pack(
                    "i16f",
                    1,
                    *([1.0] * 12),
                    saturation,
                    contrast,
                    18.0,
                    1.0,
                ),
            )
        )

    if adjustments.orientation != 0:
        history.append(
            _history_item(
                len(history),
                "flip",
                2,
                _hex_pack("i", ORIENTATION_MAP[adjustments.orientation]),
            )
        )

    if adjustments.crop is not None:
        history.append(
            _history_item(
                len(history),
                "crop",
                3,
                _hex_pack(
                    "ffffii",
                    adjustments.crop.left,
                    adjustments.crop.top,
                    adjustments.crop.right,
                    adjustments.crop.bottom,
                    -1,
                    -1,
                ),
            )
        )

    history_end_attr = (
        f'\n   darktable:history_end="{len(history) - 1}"' if history else ""
    )
    auto_presets = "0" if history else "1"
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<x:xmpmeta xmlns:x=\"adobe:ns:meta/\" x:xmptk=\"XMP Core 4.4.0-Exiv2\">\n"
        " <rdf:RDF xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\">\n"
        "  <rdf:Description rdf:about=\"\"\n"
        "    xmlns:xmp=\"http://ns.adobe.com/xap/1.0/\"\n"
        "    xmlns:xmpMM=\"http://ns.adobe.com/xap/1.0/mm/\"\n"
        "    xmlns:darktable=\"http://darktable.sf.net/\"\n"
        "   xmp:Rating=\"0\"\n"
        f"   xmpMM:DerivedFrom=\"{source_file_name}\"\n"
        "   darktable:xmp_version=\"4\"\n"
        "   darktable:raw_params=\"0\"\n"
        f"   darktable:auto_presets_applied=\"{auto_presets}\""
        f"{history_end_attr}>\n"
        "   <darktable:masks_history>\n"
        "    <rdf:Seq/>\n"
        "   </darktable:masks_history>\n"
        "   <darktable:history>\n"
        "    <rdf:Seq>\n"
        f"{''.join(history)}"
        "    </rdf:Seq>\n"
        "   </darktable:history>\n"
        "  </rdf:Description>\n"
        " </rdf:RDF>\n"
        "</x:xmpmeta>\n"
    )
