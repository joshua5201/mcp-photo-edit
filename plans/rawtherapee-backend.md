# RawTherapee Backend Implementation Plan

Current baseline: `7cdfac3`

## Objective

Add RawTherapee as a supported rendering backend for `mcp-darktable`, using a deterministic session-owned `PP3` file plus an ephemeral preview overlay profile.

This plan keeps the public MCP contract stable:

- session-based workflow remains unchanged
- the public adjustment schema remains backend-agnostic
- backend-specific sidecar formats stay internal

## Why RawTherapee Is Worth Trying

- `rawtherapee-cli` successfully processed the sample Nikon Z6II NEF files in `.codex/raw-z62`.
- A minimal hand-written `PP3` with only `[Exposure] Compensation=1` changed the rendered output, so partial profiles work in practice.
- `PP3` is a plain INI-style text format and is materially easier to generate and patch than darktable history XMP.
- RawTherapee explicitly supports layered processing profiles through repeated `-p` arguments, which matches the desired `session.pp3 + preview.pp3` model.

## Scope

### In scope

- Add a backend abstraction
- Implement a RawTherapee backend
- Store one canonical `session.pp3` per session
- Generate one temporary `preview.pp3` per preview render
- Preserve the existing MCP tool surface
- Keep darktable backend available during transition

### Out of scope

- Removing the darktable backend immediately
- Reworking the public API around RawTherapee-specific terms
- Supporting every RawTherapee control in the first pass
- Replacing the current project name right now

## Design Decisions

### 1. Backend abstraction

Introduce a renderer/backend interface so session logic no longer depends on darktable-specific sidecars.

Expected responsibilities:

- report backend availability and version
- declare supported source formats if possible
- initialize backend-specific session artifacts
- render preview
- export final image
- translate public adjustments into backend-side state

Suggested shape:

- `BackendId`: `darktable`, `rawtherapee`
- `RenderBackend` protocol / abstract base
- `DarktableBackend`
- `RawTherapeeBackend`

The MCP layer should only depend on the session/domain layer, never directly on `darktable-cli` or `rawtherapee-cli`.

### 2. Session-owned backend files

Each session should have a backend workspace under the existing session directory.

For RawTherapee:

- `session.pp3`: canonical session edit state
- `preview.pp3`: generated per preview render, disposable
- `preview.jpg`: latest preview output
- `export.<ext>`: final export output
- `manifest.json`: backend id, source path, current adjustments, generated file paths, timestamps

Rules:

- never write `.pp3` next to the source photo
- never depend on user-side sidecars
- never use `-d` or `-s` for deterministic MCP renders

### 3. Two-profile preview strategy

Use a stable base profile plus a use-once overlay:

- `session.pp3` contains canonical edit intent
- `preview.pp3` contains preview-only overrides

Preview command model:

- `rawtherapee-cli -o <preview-output> -Y -p <session.pp3> -p <preview.pp3> -c <input>`

Final export command model:

- `rawtherapee-cli -o <final-output> -Y -p <session.pp3> -c <input>`

`preview.pp3` should only override performance/output concerns:

- resize
- JPEG quality
- possibly preview-safe fast export toggles

It should not contain user edit intent such as exposure, crop, or color adjustments.

### 4. Deterministic render policy

The backend must be deterministic across machines as much as possible.

Required rules:

- do not use RawTherapee default profiles through `-d`
- do not use source-adjacent sidecars through `-s`
- generate all session state internally
- record backend name and CLI version in session metadata

This matters because RawTherapee default raw profiles can change by version, and relying on them would make MCP outputs drift.

### 5. Public adjustment model remains stable

Keep the current external schema and map it internally to RawTherapee terms.

Initial target mapping:

- `exposure` -> `[Exposure] Compensation`
- `contrast` -> `[Exposure] Contrast` or a better-matched stable control if testing shows another block is closer
- `saturation` -> `[Exposure] Saturation` or a dedicated color tool if that is directionally better
- `crop` -> `[Crop] ...`
- `orientation` / `rotation` -> RawTherapee geometry tool once field semantics are verified

The exact field selection should be validated with hand-generated or GUI-generated `PP3` samples before finalizing all mappings.

## Implementation Phases

## Phase 1. Backend foundation

- [ ] Add a backend interface in `src/mcp_darktable`
- [ ] Move render/export responsibilities behind the backend interface
- [ ] Add backend selection through config or environment variable
- [ ] Default to the current darktable backend until RawTherapee passes feature parity for the MVP set
- [ ] Record backend id in session manifests and tool responses

Acceptance:

- session creation still works with the current darktable backend
- no public MCP schema changes required

## Phase 2. RawTherapee CLI integration

- [ ] Add CLI discovery for `rawtherapee-cli`
- [ ] Capture backend version info from `rawtherapee-cli -v`
- [ ] Implement command construction for preview and export
- [ ] Normalize process errors into existing structured error types
- [ ] Add explicit error messaging for missing backend binary

Acceptance:

- a Z6II NEF can be exported through RawTherapee backend
- a JPEG can be exported through RawTherapee backend

## Phase 3. `PP3` model and generator

- [ ] Add a `PP3` writer/serializer module
- [ ] Define a minimal canonical section/key model for the supported adjustments
- [ ] Generate `session.pp3` from session adjustment state
- [ ] Generate `preview.pp3` overlays for preview renders
- [ ] Keep output deterministic and text-diff-friendly

Implementation note:

- start with minimal partial profiles, not full copied defaults
- only emit sections and keys required for the supported adjustments plus preview overrides

Acceptance:

- `session.pp3` is valid for exposure-only edits
- `preview.pp3` can be layered on top without mutating session state

## Phase 4. Adjustment mapping validation

- [ ] Validate exposure mapping against real renders
- [ ] Validate contrast mapping against real renders
- [ ] Validate saturation mapping against real renders
- [ ] Validate crop mapping against real renders
- [ ] Validate orientation/rotation mapping against real renders

Method:

- generate small targeted `PP3` fixtures
- compare baseline vs edited render outputs
- keep only controls that are visually stable and directionally correct

Important:

- do not assume field semantics from names alone for geometry controls
- verify crop and orientation with actual rendered outputs

Acceptance:

- each supported adjustment has at least one test proving it changes output in the expected direction

## Phase 5. Preview pipeline

- [ ] Decide whether preview sizing lives in `preview.pp3`, post-process downscaling, or both
- [ ] Add preview-specific JPEG quality controls
- [ ] Ensure preview renders are materially faster than final export
- [ ] Preserve consistent appearance between preview and final export, aside from size/compression differences

Preferred order:

1. try `preview.pp3` resize controls if stable
2. if resize control is awkward or incomplete, export then downscale in a post-process step

Acceptance:

- preview generation is faster than final export on the sample NEFs
- preview and final export remain visually consistent

## Phase 6. Session integration

- [ ] Update session manager to route sidecar/profile generation to the selected backend
- [ ] Keep current session ids and public workflow unchanged
- [ ] Ensure reset behavior regenerates `session.pp3` from normalized adjustment defaults
- [ ] Ensure export does not reuse preview-only settings

Acceptance:

- `create_edit_session`, `get_edit_session`, `apply_adjustments`, `reset_adjustments`, and `export_image` work through the RawTherapee backend

## Phase 7. Tests

- [ ] Add unit tests for `PP3` serialization
- [ ] Add unit tests for preview overlay generation
- [ ] Add backend selection tests
- [ ] Add integration tests for RawTherapee CLI if available in environment
- [ ] Add fixture-based tests for supported adjustments

Recommended fixtures:

- one JPEG input
- one supported NEF from `.codex/raw-z62`

Acceptance:

- RawTherapee-specific tests pass when `rawtherapee-cli` is installed
- darktable tests continue to pass

## Phase 8. Rollout strategy

- [ ] Land RawTherapee behind an explicit backend switch first
- [ ] Compare preview and export reliability against darktable on the same images
- [ ] If RawTherapee proves better for the supported adjustment set, make it the default backend
- [ ] Keep darktable as an optional backend until there is enough confidence to remove it

## Risks

### 1. Preview resizing may not be as ergonomic as darktable

RawTherapee CLI lacks direct `--width/--height` flags. Preview optimization may need:

- a resize block in `preview.pp3`
- or a post-export downscale step

This is manageable, but it must be validated early.

### 2. Some adjustment fields may not match intuitive MCP semantics

Even though `PP3` is readable, some controls may not map cleanly to user-facing concepts. Geometry and white balance need verification before they are exposed or migrated.

### 3. Version drift still exists

RawTherapee profiles evolve over time. It is better than darktable XMP for authoring, but not a forever-stable public spec. Session metadata should record CLI version.

### 4. Default profile behavior can introduce hidden variability

This is why the backend must not use `-d` or user-side defaults.

## Recommended First Execution Slice

Implement the smallest vertical slice first:

- [ ] backend abstraction
- [ ] RawTherapee backend discovery
- [ ] `session.pp3` generation for `exposure`
- [ ] `preview.pp3` generation for lower JPEG quality only
- [ ] preview and final export commands
- [ ] one end-to-end integration test on `.codex/raw-z62/DSC_9574.NEF`

Reason:

- exposure is already validated by a real local `PP3` experiment
- this proves the backend contract without committing yet to crop or rotation semantics

## Recommended Second Slice

- [ ] add `contrast`
- [ ] add `saturation`
- [ ] validate preview resizing approach
- [ ] update docs to describe backend selection and requirements

## Recommended Third Slice

- [ ] add crop
- [ ] add orientation / rotation
- [ ] decide whether darktable remains a fallback or is deprecated for the MVP

## Success Criteria

The RawTherapee backend is ready for broader use when all of the following are true:

- a supported NEF can complete session -> preview -> export end to end
- `session.pp3` is generated deterministically and lives only in session workspace
- preview uses an ephemeral overlay profile or equivalent isolated preview settings
- exposure, contrast, saturation, and at least one geometry control work reliably
- the preview image is visibly consistent with the final export
- the darktable backend can remain available without code duplication at the MCP layer
