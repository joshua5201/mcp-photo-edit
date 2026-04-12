# mcp-photo-edit

An MCP server for agent-driven photo editing with RawTherapee.

The server exposes a session-based editing workflow instead of raw sidecar manipulation. Agents create an edit session, apply structured adjustments, render previews, and export a final image. Internally the server writes session-owned RawTherapee `PP3` files and renders them through `rawtherapee-cli`.

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

## Available Tools

- `create_edit_session`
- `get_edit_session`
- `apply_adjustments`
- `reset_adjustments`
- `export_image`
- `list_supported_adjustments`

## Typical Agent Workflow

1. Create a session from an input image.
2. Inspect the returned preview path and current adjustment state.
3. Apply one or more adjustments.
4. Re-check the preview.
5. Export a final image explicitly.

See [docs/AGENT_SKILL.md](docs/AGENT_SKILL.md) for an agent-facing usage guide.

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
