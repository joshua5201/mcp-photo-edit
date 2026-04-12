# AGENTS.md

This file is a fast handoff for future work on `mcp-photo-edit`.

## What This Project Is

- MCP server for agent-driven photo editing
- Public package / module: `mcp_photo_edit`
- Public CLI entrypoint: `mcp-photo-edit`
- Current supported backend: RawTherapee via `rawtherapee-cli`

## Backend Status

- RawTherapee is the supported backend.
- The legacy `darktable-cli` backend is not stable and is expected to be removed.
- Public docs and user guidance should be RawTherapee-first.
- Do not add new public darktable setup instructions.

## Current User-Facing Workflow

1. `create_edit_session`
2. `get_edit_session`
3. `apply_adjustments`
4. `reset_adjustments`
5. `export_image`
6. `list_supported_adjustments`

Sessions are stateful and workspace-backed. The public API is adjustment-based, not sidecar-based.

## Current Adjustment Set

- `exposure`
- `contrast`
- `saturation`
- `orientation`
- `crop`

`crop` uses normalized `0..1` coordinates.
`orientation` uses quarter turns: `-90`, `0`, `90`, `180`.

## Key Implementation Files

- `src/mcp_photo_edit/server.py`: FastMCP tool registration
- `src/mcp_photo_edit/session.py`: session lifecycle and persistence
- `src/mcp_photo_edit/render.py`: backend integrations
- `src/mcp_photo_edit/pp3.py`: RawTherapee `PP3` generation
- `src/mcp_photo_edit/models.py`: schemas and validation

## Important Implementation Notes

- Sessions persist a backend-native `state_path`.
- RawTherapee sessions write `session.pp3`.
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
python3 -m pip install -e .[dev]
```

Run tests:

```bash
PYTHONPATH=./.pip-deps:./src python3 -m pytest
```

Compile check:

```bash
python3 -m compileall src
```

## Documentation Rules

- Keep public docs free of machine-specific anecdotes and local sample-file references.
- Keep public docs free of deprecated darktable setup guidance.
- If mentioning darktable at all, describe it only as unstable legacy code slated for removal.
- Treat `README.md`, `DESIGN.md`, and `docs/AGENT_SKILL.md` as the public source of truth.

## Good Next Areas

- remove the legacy darktable code path entirely
- expand supported adjustments beyond the current MVP set
- improve preview performance and preview/export parity
- add more metadata and histogram inspection helpers
