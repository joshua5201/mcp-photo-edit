"""End-to-end MCP stdio coverage using the real RawTherapee adapter."""

from __future__ import annotations

import asyncio
import hashlib
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image
from pydantic import BaseModel

from mcp_photo_edit.models import (
    ExportResult,
    PreviewResult,
    SessionEnvelope,
    SessionState,
    SupportedAdjustmentsResult,
)

pytestmark = [
    pytest.mark.raw_e2e,
    pytest.mark.skipif(
        os.environ.get("MCP_PHOTO_EDIT_RAW_E2E") != "1",
        reason="set MCP_PHOTO_EDIT_RAW_E2E=1 to run the real RawTherapee E2E test",
    ),
]

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "raw" / "no_people_bird.nef"
EXPECTED_TOOLS = {
    "apply_adjustments",
    "create_edit_session",
    "export_image",
    "get_edit_session",
    "list_supported_adjustments",
    "redo_adjustment",
    "render_preview",
    "reset_adjustments",
    "undo_adjustment",
}


def test_mcp_stdio_calls_real_rawtherapee(tmp_path: Path) -> None:
    """Run the public MCP workflow through a real stdio server and renderer."""

    assert FIXTURE_PATH.is_file(), f"Missing public RAW fixture: {FIXTURE_PATH}"
    asyncio.run(_run_e2e(tmp_path))


async def _run_e2e(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    server_environment = os.environ.copy()
    server_environment["MCP_PHOTO_EDIT_WORKDIR"] = str(workspace_root)
    server_parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_photo_edit"],
        env=server_environment,
        cwd=Path.cwd(),
    )

    async with (
        stdio_client(server_parameters) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        assert {tool.name for tool in tools.tools} == EXPECTED_TOOLS

        supported = await _call_tool(
            session,
            "list_supported_adjustments",
            None,
            SupportedAdjustmentsResult,
        )
        assert supported.ok
        assert supported.error is None
        assert {adjustment.name for adjustment in supported.adjustments} >= {
            "contrast",
            "exposure",
            "saturation",
        }

        created = await _call_tool(
            session,
            "create_edit_session",
            {
                "input_path": str(FIXTURE_PATH.resolve()),
                "preview_max_size": 640,
                "session_label": "raw-e2e",
            },
            SessionEnvelope,
        )
        initial = _require_session(created)
        assert initial.backend == "mcp-photo-edit-rawtherapee"
        assert initial.history_length == 1
        assert initial.history_index == 0
        initial_preview_size, initial_digest = _preview_digest(
            _workspace_artifact(initial.preview_path, workspace_root)
        )
        assert max(initial_preview_size) <= 640

        fetched = await _call_tool(
            session,
            "get_edit_session",
            {"session_id": initial.session_id},
            SessionEnvelope,
        )
        assert _require_session(fetched).session_id == initial.session_id

        applied = await _call_tool(
            session,
            "apply_adjustments",
            {
                "session_id": initial.session_id,
                "adjustments": {"exposure": 0.35, "contrast": 10.0, "saturation": 5.0},
                "render_preview": True,
            },
            SessionEnvelope,
        )
        adjusted = _require_session(applied)
        assert adjusted.history_length == 2
        assert adjusted.history_index == 1
        assert adjusted.adjustments.exposure == 0.35
        assert adjusted.adjustments.contrast == 10.0
        assert adjusted.adjustments.saturation == 5.0
        _, adjusted_digest = _preview_digest(
            _workspace_artifact(adjusted.preview_path, workspace_root)
        )
        assert adjusted_digest != initial_digest

        rerendered = await _call_tool(
            session,
            "render_preview",
            {"session_id": initial.session_id, "preview_max_size": 640},
            PreviewResult,
        )
        assert rerendered.ok
        assert rerendered.error is None
        assert rerendered.preview_path is not None
        _, rerendered_digest = _preview_digest(
            _workspace_artifact(rerendered.preview_path, workspace_root)
        )
        assert rerendered_digest == adjusted_digest

        undone = await _call_tool(
            session,
            "undo_adjustment",
            {"session_id": initial.session_id, "render_preview": True},
            SessionEnvelope,
        )
        restored = _require_session(undone)
        assert restored.history_index == 0
        _, restored_digest = _preview_digest(
            _workspace_artifact(restored.preview_path, workspace_root)
        )
        assert restored_digest == initial_digest

        redone = await _call_tool(
            session,
            "redo_adjustment",
            {"session_id": initial.session_id, "render_preview": True},
            SessionEnvelope,
        )
        redone_session = _require_session(redone)
        assert redone_session.history_index == 1
        _, redone_digest = _preview_digest(
            _workspace_artifact(redone_session.preview_path, workspace_root)
        )
        assert redone_digest == adjusted_digest

        export_path = tmp_path / "export.jpg"
        exported = await _call_tool(
            session,
            "export_image",
            {"session_id": initial.session_id, "output_path": str(export_path)},
            ExportResult,
        )
        assert exported.ok
        assert exported.error is None
        assert exported.backend == "mcp-photo-edit-rawtherapee"
        assert exported.output_path == str(export_path.resolve())
        export_size, _ = _preview_digest(export_path)
        assert max(export_size) > 640

        reset = await _call_tool(
            session,
            "reset_adjustments",
            {
                "session_id": initial.session_id,
                "fields": ["exposure", "contrast", "saturation"],
                "render_preview": False,
            },
            SessionEnvelope,
        )
        reset_session = _require_session(reset)
        assert reset_session.adjustments.exposure == 0.0
        assert reset_session.adjustments.contrast == 0.0
        assert reset_session.adjustments.saturation == 0.0

        missing = await _call_tool(
            session,
            "create_edit_session",
            {"input_path": str(tmp_path / "missing.nef")},
            SessionEnvelope,
        )
        assert not missing.ok
        assert missing.error is not None
        assert missing.error.code == "validation_error"


async def _call_tool[ModelT: BaseModel](
    session: ClientSession,
    name: str,
    arguments: dict[str, object] | None,
    result_type: type[ModelT],
) -> ModelT:
    result = await session.call_tool(name, arguments)
    assert not result.isError
    assert result.structuredContent is not None
    return result_type.model_validate(result.structuredContent)


def _require_session(envelope: SessionEnvelope) -> SessionState:
    assert envelope.ok
    assert envelope.error is None
    assert envelope.session is not None
    return envelope.session


def _workspace_artifact(path_text: str, workspace_root: Path) -> Path:
    artifact = Path(path_text).resolve()
    assert artifact.is_file()
    assert artifact.is_relative_to(workspace_root.resolve())
    return artifact


def _preview_digest(path: Path) -> tuple[tuple[int, int], str]:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        digest = hashlib.sha256(rgb.tobytes()).hexdigest()
        return rgb.size, digest
