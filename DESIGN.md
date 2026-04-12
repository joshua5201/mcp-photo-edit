# mcp-photo-edit Design

## Summary

`mcp-photo-edit` is an MCP server for agent-driven photo editing. The public contract is a stable, structured edit schema and a session-based workflow. Internally the server maps that schema into RawTherapee `PP3` state and renders previews / exports through `rawtherapee-cli`.

Current backend policy:

- RawTherapee is the supported backend.
- The legacy `darktable-cli` backend is not stable and is planned for removal.

The design is intentionally opinionated around agent ergonomics:

- no raw XMP hand-editing in the public API
- no stateless “send file plus edits every turn” workflow
- explicit preview vs export operations
- structured validation and discoverability

## Design Review Feedback

### What was already strong

- The self-feedback loop was the right product shape from the start.
- Using a mature external RAW processor is pragmatic and keeps implementation leverage high.
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
- Isolate RawTherapee-specific details behind an adapter layer.
- Make the server easy for agents to learn at runtime.

## Non-Goals

- Arbitrary RawTherapee control coverage
- Raw `PP3` editing as a public interface
- Full photo-editor parity with RawTherapee’s entire control surface
- AI retouching, masks, healing, or object removal
- Multi-user orchestration

## User Workflow

1. Create an edit session from an input image path.
2. Generate a canonical `session.pp3` and an initial preview artifact.
3. Inspect current edit state, preview path, preview count, and history cursor state.
4. Apply structured adjustments.
5. Move backward or forward with undo / redo when needed.
6. Re-render the preview when you want a fresh artifact for the current step.
7. Repeat until the result is acceptable.
8. Export a final image explicitly.

## Public MCP API

### `create_edit_session`

Creates a managed workspace for an input image and renders an initial preview artifact.

Input:

- `input_path`
- optional `preview_max_size`
- optional `session_label`

Output:

- `session_id`
- source file info
- current adjustment state
- preview path
- preview count
- preview history
- internal session paths that are safe to expose

The initial preview is stored as the first numbered artifact, and later preview renders append additional artifacts without overwriting older files.

The initial session also creates the first semantic history step.

### `render_preview`

Regenerates the current session preview and appends a new preview artifact to the session history.

Output:

- latest preview path
- preview count
- preview history
- history cursor metadata

### `get_edit_session`

Returns the current state of an existing session.

### `apply_adjustments`

Applies a partial adjustment patch to a session, validates it, writes the sidecar, and optionally re-renders the preview.

### `reset_adjustments`

Resets all or selected adjustment keys back to defaults.

### `export_image`

Exports the current session state to an explicit output path.

### `undo_adjustment`

Moves the session cursor to the previous committed semantic edit state.

### `redo_adjustment`

Moves the session cursor to the next committed semantic edit state.

### `list_supported_adjustments`

Returns supported keys, ranges, defaults, units, descriptions, and example payloads.

## Adjustment Schema

The public adjustment schema is intentionally narrower than RawTherapee’s full feature set.

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
- every preview render is preserved as a numbered artifact

Current implementation note:

The adapter writes native RawTherapee `PP3` settings. The initial MVP only exposes adjustments whose profile parameters are practical to encode safely and validate with real renders. Broader support such as white balance, shadows, highlights, vibrance, or continuous rotation can be added later without changing the session workflow.

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

### Backend State Adapter Layer

- converts the domain schema into backend-native `PP3`
- keeps sidecar details out of the public API

### Render Backend Layer

- executes `rawtherapee-cli`
- normalizes preview/export output locations
- isolates backend-specific behavior and errors

## Filesystem And Session Model

Each session has a managed workspace under the configured runtime root.

Session artifacts:

- `session.json`
- `session.pp3`
- `history/step-0001.pp3`, `history/step-0002.pp3`, ...
- `preview-0001.jpg`, `preview-0002.jpg`, ...
- temporary render outputs

Rules:

- source images are never modified
- `session.json` is the authoritative edit-history timeline
- `history_index` identifies the current semantic edit step
- `session.pp3` is the current materialized backend state
- immutable per-step `PP3` snapshots are preserved under `history/`
- previews are preserved as render-history artifacts
- preview history is separate from semantic edit history
- exports are explicit user-requested outputs
- paths are validated before use

Default work directory:

- `./.mcp-photo-edit`

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

- histogram and metadata inspection helpers
- compare current preview against prior preview
- copy an edit recipe across multiple images
- export presets such as preview, social, and full-res
- reusable saved edit recipes
- selective batch application
- native support for white balance, highlights, shadows, vibrance, and continuous rotation
