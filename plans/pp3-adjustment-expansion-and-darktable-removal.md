# Plan: PP3 Adjustment Expansion and Darktable Removal

## Objective

Expand the RawTherapee-backed adjustment surface by adding the highest-value PP3 parameters next, while removing the legacy darktable code path without removing the pluggable backend boundary.

The requested priority order is:

1. RGB-specific color adjustment
2. denoise
3. manual color temperature
4. white balance
5. highlight / shadow

This plan keeps the public MCP API adjustment-based, keeps `PP3` internal to the backend layer, and treats darktable removal as a structural cleanup milestone that should happen early enough to reduce implementation drag.

## Pre-Flight Analysis

### 1. Core objective

Add a new wave of stable RawTherapee adjustments that are:

- practical to validate with rendered previews and exports
- understandable to agents through `list_supported_adjustments`
- safe to persist in the normalized session state
- not tightly coupled to RawTherapee-only jargon in the public API

In parallel:

- remove the legacy darktable implementation
- keep the render backend interface so future backend swaps remain possible

### 2. Constraints and dependencies

- RawTherapee is the only supported backend going forward.
- Public docs should be RawTherapee-first and should not keep darktable setup guidance.
- The public API must remain adjustment-based, not sidecar-based.
- `session.json` remains the canonical persisted session state.
- `session.pp3` remains the materialized backend state for the current session step.
- Preview and export must stay separate operations.
- Crop geometry rules must not regress.
- Existing environment fallback names can remain for compatibility, but new design work should target `MCP_PHOTO_EDIT_*`.

### 3. Edge cases and handling strategy

- Some PP3 controls behave differently on RAW vs non-RAW inputs.
  Strategy: define clear support rules per adjustment and test both input classes where semantics differ.

- White balance semantics are not one knob.
  Strategy: separate manual temperature controls from preset-style white balance mode selection instead of forcing both into one field.

- RGB-specific color adjustment can mean several different RawTherapee tools.
  Strategy: start with the simplest stable mapping for agents, then add advanced controls later if needed.

- Denoise has many PP3 knobs with interaction effects.
  Strategy: expose a narrow safe subset first and freeze non-user-facing method defaults.

- Highlight handling exists in more than one RawTherapee area.
  Strategy: avoid exposing overlapping tools in the same milestone unless the semantic boundary is explicit.

- Removing darktable can accidentally break tests, aliases, env handling, and error names.
  Strategy: remove the implementation path, then tighten the compatibility surface deliberately rather than piecemeal.

## PP3 Surface Review

The local RawTherapee source under `.codex/RawTherapee` confirms these relevant PP3 groups and keys:

- `Channel Mixer`
  - `Enabled`
  - `Red`
  - `Green`
  - `Blue`
- `RGB Curves`
  - `Enabled`
  - `LumaMode`
  - `rCurve`
  - `gCurve`
  - `bCurve`
- `Directional Pyramid Denoising`
  - `Enabled`
  - `Luma`
  - `Ldetail`
  - `Chroma`
  - plus several advanced method keys
- `White Balance`
  - `Enabled`
  - `Setting`
  - `Temperature`
  - `Green`
  - `Equal`
  - `TemperatureBias`
- `Shadows & Highlights`
  - `Enabled`
  - `Highlights`
  - `HighlightTonalWidth`
  - `Shadows`
  - `ShadowTonalWidth`
  - `Radius`
  - `Lab`
- `Vibrance`
  - `Enabled`
  - `Pastels`
  - `Saturated`
  - `PSThreshold`
  - `ProtectSkins`
  - `AvoidColorShift`

Important interpretation:

- `Channel Mixer` is the most direct PP3-native candidate for RGB-specific adjustment, but it is a full 3x3 matrix and therefore more advanced than a simple per-channel gain control.
- `RGB Curves` exists, but curve serialization is materially more complex than scalar controls and is not a good first expansion target unless the product explicitly wants curve editing.
- `White Balance` supports both manual numeric controls and preset/mode selection.
- `Shadows & Highlights` is a cleaner first target than broader tone-mapping tools.
- `Directional Pyramid Denoising` is feature-rich, but only a subset should be normalized initially.

## Product Decisions Recommended Before Implementation

### RGB-specific adjustment

Recommended first implementation:

- expose simple per-output channel mixer controls backed by `Channel Mixer`

Not recommended for the first pass:

- exposing raw 3x3 matrix rows directly without a helper schema description
- exposing `RGB Curves` first

Reason:

- `Channel Mixer` is easier to explain and test than curve authoring, but still powerful enough to satisfy the request for RGB-specific control.

Recommended public shape:

- either a structured `rgb_mixer` object with red/green/blue output rows
- or a smaller `channel_gains` style API if the team wants a simplified abstraction

Decision to make:

- choose between a full matrix API now, or a simplified per-channel API that later compiles into mixer values

Recommendation:

- use a structured full matrix API in the internal model, but only document simple use patterns in public docs

### Denoise

Recommended first implementation:

- expose the three common denoise dimensions directly

Recommended public shape:

- `denoise_luma`
- `denoise_detail`
- `denoise_chroma`

Keep fixed internally for v1:

- `Method`
- `LMethod`
- `CMethod`
- `C2Method`
- `RGBMethod`
- `MethodMed`
- `Passes`

Reason:

- advanced editors commonly separate luminance noise, color noise, and detail preservation
- the agent benefits from having direct control over these dimensions for more varied edits
- this shape still maps cleanly to RawTherapee while remaining understandable for a future backend

Market check:

- Lightroom uses a primary luminance noise-reduction slider, then advanced detail/contrast controls, plus separate color noise reduction
- Capture One exposes luminance, color, and detail controls
- RawTherapee exposes luma, detail preservation, and chroma-oriented controls through `Directional Pyramid Denoising`

Conclusion:

- multiple denoise dimensions are common enough that they are not just RawTherapee-specific
- keep the three-dimensional denoise surface in the first implementation

### Manual color temperature vs white balance

Recommended split:

- milestone for manual white balance controls:
  - `color_temperature`
  - `tint` or `green_balance`
- do not add backend-specific white balance mode or preset controls in the first plan

Reason:

- manual temperature is a numeric control
- backend-specific white-balance mode labels are less portable than numeric controls
- a future pluggable backend design is better served by simple manual correction parameters

### Highlight / shadow

Recommended first implementation:

- expose:
  - `highlights`
  - `shadows`

Keep fixed internally for v1:

- `HighlightTonalWidth`
- `ShadowTonalWidth`
- `Radius`
- `Lab`

Reason:

- the main utility comes from the two headline sliders
- tonal width and radius are tuning controls better left for a later advanced milestone

## Milestones

## Milestone 0: Backend Cleanup and Interface Preservation

Goal:

- remove all darktable-specific execution and state-writing code
- keep the backend abstraction so RawTherapee remains one implementation of a pluggable interface

Checklist:

- [ ] remove `DarktableBackend` from [render.py](/home/tsn/mcp-darktable/src/mcp_photo_edit/render.py)
- [ ] remove XMP sidecar generation from active session flow
- [ ] remove darktable-specific tests from [test_render.py](/home/tsn/mcp-darktable/tests/test_render.py) and [test_xmp.py](/home/tsn/mcp-darktable/tests/test_xmp.py)
- [ ] remove or archive [xmp.py](/home/tsn/mcp-darktable/src/mcp_photo_edit/xmp.py) if it is no longer referenced
- [ ] simplify backend registry construction to RawTherapee-only while keeping `RenderBackend` and registry builder patterns
- [ ] decide how long alias normalization should keep accepting `darktable` and `darktable-cli`
- [ ] remove `xmp_path` usage from session lifecycle if it becomes dead state
- [ ] update README, DESIGN, and skill docs to state that darktable support is removed, not merely unstable
- [ ] verify no darktable wording remains in public tool errors or class names where it would be user-visible

Notes:

- The backend protocol should remain.
- The registry can still return a single RawTherapee backend for now.
- Compatibility aliases may remain briefly, but they should resolve to a clear validation error, not a hidden legacy path.

## Milestone 1: Adjustment Schema Refactor for Expansion

Goal:

- make the adjustment model ready for nested structured controls rather than only flat scalar fields

Checklist:

- [ ] review whether `AdjustmentState` should remain flat or introduce nested models for grouped adjustments
- [ ] add a consistent naming convention for scalar vs grouped adjustments in [models.py](/home/tsn/mcp-darktable/src/mcp_photo_edit/models.py)
- [ ] update `ADJUSTMENT_SPECS` so future grouped adjustments can still be described cleanly by `list_supported_adjustments`
- [ ] decide reset semantics for grouped fields such as RGB mixer and white balance
- [ ] add schema tests for nested patch / reset behavior
- [ ] ensure session history snapshots remain stable when nested models are added

Recommendation:

- keep simple scalar fields flat where possible
- use nested models only where the PP3 structure is inherently grouped, such as channel mixer rows

## Milestone 2: RGB-Specific Color Adjustment

Goal:

- add the first channel-specific color control backed by `Channel Mixer`

Candidate implementation shape:

- `rgb_mixer.enabled` implicit when any non-default row is set
- `rgb_mixer.red = [r_from_r, r_from_g, r_from_b]`
- `rgb_mixer.green = [g_from_r, g_from_g, g_from_b]`
- `rgb_mixer.blue = [b_from_r, b_from_g, b_from_b]`

Alternative simplified shape:

- `red_gain`
- `green_gain`
- `blue_gain`

Recommended choice:

- implement the full matrix structure if agent ergonomics remain acceptable

Checklist:

- [ ] define the normalized API for RGB-specific adjustment
- [ ] add validation ranges and defaults based on RawTherapee defaults and practical safety bounds
- [ ] map the normalized model into PP3 `Channel Mixer` keys
- [ ] document how defaults translate into neutral color output
- [ ] add PP3 serialization tests for `Channel Mixer`
- [ ] add render tests that verify the generated profile is accepted by `rawtherapee-cli`
- [ ] update `list_supported_adjustments` examples with one realistic RGB adjustment example

Risks:

- a full 3x3 matrix is powerful but can be hard for agents to use well
- simplified gains are easier to use but may not match user expectations for “RGB-specific color adjustment”

## Milestone 3: Denoise MVP

Goal:

- add a stable denoise subset backed by `Directional Pyramid Denoising`

Recommended exposed fields:

- `denoise_luma`
- `denoise_detail`
- `denoise_chroma`

Recommended internal fixed values for first pass:

- `Enabled=true` when any denoise value is non-default
- `Method=Lab`
- preserve one vetted internal default set for the remaining method keys

Recommended mapping strategy:

- map the public fields directly to RawTherapee:
  - `denoise_luma` -> `Luma`
  - `denoise_detail` -> `Ldetail`
  - `denoise_chroma` -> `Chroma`
- keep method-selection fields internal for the first pass

Checklist:

- [ ] add denoise fields and validation ranges to [models.py](/home/tsn/mcp-darktable/src/mcp_photo_edit/models.py)
- [ ] add PP3 generation in [pp3.py](/home/tsn/mcp-darktable/src/mcp_photo_edit/pp3.py) for `Directional Pyramid Denoising`
- [ ] define when the section is omitted versus emitted with zero-like values
- [ ] define default internal method values for the non-exposed denoise keys
- [ ] add tests for neutral denoise, non-neutral denoise, and reset behavior
- [ ] test on both RAW and non-RAW sample inputs
- [ ] document that advanced denoise methods remain internal for now

Risks:

- denoise behavior can depend on image content and file type
- the relationship between noise reduction and detail preservation is content-dependent, so defaults and examples need careful tuning

## Milestone 4: Manual Color Temperature and Tint MVP

Goal:

- add explicit manual white-balance numeric controls with a backend-neutral surface

Recommended exposed fields:

- `color_temperature`
- `tint` or `green_balance`

Optional later:

- `equal`
- `temperature_bias`

Recommended PP3 mapping:

- `White Balance/Enabled=true`
- `White Balance/Setting=Custom` or equivalent verified custom mode
- `White Balance/Temperature`
- `White Balance/Green`

Checklist:

- [ ] confirm the minimum PP3 block needed for custom manual white balance in RawTherapee
- [ ] decide whether the public parameter should be `tint` or the backend-native `green_balance`
- [ ] if `tint` is chosen, define a deterministic conversion layer for RawTherapee `Green`
- [ ] add numeric range validation for temperature and tint / green balance
- [ ] define behavior for non-RAW files where white-balance compatibility rules may differ
- [ ] emit a minimal `White Balance` block for manual controls
- [ ] add PP3 serialization tests for manual WB
- [ ] add golden render checks for warm/cool and green/magenta shifts

Important note:

- this milestone should ship as the complete white-balance MVP unless a future backend-neutral preset abstraction becomes necessary

## Milestone 5: Highlights / Shadows MVP

Goal:

- add simple highlight and shadow recovery backed by `Shadows & Highlights`

Recommended exposed fields:

- `highlights`
- `shadows`

Keep advanced tuning internal:

- `HighlightTonalWidth`
- `ShadowTonalWidth`
- `Radius`
- `Lab`

Checklist:

- [ ] add shadow/highlight fields and ranges to [models.py](/home/tsn/mcp-darktable/src/mcp_photo_edit/models.py)
- [ ] emit a `Shadows & Highlights` block in [pp3.py](/home/tsn/mcp-darktable/src/mcp_photo_edit/pp3.py)
- [ ] decide and document the internal defaults for tonal width, radius, and Lab mode
- [ ] test interactions with exposure and contrast
- [ ] verify that neutral values do not unintentionally alter renders

## Milestone 6: Advanced Color Controls

Goal:

- add second-wave color controls once the first five priorities are stable

Likely candidates:

- `vibrance`
- `highlight_recovery_method` or `highlight_recovery` refinement
- `rgb_curves` if curve authoring becomes a real requirement
- additional white-balance controls such as `equal` and `temperature_bias`
- denoise method-selection controls if advanced tuning becomes necessary

Checklist:

- [ ] evaluate whether `Vibrance` should replace or complement current `saturation`
- [ ] decide whether `HLRecovery` should be exposed separately from `Shadows & Highlights`
- [ ] avoid overlapping controls that confuse agents unless conflict rules are explicit
- [ ] add these only after the simpler scalar MVP controls are validated

## Cross-Cutting Workstreams

### Testing

- [ ] expand [test_pp3.py](/home/tsn/mcp-darktable/tests/test_pp3.py) to cover every new PP3 group
- [ ] expand [test_models.py](/home/tsn/mcp-darktable/tests/test_models.py) for validation boundaries and grouped state behavior
- [ ] update [test_render.py](/home/tsn/mcp-darktable/tests/test_render.py) to validate profile generation with the RawTherapee backend only
- [ ] add integration cases for RAW and non-RAW inputs where WB and denoise semantics may diverge
- [ ] verify reset, undo, redo, and preview rerender behavior for all new fields

### Documentation

- [ ] update [README.md](/home/tsn/mcp-darktable/README.md) with the new adjustment list and examples
- [ ] update [DESIGN.md](/home/tsn/mcp-darktable/DESIGN.md) so the supported adjustment contract matches implementation
- [ ] update [SKILL.md](/home/tsn/mcp-darktable/skills/mcp-photo-edit/SKILL.md) with new tool guidance and example patches
- [ ] document grouped-adjustment payload shapes clearly if RGB mixer ships as a nested object

### Session and API compatibility

- [ ] ensure `list_supported_adjustments` remains readable even with grouped controls
- [ ] verify `reset_adjustments(fields=...)` works for newly added grouped fields
- [ ] confirm history snapshots remain deterministic and JSON-stable
- [ ] keep backward-compatible env-var fallbacks only where they still add value

## Recommended Delivery Order

Recommended execution order:

1. Milestone 0: remove darktable path, keep pluggable backend boundary
2. Milestone 1: make the adjustment schema ready for expansion
3. Milestone 2: RGB-specific adjustment
4. Milestone 3: denoise
5. Milestone 4: manual color temperature and tint
6. Milestone 5: highlights / shadows
7. Milestone 6: advanced color controls

Reasoning:

- removing darktable first reduces split-path complexity
- RGB and denoise are the highest product priorities
- manual temperature is simpler and more backend-neutral than preset-style white-balance modes
- highlights/shadows should come after the color and denoise expansion unless you want a simpler scalar milestone earlier

## Open Decisions

- [ ] decide whether RGB-specific control means full channel mixer or simplified channel gains
- [ ] decide whether manual white balance uses `green_balance` or a more user-friendly `tint` abstraction
- [ ] decide denoise validation ranges that are broad enough for real use but not so broad that agents produce destructive defaults
- [ ] decide whether `saturation` and future `vibrance` should coexist publicly
- [ ] decide whether old darktable backend aliases should error immediately or remain as deprecated config aliases for one release
- [ ] decide whether manual white-balance controls should be supported identically on non-RAW files in the first pass

## Suggested Success Criteria

- each new adjustment can be expressed cleanly in `AdjustmentPatch`
- each new adjustment round-trips through session history without ambiguity
- PP3 generation stays minimal and deterministic
- `rawtherapee-cli` accepts generated profiles without requiring user-facing PP3 knowledge
- all darktable execution paths are removed, but the backend boundary remains reusable

## Source Notes

This plan is based on the current repo architecture plus RawTherapee source and bundled profiles in the local clone under `.codex/RawTherapee`, especially:

- `rtengine/procparams.h`
- `rtengine/procparams.cc`
- `rtdata/profiles/*.pp3`

Those files confirm the PP3 group and key names used above and are the right source of truth for implementation follow-up.
