# AGENTS.md

This file is a fast handoff for future work on `mcp-photo-edit`.

## What This Project Is

- MCP server for agent-driven photo editing
- Public package / module: `mcp_photo_edit`
- Public CLI entrypoint: `mcp-photo-edit`
- Current backend: `LocalFileBackend` calling `raw-edit-service` in-process
- Repo also ships a reusable skill at `skills/mcp-photo-edit`

## Backend Status

- RawTherapee is the supported backend.
- The legacy `darktable-cli` backend is not stable and is expected to be removed.
- Public docs and user guidance should be RawTherapee-first.
- Do not add new public darktable setup instructions.

## Current User-Facing Workflow

1. `create_edit_session`
2. `get_edit_session`
3. `apply_adjustments`
4. `render_preview`
5. `reset_adjustments`
6. `undo_adjustment`
7. `redo_adjustment`
8. `export_image`
9. `list_supported_adjustments`

Sessions are stateful and workspace-backed. The public API is adjustment-based, not sidecar-based. Preview renders are preserved as numbered artifacts, and session-bearing responses return the latest `preview_path` plus `preview_history`. `render_preview` also returns an explicit `preview_count`.

## Current Adjustment Set

- `exposure`
- `contrast`
- `saturation`
- `rgb_mixer`
- `denoise_luma`
- `denoise_detail`
- `denoise_chroma`
- `color_temperature`
- `green_balance`
- `highlights`
- `shadows`
- `sharpen_amount`
- `sharpen_radius`
- `sharpen_contrast`
- `orientation`
- `crop`

`crop` uses normalized `0..1` coordinates.
`orientation` uses quarter turns: `-90`, `0`, `90`, `180`.

## Key Implementation Files

- `src/mcp_photo_edit/server.py`: FastMCP tool registration
- `src/mcp_photo_edit/backend.py`: LocalFileBackend and service adapter
- `src/mcp_photo_edit/interfaces.py`: typed EditBackend contracts
- `src/mcp_photo_edit/session.py`: session lifecycle and persistence
- `src/mcp_photo_edit/models.py`: schemas and validation

## Important Implementation Notes

- Sessions persist an internal renderer-neutral `state_path`.
- RawTherapee implementation details belong to `raw-edit-service`.
- Preview rendering and final export are separate operations.
- Crop math must use the full developed image dimensions as the canonical base, not the dimensions of an already-cropped preview.
- `exiftool` is used when available as a metadata fallback, but the authoritative geometry base should come from real rendered dimensions when needed.

## Config And Compatibility

Preferred env vars:

- `MCP_PHOTO_EDIT_WORKDIR`
- `MCP_PHOTO_EDIT_BACKEND`

Backward-compatible env-var fallbacks still exist in code:

- `MCP_DARKTABLE_WORKDIR`
- `MCP_DARKTABLE_BACKEND`

These fallbacks are compatibility-only. Avoid introducing new docs or features around the old names.

## Verification Commands

Install dev dependencies:

```bash
uv sync
```

Run tests:

```bash
uv run pytest
```

Compile check:

```bash
uv run python -m compileall src
```

## Documentation Rules

- Keep public docs free of machine-specific anecdotes and local sample-file references.
- Keep public docs free of deprecated darktable setup guidance.
- If mentioning darktable at all, describe it only as unstable legacy code slated for removal.
- Treat `README.md`, `DESIGN.md`, and `skills/mcp-photo-edit/SKILL.md` as the public source of truth.

## Good Next Areas

- remove the legacy darktable code path entirely
- expand supported adjustments beyond the current MVP set
- improve preview performance and preview/export parity
- add more metadata and histogram inspection helpers
