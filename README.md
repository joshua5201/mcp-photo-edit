# mcp-photo-edit

An MCP server for agent-driven photo editing with RawTherapee.

The server exposes a session-based editing workflow instead of raw sidecar manipulation. Agents create an edit session, apply structured adjustments, regenerate previews when needed, and export a final image. Internally the server writes session-owned RawTherapee `PP3` files and renders them through `rawtherapee-cli`.

Each session now also maintains an explicit undo / redo timeline in `session.json`. Semantic edit history is tracked separately from preview-render history.

## Examples

The demo photographs are original work and are not covered by the GPL license. Commercial use is prohibited.

### Example: Fujifilm Style (v0.2.0)

Compare the baseline image with the two Fujifilm-style outputs below. Each thumbnail links to the full-size file. One with [advanced image info](#advanced-image-info) and the other off.

**Prompt:**
> Apply a Fujifilm camera like profile to `demo/cosplay.NEF`. Apply a crop to focus on the center but keep the aspect ratio, export the result as `demo/fujifilm_style.jpg`

| Before | Preview only | With diagnostics |
| :--- | :--- | :--- |
| <a href="demo/cosplay.jpg"><img src="demo/cosplay.jpg" alt="Before" width="240"></a> | <a href="demo/fujifilm_style_pro.jpg"><img src="demo/fujifilm_style_pro.jpg" alt="After with advanced image info disabled" width="240"></a> | <a href="demo/fujifilm_style_advanced_info_pro.jpg"><img src="demo/fujifilm_style_advanced_info_pro.jpg" alt="After with advanced image info enabled" width="240"></a> |

**Model:** gemini-3.1-pro-preview

### Example: CCD Style (v0.2.0)

This example compares [advanced image info](#advanced-image-info)-assisted runs using the same source image, prompt but different models.

**Prompt:**
> Apply a 2000s CCD camera like profile to `demo/cosplay.NEF`. Apply a crop to focus on the center but keep the aspect ratio, export the result as [demo/ccd_style_gpt54_mini_medium.jpg](demo/ccd_style_gpt54_mini_medium.jpg)

Main comparison:

| Baseline | Gemini 3 Flash | Gemini 3.1 Pro | GPT-5.4 Medium | GPT-5.4 Mini |
| :--- | :--- | :--- | :--- | :--- |
| <a href="demo/cosplay.jpg"><img src="demo/cosplay.jpg" alt="Baseline" width="240"></a> | <a href="demo/ccd_style_flash.jpg"><img src="demo/ccd_style_flash.jpg" alt="CCD style by Gemini 3 Flash" width="240"></a> | <a href="demo/ccd_style_pro.jpg"><img src="demo/ccd_style_pro.jpg" alt="CCD style by Gemini 3.1 Pro" width="240"></a> | <a href="demo/ccd_style_gpt54_medium.jpg"><img src="demo/ccd_style_gpt54_medium.jpg" alt="CCD style by GPT-5.4 Medium" width="240"></a> | <a href="demo/ccd_style_gpt54_mini_medium.jpg"><img src="demo/ccd_style_gpt54_mini_medium.jpg" alt="CCD style by GPT-5.4 Mini" width="240"></a> |

**Models:** gemini-3-flash-preview, gemini-3.1-pro-preview, gpt-5.4 (medium), gpt-5.4-mini (medium)

## Status

This is an MVP implementation.

Current focus:

- session-based editing flow
- structured adjustment schema
- `rawtherapee-cli` preview and export
- RAW and common raster inputs when supported by the local RawTherapee build

Not in scope:

- local masks
- healing / AI retouch
- full photo-editor feature coverage
- large preset libraries
- batch editing UX

## Requirements

- Python 3.12+
- `uv` for the easiest local install and run workflow
- `rawtherapee-cli` on `PATH`

### Tested Environment

- **OS:** Ubuntu 24.04 LTS
- **RawTherapee:** v5.10 (CLI)

Install the project with `uv`:

```bash
uv sync
```

For development, include the optional test dependency:

```bash
uv sync --extra dev
```

Verify `rawtherapee-cli`:

```bash
rawtherapee-cli -v
```

## Quickstart

Example stdio configurations

### Codex CLI

Add this block:

```toml
[mcp_servers.photo_edit]
command = "uv"
args = ["run", "mcp-photo-edit"]

[mcp_servers.photo_edit.env]
MCP_PHOTO_EDIT_WORKDIR = "/absolute/path/to/.mcp-photo-edit"
MCP_PHOTO_EDIT_BACKEND = "rawtherapee-cli"
```

If you prefer to add it from the CLI instead of editing TOML manually:

```bash
codex mcp add photo-edit --env MCP_PHOTO_EDIT_WORKDIR=/absolute/path/to/.mcp-photo-edit --env MCP_PHOTO_EDIT_BACKEND=rawtherapee-cli -- uv run mcp-photo-edit
```

Verify the server is registered:

```bash
codex mcp list
```

Project guidance for Codex:

- This repo includes project-scoped guidance in `AGENTS.md`.
- This repo also ships an installable reusable skill at `skills/mcp-photo-edit`.

Install the reusable skill manually by linking or copying it into Codex's skill directory.
`$CODEX_HOME` typically defaults to `~/.codex`.

Link it:

```bash
mkdir -p ~/.codex/skills
ln -s <repo-path>/skills/mcp-photo-edit ~/.codex/skills/mcp-photo-edit
```

Or copy it:

```bash
mkdir -p ~/.codex/skills
cp -R <repo-path>/skills/mcp-photo-edit ~/.codex/skills/mcp-photo-edit
```

Codex CLI does not currently expose a dedicated `skills install` subcommand, so the skill-directory install is the supported path.

Recommended `AGENTS.md` snippet for better tool selection:

```md
Use the `photo-edit` MCP server for photo-editing tasks. Create an edit session first, iterate with previews, and export only when the preview looks correct.
```

### Gemini CLI

Add this block:

```json
{
  "mcpServers": {
    "photo-edit": {
      "command": "uv",
      "args": ["run", "mcp-photo-edit"],
      "env": {
        "MCP_PHOTO_EDIT_WORKDIR": "/absolute/path/to/.mcp-photo-edit",
        "MCP_PHOTO_EDIT_BACKEND": "rawtherapee-cli"
      },
      "timeout": 30000,
      "trust": true
    }
  }
}
```

Or add it from the CLI. This example writes to user config instead of project-local config:

```bash
gemini mcp add --scope user --transport stdio --env MCP_PHOTO_EDIT_WORKDIR=/absolute/path/to/.mcp-photo-edit --env MCP_PHOTO_EDIT_BACKEND=rawtherapee-cli --timeout 30000 --trust photo-edit uv run mcp-photo-edit
```

If you omit `--scope user`, Gemini CLI writes the MCP entry to project-local config by default.

Verify the configuration:

```bash
gemini mcp list
```

If Gemini shows the stdio server as disconnected, trust the current folder first:

```bash
gemini trust
```

Gemini CLI also supports installing the reusable skill bundled with this repo.

Install from a local path:

```bash
gemini skills install <repo-path>/skills/mcp-photo-edit --scope user
```

For active local development, link it instead so updates in the repo are reflected immediately:

```bash
gemini skills link <repo-path>/skills/mcp-photo-edit --scope user
```

Verify the skill is available:

```bash
gemini skills list
```

## Compatibility Note

RAW support depends on the local RawTherapee build and its bundled RAW decoders. A file extension being supported in principle does not guarantee that every camera or compression variant will decode on every machine. When diagnosing unsupported RAW files, check the installed RawTherapee version and the camera / compression mode used by the source file. For reference, this project is primarily developed and tested on the environment described in the [Tested Environment](#tested-environment) section.

**Note on Nikon RAW:** Some compressed Nikon RAW formats (e.g., High Efficiency / HE* compression) may not be supported by the underlying libraries in current RawTherapee builds. If you encounter issues with Nikon files, try using uncompressed RAW or Lossless Compressed modes if available in-camera.

## Advanced Image Info

This project can attach extra diagnostic output to each preview render:

- `preview_path` remains the primary image for aesthetic judgment.
- `diagnostic_dashboard_path` adds a separate technical dashboard image.
- `diagnostic_summary` adds machine-readable stats for exposure, balance, and saturation.
- Set `DISABLE_ADVANCED_IMAGE_INFO=true` to turn the diagnostics off and keep the original preview-first workflow.

When enabled, the dashboard is meant to complement the clean preview rather than replace it.

## Available Tools

- `create_edit_session`
- `get_edit_session`
- `render_preview`
- `apply_adjustments`
- `reset_adjustments`
- `undo_adjustment`
- `redo_adjustment`
- `export_image`
- `list_supported_adjustments`

`render_preview` regenerates the current session preview, appends a new preview artifact, and returns the latest `preview_count`.
`undo_adjustment` and `redo_adjustment` move the session cursor across committed edit states without creating new edit-history entries.

## Typical Agent Workflow

1. Create a session from an input image.
2. Inspect the returned session state, including `preview_path`, `preview_history`, current adjustment state, and history cursor fields such as `history_index`, `history_length`, `can_undo`, and `can_redo`.
3. Apply one or more adjustments.
4. Use `undo_adjustment` or `redo_adjustment` when you need to move across committed edit steps.
5. Re-check the preview by calling `render_preview` whenever you want a fresh preview artifact and an explicit `preview_count` for the current step.
6. Export a final image explicitly.

See [SKILL.md](skills/mcp-photo-edit/SKILL.md) for an agent-facing usage guide.

## Adjustment Model

The public API exposes a stable edit schema. It does not ask clients to hand-author backend profile files.

Current default-backend MVP adjustments:

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
- `sharpen_amount`
- `sharpen_radius`
- `sharpen_contrast`
- `orientation`
- `crop`

Use `list_supported_adjustments` to discover exact ranges, defaults, and example payloads at runtime.

Backend note:

- the current implementation targets RawTherapee `PP3`
- `list_supported_adjustments` is the source of truth for runtime support

## Session History

- `session.json` is the authoritative session timeline.
- `history` stores committed semantic edit steps.
- `history_index` points to the current step.
- `session.pp3` is the current materialized backend state.
- `render_preview` appends preview artifacts but does not append semantic edit history.
- Applying a new edit after undo truncates the redo tail.

## Project Layout

```text
src/mcp_photo_edit/
  models.py        Pydantic schemas and validation
  session.py       Session lifecycle and persistence
  pp3.py           Adjustment to RawTherapee PP3 translation
  render.py        Backend integrations
  server.py        MCP tool registration
tests/
skills/
```

## Development

Install dev dependencies:

```bash
uv sync --extra dev
```

Run tests:

```bash
uv run pytest
```

Start the server over stdio:

```bash
uv run mcp-photo-edit
```


## Disclaimers

- This project invokes `rawtherapee-cli`; it does not embed or redistribute RawTherapee internals.
- Exact visual behavior depends on the local RawTherapee version, decoder support, ICC setup, and the input file.
- The server never modifies the original source image. It writes session artifacts and backend state files in a managed workspace.
