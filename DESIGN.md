# mcp-darktable Design

## Summary

`mcp-darktable` is an MCP server for agent-driven photo editing. The public contract is a stable, structured edit schema and a session-based workflow. The server translates those edits into native darktable XMP sidecars internally and renders them through `darktable-cli`.

The design is intentionally opinionated around agent ergonomics:

- no raw XMP hand-editing in the public API
- no stateless “send file plus edits every turn” workflow
- explicit preview vs export operations
- structured validation and discoverability

## Design Review Feedback

### What was already strong

- The self-feedback loop was the right product shape from the start.
- Using darktable/XMP is pragmatic and keeps implementation leverage high.
- Preview-first iteration matches how agents reason about visual edits.

### Gaps in the original draft and the adopted fixes

- Public API was too coupled to XMP internals.
  Fix: expose a domain-level adjustment schema and keep XMP internal.
- Session lifecycle was missing.
  Fix: use `session_id` and persist state in a managed workspace.
- Edit semantics were underspecified.
  Fix: define bounded ranges, units, and normalized crop coordinates.
- Preview and export behavior were mixed.
  Fix: render previews separately from final export.
- Discoverability and validation were missing.
  Fix: add `list_supported_adjustments` and structured error payloads.

## Goals

- Support end-to-end agent editing on RAW and common raster inputs.
- Keep the public MCP surface simple and stable.
- Preserve original source files.
- Isolate darktable-specific details behind an adapter layer.
- Make the server easy for agents to learn at runtime.

## Non-Goals

- Arbitrary darktable module coverage
- Raw XMP editing as a public interface
- Full photo-editor parity with darktable’s entire module surface
- AI retouching, masks, healing, or object removal
- Multi-user orchestration

## User Workflow

1. Create an edit session from an input image path.
2. Generate a default sidecar and initial preview.
3. Inspect current edit state and preview path.
4. Apply structured adjustments.
5. Re-render the preview.
6. Repeat until the result is acceptable.
7. Export a final image explicitly.

## Public MCP API

### `create_edit_session`

Creates a managed workspace for an input image and renders an initial preview.

Input:

- `input_path`
- optional `preview_max_size`
- optional `session_label`

Output:

- `session_id`
- source file info
- current adjustment state
- preview path
- internal session paths that are safe to expose

### `get_edit_session`

Returns the current state of an existing session.

### `apply_adjustments`

Applies a partial adjustment patch to a session, validates it, writes the sidecar, and optionally re-renders the preview.

### `reset_adjustments`

Resets all or selected adjustment keys back to defaults.

### `export_image`

Exports the current session state to an explicit output path.

### `list_supported_adjustments`

Returns supported keys, ranges, defaults, units, descriptions, and example payloads.

## Adjustment Schema

The public adjustment schema is intentionally narrower than darktable’s full feature set.

Current MVP keys:

- `exposure`
- `contrast`
- `saturation`
- `orientation`
- `crop`

Rules:

- scalar values use bounded ranges
- crop coordinates are normalized to `0..1`
- orientation uses quarter-turn values: `-90`, `0`, `90`, `180`
- preview and export work from the same logical session state

Current implementation note:

The adapter writes native `darktable:*` history entries. The initial MVP only exposes adjustments whose module parameters are practical to encode safely from darktable source. Broader support such as white balance, shadows, highlights, vibrance, or continuous rotation can be added later without changing the session workflow.

## Architecture

### MCP Layer

- registers tools
- validates tool inputs via Pydantic
- shapes structured responses for agent use

### Domain Layer

- session model
- adjustment schema
- validation
- merge and reset behavior

### XMP Adapter Layer

- converts the domain schema into sidecar content
- keeps XMP details out of the public API

### Render Backend Layer

- executes `darktable-cli`
- normalizes preview/export output locations
- isolates backend-specific behavior and errors

## Filesystem And Session Model

Each session has a managed workspace under the configured runtime root.

Session artifacts:

- `session.json`
- `session.xmp`
- `preview.jpg`
- temporary render outputs

Rules:

- source images are never modified
- previews are disposable intermediates
- exports are explicit user-requested outputs
- paths are validated before use

Default work directory:

- `./.mcp-darktable`

This keeps the MVP easy to inspect locally and easy to ignore in git.

## Error Handling

Tools return structured error payloads with:

- `code`
- `message`
- optional `hint`

Primary error categories:

- invalid session
- input file missing
- unsupported adjustment key
- out-of-range adjustment value
- invalid crop geometry
- render backend unavailable
- render failure
- filesystem write failure

## MVP Scope

The current MVP prioritizes:

- session ergonomics
- a small stable edit schema
- real preview/export execution
- safe file handling
- runtime discoverability

This deliberately trades breadth for clarity and implementation reliability.

## Future Improvements

- style presets such as film, portrait, and landscape
- histogram and metadata inspection helpers
- undo / redo and preview history
- compare current preview against prior preview
- copy an edit recipe across multiple images
- export presets such as preview, social, and full-res
- reusable saved edit recipes
- selective batch application
- native support for white balance, highlights, shadows, vibrance, and continuous rotation
