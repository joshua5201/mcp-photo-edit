# Plan: RawTherapee Sharpening Support

## Objective

Determine whether sharpening is supported by RawTherapee for this project, and define the safest way to add it to the current adjustment-based MCP API.

Conclusion up front:

- yes, RawTherapee supports sharpening
- no, this repo does not currently expose sharpening
- sharpening should be added, but only one sharpening family should be exposed first to avoid overlapping controls and confusing agent behavior

## Pre-Flight Analysis

### 1. Core objective

Add a useful sharpening adjustment that:

- maps cleanly to RawTherapee `PP3`
- is understandable to agents through `list_supported_adjustments`
- does not create conflicting sharpening paths in the public API
- can be verified with preview and export renders

### 2. Constraints and dependencies

- the public API is adjustment-based, not `PP3`-native
- the backend layer should remain pluggable
- the current repo already exposes tone, denoise, white balance, channel mix, and highlights/shadows
- sharpening should not force users to understand all RawTherapee sharpening internals

### 3. Edge cases and handling strategy

- RawTherapee has multiple sharpening modules with different semantics.
  Strategy: expose exactly one sharpening family first.

- Sharpening and denoise interact strongly.
  Strategy: test combined use and avoid overly aggressive defaults.

- Different sharpening stages exist in RawTherapee.
  Strategy: prefer a stage that is stable and general-purpose for both RAW and common raster workflows.

## RawTherapee Findings

Using the local RawTherapee source under `.codex/RawTherapee`, the following sharpening-related PP3 groups are supported:

- `Sharpening`
- `SharpenEdge`
- `SharpenMicro`
- `PostDemosaicSharpening`
- `PostResizeSharpening`

Relevant RawTherapee source locations:

- `rtengine/procparams.h`
- `rtengine/procparams.cc`
- `rtgui/tools/sharpening.cc`
- `rtgui/tools/sharpenedge.cc`
- `rtgui/tools/sharpenmicro.cc`
- `rtgui/tools/pdsharpening.cc`
- `rtgui/tools/prsharpening.cc`

## Sharpening Families

### 1. `Sharpening`

This is the main general sharpening tool.

It supports:

- `Enabled`
- `Method`
- `Radius`
- `Amount`
- `Threshold`
- `Contrast`
- `BlurRadius`
- edge-only options
- halo-control options
- deconvolution-specific options

RawTherapee defaults from source:

- `enabled=false`
- `method="usm"`
- `radius=0.5`
- `amount=200`
- `contrast=20.0`
- `blurradius=0.2`

Interpretation:

- this is the most promising first sharpening target
- it already gives a conventional sharpening model
- it can start in `usm` mode without exposing the full method matrix

### 2. `SharpenEdge`

This is a more specialized edge-sharpening tool.

It supports:

- `Enabled`
- `Passes`
- `Strength`
- `ThreeChannels`

Interpretation:

- useful, but more niche than the main sharpening tool
- better as a later advanced control

### 3. `SharpenMicro`

This is microcontrast-style sharpening.

It supports:

- `Enabled`
- `Matrix`
- `Strength`
- `Contrast`
- `Uniformity`

Interpretation:

- useful as a local-contrast-like texture control
- not the best first sharpening control because users generally expect a more standard sharpening tool first

### 4. `PostDemosaicSharpening`

This is a RAW-stage sharpening path.

Bundled profiles show it enabled in some standard RawTherapee profiles.

Interpretation:

- attractive for RAW quality
- less backend-neutral and less predictable for a simple public API
- not a good first sharpening control for this project

### 5. `PostResizeSharpening`

This is export/resize-stage sharpening.

Interpretation:

- tied to resize/export semantics
- not appropriate for the current edit-session adjustment model as a first sharpening control

## Recommendation

Recommended first implementation:

- expose the main `Sharpening` tool only
- lock the method to `usm` for the first pass
- expose a small set of scalar controls

Recommended public fields:

- `sharpen_amount`
- `sharpen_radius`

Optional first-pass third field:

- `sharpen_contrast`

Do not expose initially:

- `sharpen_method`
- `sharpen_threshold`
- `sharpen_blur_radius`
- `sharpen_edges_only`
- `sharpen_halo_control`
- deconvolution-specific controls
- `SharpenEdge`
- `SharpenMicro`
- `PostDemosaicSharpening`
- `PostResizeSharpening`

Reasoning:

- `amount` and `radius` cover the most common sharpening use case
- `contrast` is still understandable if a third control is wanted
- everything beyond that is either advanced tuning or a different sharpening family

## API Design Recommendation

Preferred first public contract:

- `sharpen_amount`
- `sharpen_radius`

Alternative:

- grouped object `sharpen = { amount, radius, contrast }`

Recommendation:

- keep it flat for the first pass
- this matches the current scalar-heavy API and reduces adjustment discovery complexity

## PP3 Mapping Recommendation

Recommended v1 mapping:

- emit `[Sharpening]` only when any sharpening value is non-default
- write:
  - `Enabled=true`
  - `Method=usm`
  - `Amount=<sharpen_amount>`
  - `Radius=<sharpen_radius>`
- optionally:
  - `Contrast=<sharpen_contrast>`
- keep internal defaults for:
  - `BlurRadius=0.2`
  - `Threshold`
  - `OnlyEdges=false`
  - `HalocontrolEnabled=false`

## Proposed Milestone

### Milestone: Sharpening MVP

Goal:

- add one safe, general-purpose sharpening path backed by RawTherapee `Sharpening`

Checklist:

- [ ] add sharpening fields to `AdjustmentState`, `AdjustmentPatch`, and `ADJUSTMENT_SPECS`
- [ ] choose whether to expose 2 or 3 fields:
  - `sharpen_amount`
  - `sharpen_radius`
  - optional `sharpen_contrast`
- [ ] add PP3 generation for `[Sharpening]`
- [ ] keep `Method=usm` fixed for the first release
- [ ] define omission rules for fully default sharpening
- [ ] update backend `supported_adjustment_names`
- [ ] add unit tests for model validation and PP3 serialization
- [ ] add render-path tests for state writing
- [ ] update README, DESIGN, and skill docs
- [ ] test interaction with denoise and highlights/shadows

## Validation Strategy

- verify sharpening-only patches create the expected `[Sharpening]` PP3 block
- verify default sharpening does not emit unnecessary PP3 sections
- verify partial patches preserve existing sharpening state
- verify reset behavior works field-by-field
- verify combined denoise + sharpening patches behave deterministically

## Open Decisions

- [ ] expose only `amount` and `radius`, or add `contrast` too
- [ ] choose flat fields or a grouped `sharpen` object
- [ ] decide whether future advanced sharpening should extend the same family or add separate families such as `SharpenMicro`

## Recommendation Summary

If you want sharpening now, add it.

But add only the main `Sharpening` tool first, in `usm` mode, with a small scalar API.

That is the most practical fit for the current project architecture and the least likely to create a confusing public contract.
