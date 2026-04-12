---
name: mcp-photo-edit
description: Use this skill when working with the mcp-photo-edit MCP server for iterative RAW or raster photo editing through RawTherapee.
---

# mcp-photo-edit

Use this skill when an agent should edit photos through the `photo-edit` MCP server instead of trying to describe image edits abstractly without tools.

## When To Use

- The task is about editing a photo through this project.
- The user wants iterative preview / adjust / export behavior.
- The workflow should use the MCP server instead of hand-authoring RawTherapee `PP3`.

## Expected Setup

- The `photo-edit` MCP server is configured in the client.
- `rawtherapee-cli` is installed and available on `PATH`.
- The working directory points at a repo or environment where the source image paths are accessible.

## Recommended Workflow

1. Call `create_edit_session` with the image path.
2. Inspect the returned preview path and current adjustment state.
3. Use `list_supported_adjustments` if ranges or semantics are unclear.
4. Apply small patches with `apply_adjustments`.
5. Re-check the preview after each patch.
6. Call `export_image` only when the preview looks correct.

## Adjustment Notes

- `crop` uses normalized `0..1` coordinates.
- `orientation` uses quarter turns: `-90`, `0`, `90`, `180`.
- Prefer incremental changes instead of large blind jumps.

## Example Patch

```json
{
  "exposure": 0.8,
  "contrast": 12,
  "saturation": 8,
  "orientation": 90,
  "crop": {
    "left": 0.1,
    "top": 0.1,
    "right": 0.9,
    "bottom": 0.95
  }
}
```

## Notes

- This skill assumes RawTherapee is the active backend.
- The legacy `darktable-cli` backend is unstable and slated for removal.
