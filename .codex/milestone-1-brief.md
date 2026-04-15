# Milestone 1 Brief: Artifact Contract

## Objective

Implement Milestone 1 from `.codex/advanced-editing.md` as the first project delivery gate.

This milestone is about the public artifact contract only:

- keep the current preview-first workflow intact
- add optional advanced image info outputs
- gate advanced image info behind `DISABLE_ADVANCED_IMAGE_INFO`
- make enabled and disabled response behavior coherent and reviewable

This is not the milestone for full diagnostic rendering quality. Favor a clean contract over ambitious scope.

## Scope

Required outcomes:

- `preview_path` remains the primary preview artifact
- session-bearing responses can expose `diagnostic_dashboard_path`
- session-bearing responses can expose `diagnostic_summary`
- `render_preview` responses can expose the same advanced image info fields
- `DISABLE_ADVANCED_IMAGE_INFO=true` disables advanced image info cleanly
- disabled mode must not break or degrade the base preview workflow

Out of scope for this milestone:

- high-fidelity histogram / vectorscope correctness
- tone diagnostics sophistication
- prompt / skill prompt rewrite
- evaluation harnesses beyond milestone-level verification

## Expected behavior

Enabled mode:

- advanced image info fields are present in response models
- advanced image info artifacts can be generated and tracked alongside previews

Disabled mode:

- `preview_path`, `preview_history`, and existing preview behavior stay intact
- advanced image info fields should stay stable in shape and return `null` when disabled
- preview rendering must not fail because advanced image info is disabled or unavailable

## Likely code surface

- `src/mcp_photo_edit/models.py`
- `src/mcp_photo_edit/session.py`
- `src/mcp_photo_edit/server.py`
- tests around session envelopes and preview results

## Constraints

- Do not remove or regress existing preview behavior.
- Do not invent S-curve support.
- Do not redesign the whole server surface.
- Respect existing session history and preview history behavior.
- Work in this branch only: `feat/advanced-image-info`

## Review target

The milestone passes when a reviewer can verify:

- the contract is understandable without reading internals
- enabled and disabled modes are both coherent
- clients can rely on stable response shape
- the original preview-first workflow still works
