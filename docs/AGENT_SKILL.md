# Agent Usage Guide

Use this MCP as an iterative editor, not as a one-shot prompt sink.

Project name:

- `mcp-photo-edit`
- Python module: `mcp_photo_edit`
- Reusable skill path: `skills/mcp-photo-edit`

## Recommended Flow

1. Call `create_edit_session` with the source image path.
2. Inspect the returned preview image and current adjustments.
3. Call `list_supported_adjustments` if you need ranges or semantics.
4. Apply a small patch with `apply_adjustments`.
5. Re-check the preview and continue iterating.
6. Use `render_preview` with `mode="baseline"` if you want to see the original image without any edits.
7. Use `render_preview` with `mode="rawtherapee_default"` to see the image with the user's default RawTherapee profile.
8. Call `export_image` only when the preview looks correct.

## Preview Modes

The `render_preview` tool supports several modes:

- `current` (default): Renders using the current session adjustments.
- `baseline`: Renders the original source image without any session edits.
- `rawtherapee_default`: Renders using the local user's configured default RawTherapee profile. This mode is non-deterministic as it depends on machine-specific configuration.

## Good Practices

- Prefer small, incremental changes over large blind jumps.
- Use `crop` values in normalized `0..1` coordinates.
- Use `orientation` with quarter turns: `-90`, `0`, `90`, `180`.
- Keep export separate from preview generation.
- If a value is rejected, read the returned `hint` and retry with a bounded value.

## Example Adjustment Patch

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

## Prompt Pattern

Use prompts that separate intent from mechanics. For example:

> Create an edit session for `/photos/portrait.nef`. Make the face brighter, keep highlight detail in the sky, and give me a clean preview before exporting.
