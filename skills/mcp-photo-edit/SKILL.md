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
2. Inspect the returned preview image, `preview_count`, current state, and history cursor fields such as `history_index`, `history_length`, `can_undo`, and `can_redo`.
3. Use `list_supported_adjustments` if ranges or semantics are unclear.
4. Apply small patches with `apply_adjustments`.
5. Use `undo_adjustment` or `redo_adjustment` to move across committed edit steps when needed.
6. Re-check the preview after each patch.
7. Use `render_preview` whenever you want a fresh preview artifact for the current session state.
8. If operating in **Interactive Mode**, ask the user for confirmation before exporting. Otherwise, call `export_image` only when the preview matches the requested criteria.

## Interactive Mode

- If the user requests "interactive mode", you MUST NOT automatically call `export_image`.
- Once you believe the edits are complete based on the preview, stop and ask the user for confirmation (e.g., using the `ask_user` tool or simply asking in the chat).
- Only call `export_image` after the user has explicitly confirmed the preview is satisfactory.

## Preview History

- Every preview render is preserved as a numbered artifact.
- `preview_path` always points at the latest preview.
- `preview_count` tells you how many preview artifacts exist for the session.

## Undo / Redo

- Semantic edit history is tracked separately from preview history.
- `history_index` points to the current committed edit step.
- `can_undo` and `can_redo` indicate whether cursor movement is available.
- Applying a new edit after undo truncates the redo branch.

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
- The legacy `darktable-cli` backend has been removed.
