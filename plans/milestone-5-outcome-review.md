# Milestone 5 Outcome Review Playbook

## Objective

Create a lightweight, repeatable A/B review workflow that compares advanced image info enabled vs disabled and answers one question: does it improve final editing outcomes enough to justify keeping it on by default?

This playbook is documentation only. It does not add diagnostics, benchmark code, or new editing behavior.

## Scope And Constraints

- Use the current repo workflow and the existing `skills/mcp-photo-edit` guidance.
- Compare the same image, same prompt, and same review procedure with advanced image info enabled and disabled.
- Keep the process human-reviewable and easy to rerun on the current demo assets.
- Do not invent new edit controls or new scoring infrastructure.
- Stay aligned with the current public workflow: `create_edit_session`, `apply_adjustments`, `render_preview`, `export_image`, and the existing session state fields.

## What Reviewers Judge

Review the final output, not the dashboard alone. Advanced image info is a decision aid, so the question is whether the final image is better.

Judge these dimensions on every case:

- White balance: neutral where appropriate, but still faithful to the scene.
- Clipping handling: avoid obvious highlight or shadow damage.
- Contrast restraint: do not over-press flat scenes into fake drama.
- Saturation restraint: do not overcook color.
- Scene intent: preserve the look the image is already trying to express.
- Already-good safety: do not make a solid image worse just because diagnostics are available.

## Case Matrix

Use the closest matching demo image and keep the intent in the prompt stable across enabled and disabled runs.

| Case | Suggested demo asset | What it stresses | What reviewers should look for |
| --- | --- | --- | --- |
| Low-key | `demo/idol_9293.jpg` | Dark tones, restrained light, subtle color | Whether the edit keeps the moody look instead of flattening shadows or pushing saturation |
| High-key | `demo/idol_9377.jpg` or `demo/tennis-free.jpg` | Bright, airy treatment | Whether the edit keeps highlights clean and avoids forcing unnecessary contrast |
| Mixed-light | `demo/tennis.jpg` | Competing color sources and uneven tone | Whether white balance stays controlled without making skin or background look wrong |
| Backlit | `demo/hk.jpg` | Bright signage / strong foreground-background imbalance | Whether the edit holds highlight detail and subject separation without harsh correction |
| Already-good | `demo/japanese_film_style.jpg` | A scene that should mostly be left alone | Whether the edit avoids overworking a visually coherent image |

If a source does not perfectly fit one archetype, keep the target intent in the prompt and treat the archetype as the review lens rather than a strict scene label.

## Prompt And Run Template

Use the same prompt structure for both runs. Only the advanced image info setting changes.

### Base prompt template

```text
Edit <image> for <target intent>. Keep the look faithful to the scene. Use the current photo-edit workflow and stop when the result is clean, balanced, and not over-processed.
```

### Recommended intent phrases

- Low-key: `preserve the moody low-key look while improving technical balance`
- High-key: `keep the image bright, airy, and restrained`
- Mixed-light: `balance the mixed lighting without making the scene look artificial`
- Backlit: `recover the subject while protecting the bright background`
- Already-good: `leave the image natural and avoid unnecessary changes`

### Run template

1. Start one session with advanced image info enabled.
2. Start a second session with advanced image info disabled by setting `DISABLE_ADVANCED_IMAGE_INFO=true`.
3. Use the same source image and the same base prompt in both runs.
4. Keep the same iteration budget for both runs. Three preview cycles is usually enough for a review pass.
5. Record the final `preview_path`, `preview_count`, and the final adjustment state for both runs.
6. Export only after the run looks complete.

## Scoring Rubric

Use a simple 3-point comparison for each case and each dimension:

- `Better`: the enabled run is clearly preferable.
- `Same`: no meaningful difference.
- `Worse`: the enabled run regresses.

Score each case against the disabled run on the six review dimensions above. Keep notes short and concrete.

Recommended note format:

```text
case = mixed-light
wb = better
clipping = same
contrast = better
saturation = same
intent = better
already_good = n/a
comment = less color cast, no extra punch
```

## Review Procedure

1. Review enabled and disabled outputs side by side, but keep the mode labels hidden until scoring is complete if possible.
2. First check for hard failures: obvious color cast, clipped highlights, muddy shadows, or a scene that no longer reads correctly.
3. Then judge restraint: did the run stop before it became too contrasty or too saturated?
4. For already-good images, prefer the version that changed least while still remaining technically sound.
5. Record a short note for any difference that is visible without zooming.
6. Repeat the same procedure across all five case categories.

## Decision Rule

Keep advanced image info enabled by default if both conditions hold:

- It is better or tied on most cases, especially the difficult ones.
- It does not introduce severe regressions on already-good images.

Treat the feature as not ready for default-on if either condition fails:

- It repeatedly over-corrects low-key, high-key, mixed-light, or backlit scenes.
- It makes already-good images look more processed than the disabled run.

For a practical review pass, a simple acceptance rule is:

- Enabled should win or tie on at least 4 of 5 cases overall.
- Enabled should not produce any severe regression on the already-good case.

## Repeatability Notes

- Use the current demo assets in the repo so reviewers do not need special fixtures.
- Use the existing skill prompt instead of hand-authoring backend profiles.
- Keep the comparison focused on final image quality, not on how clever the intermediate diagnostics look.
- If you need to rerun a case, rerun both modes with the same prompt and the same source image.

