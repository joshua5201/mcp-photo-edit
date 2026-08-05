# mcp-photo-edit

An installable MCP server for agent-driven photo editing with RawTherapee.

The server exposes a session-based editing workflow instead of raw sidecar manipulation.
Agents create an edit session, apply structured adjustments, regenerate previews when
needed, and export a final image. Installing `mcp-photo-edit` installs all Python runtime
dependencies automatically; users only need Python, an MCP client, and RawTherapee.

Each session now also maintains an explicit undo / redo timeline in `session.json`. Semantic edit history is tracked separately from preview-render history.

## Examples

The JPEG images embedded in this README are original work by Tsung-en Hsiao and are
licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
See [demo/ASSET_LICENSES.md](demo/ASSET_LICENSES.md) for the per-file list.

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

| Baseline | Gemini 3 Flash | Gemini 3.1 Pro | GPT-5.4 (Medium) | GPT-5.4 Mini (Medium) |
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
- `uv` for the easiest install and run workflow, or `pipx`
- RawTherapee with `rawtherapee-cli` available on `PATH`, or an absolute executable
  path set in `RAWTHERAPEE_CLI`

### Tested Environment

- **OS:** Windows 11 and Ubuntu 24.04 LTS
- **RawTherapee:** v5.12 on Windows and in the Ubuntu 24.04 RAW E2E workflow

Verify RawTherapee:

```shell
rawtherapee-cli -v
```

### Real RAW E2E test

The normal test suite skips the real RAW fixture so contributors without
RawTherapee can run the fast unit tests. To exercise the complete MCP stdio →
RawTherapee CLI path, provide an absolute CLI path and opt in explicitly:

```powershell
$env:RAWTHERAPEE_CLI = "C:\Program Files\RawTherapee\5.12\rawtherapee-cli.exe"
$env:MCP_PHOTO_EDIT_RAW_E2E = "1"
uv run --frozen pytest -m raw_e2e
```

The public fixture is licensed separately under CC BY-SA 4.0 and the workflow
does not upload any generated previews or exports.

On Windows, if RawTherapee is installed but its directory is not on `PATH`, set the
absolute executable path before starting the MCP client:

```powershell
$env:RAWTHERAPEE_CLI = "C:\Program Files\RawTherapee\5.12\rawtherapee-cli.exe"
```

## Install

Run the published package without cloning this repository:

```shell
uvx mcp-photo-edit
```

`uvx` creates and caches an isolated environment. All Python dependencies are resolved
from the package metadata. To install the command persistently instead:

```shell
uv tool install mcp-photo-edit
```

Or use `pipx`:

```shell
pipx install mcp-photo-edit
```

After a persistent install, the executable is simply `mcp-photo-edit`.

## MCP Quickstart

Example stdio configurations

### Codex CLI

Add this block:

```toml
[mcp_servers.photo_edit]
command = "uvx"
args = ["mcp-photo-edit"]

[mcp_servers.photo_edit.env]
MCP_PHOTO_EDIT_WORKDIR = "/absolute/path/to/.mcp-photo-edit"
```

If you prefer to add it from the CLI instead of editing TOML manually:

```bash
codex mcp add photo-edit --env MCP_PHOTO_EDIT_WORKDIR=/absolute/path/to/.mcp-photo-edit -- uvx mcp-photo-edit
```

Verify the server is registered:

```bash
codex mcp list
```

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
      "command": "uvx",
      "args": ["mcp-photo-edit"],
      "env": {
        "MCP_PHOTO_EDIT_WORKDIR": "/absolute/path/to/.mcp-photo-edit"
      },
      "timeout": 30000,
      "trust": true
    }
  }
}
```

Or add it from the CLI. This example writes to user config instead of project-local config:

```bash
gemini mcp add --scope user --transport stdio --env MCP_PHOTO_EDIT_WORKDIR=/absolute/path/to/.mcp-photo-edit --timeout 30000 --trust photo-edit uvx mcp-photo-edit
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

## Compatibility Note

RAW support depends on the local RawTherapee build and its bundled RAW decoders. A file extension being supported in principle does not guarantee that every camera or compression variant will decode on every machine. When diagnosing unsupported RAW files, check the installed RawTherapee version and the camera / compression mode used by the source file. For reference, this project is primarily developed and tested on the environment described in the [Tested Environment](#tested-environment) section.

**Note on Nikon RAW:** Some compressed Nikon RAW formats (e.g., High Efficiency / HE* compression) may not be supported by the underlying libraries in current RawTherapee builds. If you encounter issues with Nikon files, try using uncompressed RAW or Lossless Compressed modes if available in-camera.

## Advanced Image Info

The server can attach structured diagnostics to each preview:

- `preview_path` remains the primary image for aesthetic judgment.
- `diagnostic_summary` adds machine-readable stats for exposure, balance, and saturation.
- Set `DISABLE_ADVANCED_IMAGE_INFO=true` to turn the diagnostics off and keep the original preview-first workflow.

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

`list_supported_adjustments` is the source of truth for the installed renderer's runtime
capabilities.

## Session History

- `session.json` is the authoritative session timeline.
- `history` stores committed semantic edit steps.
- `history_index` points to the current step.
- `state.json` is the current renderer-neutral service request state.
- `render_preview` appends preview artifacts but does not append semantic edit history.
- Applying a new edit after undo truncates the redo tail.

## Project Layout

```text
src/mcp_photo_edit/
  interfaces.py    Backend protocols
  backend.py       Local file editing backend
  models.py        Pydantic schemas and validation
  session.py       Session lifecycle and persistence
  server.py        MCP tool registration
tests/
skills/
```

## Development

Install dev dependencies:

```bash
uv sync --frozen --group dev
```

Run tests:

```bash
uv run --frozen pytest
```

Start the server over stdio:

```bash
uv run --frozen mcp-photo-edit
```

This repository is self-contained for development. `uv sync --frozen --group dev` uses
the checked-in public-index lockfile to resolve all declared Python dependencies
automatically. Development and CI require uv `0.11.32`; the project itself is the
expected editable root entry in `uv.lock`.


## Disclaimers

- This project invokes `rawtherapee-cli`; it does not embed or redistribute RawTherapee internals.
- Exact visual behavior depends on the local RawTherapee version, decoder support, ICC setup, and the input file.
- The server never modifies the original source image. It writes session artifacts and backend state files in a managed workspace.
