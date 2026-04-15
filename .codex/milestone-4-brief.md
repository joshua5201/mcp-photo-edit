# Milestone 4 Brief: Prompt And Skill Behavior

## Objective

Make the agent actually use the new advanced image info in the intended editing order.

This milestone is about behavior guidance:

- update the reusable skill and any closely related agent-facing guidance
- define how preview image, diagnostic dashboard, diagnostic summary, and current adjustment state should be used together
- keep behavior sensible when advanced image info is disabled

This is not the milestone for adding new diagnostics or changing the render pipeline.

## Scope

Required outcomes:

- the skill no longer treats `preview_path` as the only truth source
- the skill tells agents to use `diagnostic_dashboard_path` and `diagnostic_summary` when available
- the skill defines a clear editing order
- the skill includes guardrails against simplistic or overly technical edits
- disabled advanced-image-info mode remains a first-class workflow

Expected guidance:

- judge composition first
- correct white balance before pushing contrast or saturation
- use clipping and histogram signals for exposure / highlight / shadow decisions
- use RGB balance and summary hints for color cast decisions
- increase saturation only after tone and balance are stable
- apply sharpening and denoise late

Guardrails to preserve:

- do not force all images toward technical neutrality
- do not chase a perfectly centered histogram
- preserve scene intent for low-key, high-key, warm, cool, or stylized images
- if dashboard and preview disagree, favor preview for aesthetic intent and summary JSON for hard facts

## Disabled-mode behavior

The guidance must still make sense when advanced image info is disabled.

That means:

- use dashboard and summary when available
- fall back to preview-first reasoning when they are not available
- do not assume the advanced fields always exist

## Likely code surface

- `skills/mcp-photo-edit/SKILL.md`
- possibly `README.md` only if a small user-facing guidance update is clearly warranted

## Constraints

- Do not rewrite public docs broadly unless needed.
- Do not change core server code in this milestone unless a very small wording or response-shape note is unavoidable.
- Keep the skill concise and actionable.
- Work in this branch only: `feat/advanced-image-info`

## Review target

The milestone passes when a reviewer can verify:

- the skill tells agents how to use advanced image info rather than merely mentioning it
- the editing order is clear and professional
- the guidance remains useful in both enabled and disabled modes
