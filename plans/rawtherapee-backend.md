# RawTherapee Roadmap

This document tracks the forward-looking roadmap for the RawTherapee-backed implementation used by `mcp-photo-edit`.

## Current State

- RawTherapee is the supported backend.
- Session state is stored as session-owned `PP3`.
- Preview and export are both rendered through `rawtherapee-cli`.
- Current adjustment support:
  - `exposure`
  - `contrast`
  - `saturation`
  - `rgb_mixer`
  - `denoise_luma`
  - `denoise_detail`
  - `denoise_chroma`
  - `color_temperature`
  - `green_balance`
  - `highlights`
  - `shadows`
  - `orientation`
  - `crop`

## Near-Term Priorities

- [x] remove the unstable legacy `darktable-cli` backend
- [x] simplify code paths after darktable removal
- [ ] record backend version and render metadata more explicitly in session manifests
- [ ] improve preview performance without changing edit semantics
- [ ] improve preview/export consistency checks

## Adjustment Expansion

- [ ] vibrance
- [ ] continuous rotation if semantics are stable
- [ ] additional tone and color controls that map cleanly to `PP3`

## Session And UX Improvements

- [ ] undo / redo
- [ ] preview history
- [ ] compare current preview against previous preview
- [ ] reusable edit recipes
- [ ] export presets such as preview, social, and full-res
- [ ] copy edits across images

## Reliability Work

- [ ] broaden test coverage for real RawTherapee geometry and crop behavior
- [ ] strengthen validation around unsupported source formats
- [ ] improve structured render failure diagnostics
- [ ] make metadata probing more robust across RAW and raster inputs

## Performance Work

- [ ] evaluate preview-specific `PP3` overlays for resize/output tuning
- [ ] benchmark post-render downscaling versus profile-based preview sizing
- [ ] reduce repeated work during iterative edit loops where safe

## Public Contract Rules

- Keep the MCP API adjustment-based, not sidecar-based.
- Keep `PP3` internal to the backend layer.
- Keep preview and export as separate operations.
- Keep public docs RawTherapee-first.
