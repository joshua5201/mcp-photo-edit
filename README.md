# mcp-photo-edit

An MCP server for agent-driven photo editing with pluggable RAW backends.

The server exposes a session-based editing workflow instead of raw sidecar manipulation. Agents create an edit session, apply structured adjustments, render previews, and export a final image. The current default backend writes session-owned RawTherapee `PP3` files and renders them through `rawtherapee-cli`. A darktable backend remains available as an optional fallback.

Proposed project rename:

- Public name: `mcp-photo-edit`
- Current repo, package, and CLI identifiers remain `mcp-darktable` / `mcp_darktable` during the migration

## Status

This is an MVP implementation.

Current focus:

- session-based editing flow
- structured adjustment schema
- `rawtherapee-cli` preview and export
- Nikon NEF and common raster inputs when supported by the local backend build

Not in scope yet:

- local masks
- healing / AI retouch
- full darktable module coverage
- large preset libraries
- batch editing UX

## Requirements

- Python 3.12+
- `rawtherapee-cli` on `PATH`

Optional fallback backend:

- `darktable-cli` on `PATH`

Install the project:

```bash
python3 -m pip install -e .
```

Verify `rawtherapee-cli`:

```bash
rawtherapee-cli -v
```

## Important Compatibility Note

RAW support depends on the local backend build and its bundled RAW decoders. A file extension being supported by a backend does not guarantee that every camera or compression variant will decode on every machine.

On this machine, the bundled sample Nikon Z50_2 `.NEF` files under `.codex/raw/` do not decode successfully with `darktable 4.6.1` because RawSpeed does not recognize that camera variant. The default RawTherapee backend can process the Nikon Z6II `.NEF` samples under `.codex/raw-z62`.

## Running The Server

Start the server over stdio:

```bash
python3 -m mcp_darktable
```

## MCP Client Configuration

Example stdio configuration:

```json
{
  "mcpServers": {
    "darktable": {
      "command": "python3",
      "args": ["-m", "mcp_darktable"],
      "env": {
        "MCP_DARKTABLE_WORKDIR": "/absolute/path/to/.mcp-darktable",
        "MCP_DARKTABLE_BACKEND": "rawtherapee-cli"
      }
    }
  }
}
```

### Codex CLI

Codex reads MCP configuration from `~/.codex/config.toml`.

Add this block:

```toml
[mcp_servers.darktable]
command = "python3"
args = ["-m", "mcp_darktable"]

[mcp_servers.darktable.env]
MCP_DARKTABLE_WORKDIR = "/absolute/path/to/.mcp-darktable"
MCP_DARKTABLE_BACKEND = "rawtherapee-cli"
```

If you prefer to add it from the CLI instead of editing TOML manually:

```bash
codex mcp add darktable --env MCP_DARKTABLE_WORKDIR=/absolute/path/to/.mcp-darktable --env MCP_DARKTABLE_BACKEND=rawtherapee-cli -- python3 -m mcp_darktable
```

Verify the server is registered:

```bash
codex mcp list
```

Recommended `AGENTS.md` snippet for better tool selection:

```md
Use the `darktable` MCP server for photo-editing tasks. Create an edit session first, iterate with previews, and export only when the preview looks correct.
```

### Gemini CLI

Gemini CLI stores user MCP config in `~/.gemini/settings.json`. Project-local config can also live in `.gemini/settings.json`.

Add this block:

```json
{
  "mcpServers": {
    "darktable": {
      "command": "python3",
      "args": ["-m", "mcp_darktable"],
      "env": {
        "MCP_DARKTABLE_WORKDIR": "/absolute/path/to/.mcp-darktable",
        "MCP_DARKTABLE_BACKEND": "rawtherapee-cli"
      },
      "timeout": 30000,
      "trust": true
    }
  }
}
```

Or add it from the CLI. This example writes to user config instead of project-local config:

```bash
gemini mcp add --scope user --transport stdio --env MCP_DARKTABLE_WORKDIR=/absolute/path/to/.mcp-darktable --env MCP_DARKTABLE_BACKEND=rawtherapee-cli --timeout 30000 --trust darktable python3 -m mcp_darktable
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

The public API exposes a stable edit schema. It does not expose raw darktable module XML or ask clients to hand-author XMP.

Current default-backend MVP adjustments:

- `exposure`
- `contrast`
- `saturation`

Use `list_supported_adjustments` to discover exact ranges, defaults, and example payloads at runtime.

Backend note:

- `rawtherapee-cli` is the default backend and currently supports `exposure`, `contrast`, and `saturation`
- `darktable-cli` remains available as an optional fallback backend while geometry support is migrated

## Project Layout

```text
src/mcp_darktable/
  models.py        Pydantic schemas and validation
  session.py       Session lifecycle and persistence
  pp3.py           Adjustment to RawTherapee PP3 translation
  xmp.py           Legacy darktable XMP translation
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

- This project invokes external CLI backends such as `rawtherapee-cli` and `darktable-cli`; it does not embed or redistribute their internals.
- Exact visual behavior depends on the local backend version, decoder support, ICC setup, and the input file.
- The server never modifies the original source image. It writes session artifacts and backend state files in a managed workspace.
