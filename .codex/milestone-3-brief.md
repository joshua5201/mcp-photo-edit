# Milestone 3 Brief: Dashboard Readability

## Objective

Improve the diagnostic dashboard so it is easier for a vision model to read reliably.

This milestone is about presentation clarity:

- clearer panel hierarchy
- larger and more purposeful labels
- cleaner separation between image-driven patterns and text-driven facts
- less visual density and ambiguity

This is not the milestone for new diagnostic semantics or prompt rewrites.

## Scope

Required outcomes:

- keep the dashboard as a separate artifact from `preview_path`
- improve readability without regressing Milestone 2 truthfulness
- make the dashboard easier to parse visually as a small number of major panels
- make the text summary easier to consume quickly
- keep `diagnostic_summary` as the exact machine-readable source of facts

Preferred dashboard structure:

- one main histogram panel
- one explicit text summary panel
- one or two supporting metric panels at most

What to improve:

- panel titles
- legends or labels where they remove ambiguity
- spacing and grouping
- text sizing
- visual emphasis for the most important values
- reduction of unnecessary decorative or low-signal elements

Out of scope:

- new diagnostic categories that change milestone semantics substantially
- prompt / skill changes
- merged preview-plus-dashboard composite
- fake vectorscope or fake S-curve

## Expected behavior

The dashboard should let a reviewer quickly answer:

- Is the image clipped in shadows or highlights?
- Is the image overall warm, cool, or neutral?
- Is there a green or magenta bias?
- Is saturation restrained or extreme?

The dashboard image should support quick pattern reading.
The JSON summary should remain the exact source of numeric values.

## Constraints

- Do not regress the truthful diagnostics already implemented in Milestone 2.
- Do not remove fail-open behavior.
- Do not break disabled-mode behavior.
- Do not make the dashboard denser just to add more information.
- Prefer fewer, clearer panels over broader visual coverage.
- Work in this branch only: `feat/advanced-image-info`

## Likely code surface

- `src/mcp_photo_edit/render.py`
- `tests/test_render.py`
- `tests/test_session.py`

## Review target

The milestone passes when a reviewer can verify:

- the dashboard is easier to parse at a glance than the Milestone 2 version
- the major signals are visually obvious
- the image and JSON roles are still cleanly separated
- the layout looks intentional rather than crowded
