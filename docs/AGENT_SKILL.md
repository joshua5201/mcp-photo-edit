# Agent Usage Guide

Use this MCP as an iterative editor, not as a one-shot prompt sink.

Project naming note:

- Public name: `mcp-photo-edit`
- Current Python module and CLI entrypoint remain `mcp_darktable`

## Recommended Flow

1. Call `create_edit_session` with the source image path.
2. Inspect the returned preview image and current adjustments.
3. Call `list_supported_adjustments` if you need ranges or semantics.
4. Apply a small patch with `apply_adjustments`.
5. Re-check the preview and continue iterating.
6. Call `export_image` only when the preview looks correct.

## Good Practices

- Prefer small, incremental changes over large blind jumps.
- Check `list_supported_adjustments` before assuming geometry or backend-specific controls are available.
- Keep export separate from preview generation.
- If a value is rejected, read the returned `hint` and retry with a bounded value.

## Example Adjustment Patch

```json
{
  "exposure": 0.8,
  "contrast": 12,
  "saturation": 8
}
```

## Prompt Pattern

Use prompts that separate intent from mechanics. For example:

> Create an edit session for `/photos/portrait.nef`. Make the face brighter, keep highlight detail in the sky, and give me a clean preview before exporting.
