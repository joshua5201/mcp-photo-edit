# mcp-photo-edit

An MCP server for agent-driven photo editing with RawTherapee.

The server exposes a session-based editing workflow instead of raw sidecar manipulation. Agents create an edit session, apply structured adjustments, regenerate previews when needed, and export a final image. Internally the server writes session-owned RawTherapee `PP3` files and renders them through `rawtherapee-cli`.

Each session now also maintains an explicit undo / redo timeline in `session.json`. Semantic edit history is tracked separately from preview-render history.

## Status

This is an MVP implementation.

Important backend notice:

- `rawtherapee-cli` is the supported backend.
- The legacy `darktable-cli` backend is not stable and will be removed in a future cleanup.

Current focus:

- session-based editing flow
- structured adjustment schema
- `rawtherapee-cli` preview and export
- RAW and common raster inputs when supported by the local RawTherapee build

Not in scope yet:

- local masks
- healing / AI retouch
- full photo-editor feature coverage
- large preset libraries
- batch editing UX

## Requirements

- Python 3.12+
- `rawtherapee-cli` on `PATH`

Install the project:

```bash
python3 -m pip install -e .
```

Verify `rawtherapee-cli`:

```bash
rawtherapee-cli -v
```

## Important Compatibility Note

RAW support depends on the local RawTherapee build and its bundled RAW decoders. A file extension being supported in principle does not guarantee that every camera or compression variant will decode on every machine. When diagnosing unsupported RAW files, check the installed RawTherapee version and the camera / compression mode used by the source file.

**Note on Nikon RAW:** Some compressed Nikon RAW formats (e.g., High Efficiency / HE* compression) may not be supported by the underlying libraries in current RawTherapee builds. If you encounter issues with Nikon files, try using uncompressed RAW or Lossless Compressed modes if available in-camera.

## Running The Server

Start the server over stdio:

```bash
python3 -m mcp_photo_edit
```

## MCP Client Configuration

Example stdio configuration:

```json
{
  "mcpServers": {
    "photo-edit": {
      "command": "python3",
      "args": ["-m", "mcp_photo_edit"],
      "env": {
        "MCP_PHOTO_EDIT_WORKDIR": "/absolute/path/to/.mcp-photo-edit",
        "MCP_PHOTO_EDIT_BACKEND": "rawtherapee-cli"
      }
    }
  }
}
```

### Codex CLI

Add this block:

```toml
[mcp_servers.photo_edit]
command = "python3"
args = ["-m", "mcp_photo_edit"]

[mcp_servers.photo_edit.env]
MCP_PHOTO_EDIT_WORKDIR = "/absolute/path/to/.mcp-photo-edit"
MCP_PHOTO_EDIT_BACKEND = "rawtherapee-cli"
```

If you prefer to add it from the CLI instead of editing TOML manually:

```bash
codex mcp add photo-edit --env MCP_PHOTO_EDIT_WORKDIR=/absolute/path/to/.mcp-photo-edit --env MCP_PHOTO_EDIT_BACKEND=rawtherapee-cli -- python3 -m mcp_photo_edit
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
      "command": "python3",
      "args": ["-m", "mcp_photo_edit"],
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
gemini mcp add --scope user --transport stdio --env MCP_PHOTO_EDIT_WORKDIR=/absolute/path/to/.mcp-photo-edit --env MCP_PHOTO_EDIT_BACKEND=rawtherapee-cli --timeout 30000 --trust photo-edit python3 -m mcp_photo_edit
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
2. Inspect the returned preview image, `preview_count`, current adjustment state, and history cursor fields such as `history_index`, `history_length`, `can_undo`, and `can_redo`.
3. Apply one or more adjustments.
4. Use `undo_adjustment` or `redo_adjustment` when you need to move across committed edit steps.
5. Re-check the preview by calling `render_preview` whenever you want a fresh preview artifact for the current step.
6. Export a final image explicitly.

See [SKILL.md](skills/mcp-photo-edit/SKILL.md) for an agent-facing usage guide.

## Adjustment Model

The public API exposes a stable edit schema. It does not ask clients to hand-author backend profile files.

Current default-backend MVP adjustments:

- `exposure`
- `contrast`
- `saturation`
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
docs/
```

## Development

Install dev dependencies:

```bash
python3 -m pip install -e .[dev]
```

Run tests:

```bash
pytest
```

## Disclaimers

- This project invokes `rawtherapee-cli`; it does not embed or redistribute RawTherapee internals.
- Exact visual behavior depends on the local RawTherapee version, decoder support, ICC setup, and the input file.
- The server never modifies the original source image. It writes session artifacts and backend state files in a managed workspace.
