# Milestone 2 Brief: Honest Diagnostic Generation

## Objective

Implement the first real advanced image info generation path.

This milestone is about truthfulness, not polish:

- generate advanced image info from the current edited render state
- produce a real `diagnostic_dashboard_path`
- produce a real `diagnostic_summary`
- avoid invented semantics and fake controls

This is not the milestone for prompt integration or dashboard design refinement.

## Scope

Required outcomes:

- when advanced image info is enabled, preview rendering produces a real dashboard artifact
- when advanced image info is enabled, preview rendering produces a real summary payload
- diagnostics must be derived from the current edited image state, not the untouched source file
- history state must remain coherent so undo / redo can restore the active dashboard state consistently
- disabled mode via `DISABLE_ADVANCED_IMAGE_INFO=true` must continue to return stable `null` fields
- existing preview behavior must remain intact

Recommended implementation direction:

- use the current rendered preview image as the analysis source for this milestone
- keep the dashboard simple and honest
- prefer a minimal but real diagnostic set over a broad but misleading one

## Diagnostic scope for this milestone

Implement only diagnostics that are clearly defensible now.

Minimum expected output:

- histogram visualization
- luma / clipping summary values
- RGB balance summary values
- saturation summary values

Dashboard expectations:

- separate image artifact, not merged into `preview_path`
- simple layout
- readable labels
- no fake S-curve

Acceptable tone diagnostics for this milestone:

- clipped black / white percentages
- luma percentile summary
- simple tone summary text or bars

Vectorscope:

- only implement it if it can be done honestly within this milestone
- do not fake a vectorscope panel just to satisfy layout symmetry
- if omitted for this milestone, the dashboard and summary must still remain truthful and useful

## Expected behavior

Enabled mode:

- `diagnostic_dashboard_path` points to a real generated artifact
- `diagnostic_summary` contains real computed values
- diagnostics correspond to the same current render state as `preview_path`

Disabled mode:

- `preview_path` and preview history continue to work exactly as before
- advanced image info fields stay `null`

Failure handling:

- preserve preview-first behavior whenever practical
- prefer failing open to `null` advanced image info instead of breaking preview rendering because of dashboard generation issues

## Likely code surface

- `src/mcp_photo_edit/render.py`
- `src/mcp_photo_edit/session.py`
- `src/mcp_photo_edit/models.py`
- `src/mcp_photo_edit/server.py`
- `tests/test_render.py`
- `tests/test_session.py`
- possibly `tests/test_models.py`

## Constraints

- Do not analyze the untouched source file after edits have been applied.
- Do not invent S-curve support.
- Do not regress `preview_path` behavior.
- If diagnostic fields need to be added to `HistoryStep` for undo / redo correctness, keep them optional so legacy session manifests still load.
- Do not remove the feature gate behavior from Milestone 1.
- Work around existing dirty changes in `src/mcp_photo_edit/render.py` and `tests/test_render.py`; do not revert them.
- Work in this branch only: `feat/advanced-image-info`

## Review target

The milestone passes when a reviewer can verify:

- advanced image info is now real, not just contract placeholders
- generated diagnostics describe the current edited state
- the dashboard is truthful even if it is still visually simple
- disabled mode still preserves the original workflow
