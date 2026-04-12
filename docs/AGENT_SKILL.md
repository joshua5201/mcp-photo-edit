# Agent Usage Guide

Use this MCP as an iterative editor, not as a one-shot prompt sink.

## Recommended Flow

1. Call `create_edit_session` with the source image path.
2. Inspect the returned preview image and current adjustments.
3. Call `list_supported_adjustments` if you need ranges or semantics.
4. Apply a small patch with `apply_adjustments`.
5. Re-check the preview and continue iterating.
6. Call `export_image` only when the preview looks correct.

## Good Practices

- Prefer small, incremental changes over large blind jumps.
- Use crop values in normalized `0..1` coordinates.
- Use `orientation` with quarter turns: `-90`, `0`, `90`, `180`.
- Keep export separate from preview generation.
- If a value is rejected, read the returned `hint` and retry with a bounded value.

## Example Adjustment Patch

```json
{
  "exposure": 0.8,
  "contrast": 12,
  "saturation": 8,
  "orientation": 0,
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
