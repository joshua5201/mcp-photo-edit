# mcp-darktable

An MCP server for agent-driven photo editing with `darktable-cli`.

The server exposes a session-based editing workflow instead of raw XMP manipulation. Agents create an edit session, apply structured adjustments, render previews, and export a final image. Internally the server writes native darktable XMP history sidecars and asks `darktable-cli` to render them.

## Status

This is an MVP implementation.

Current focus:

- session-based editing flow
- structured adjustment schema
- `darktable-cli` preview and export
- Nikon NEF and common raster inputs when supported by the local darktable build

Not in scope yet:

- local masks
- healing / AI retouch
- full darktable module coverage
- large preset libraries
- batch editing UX

## Requirements

- Python 3.12+
- `darktable-cli` on `PATH`

Install the project:

```bash
python3 -m pip install -e .
```

Verify `darktable-cli`:

```bash
darktable-cli --version
```

## Important Compatibility Note

RAW support depends on the local darktable build and its bundled RAW decoders. A file extension being supported by darktable does not guarantee that every camera or compression variant will decode on every machine.

On this machine, the bundled sample Nikon Z50_2 `.NEF` files under `.codex/raw/` do not decode successfully with `darktable 4.6.1` because RawSpeed does not recognize that camera variant. The MCP server still supports RAW inputs in principle, but actual success depends on local decoder support.

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
        "MCP_DARKTABLE_WORKDIR": "/absolute/path/to/.mcp-darktable"
      }
    }
  }
}
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

Current MVP adjustments:

- `exposure`
- `contrast`
- `saturation`
- `orientation`
- `crop`

Use `list_supported_adjustments` to discover exact ranges, defaults, and example payloads at runtime.

## Project Layout

```text
src/mcp_darktable/
  models.py        Pydantic schemas and validation
  session.py       Session lifecycle and persistence
  xmp.py           Adjustment to XMP translation
  render.py        darktable-cli integration
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

- This project invokes `darktable-cli`; it does not embed or redistribute darktable internals.
- Exact visual behavior depends on the local darktable version, decoder support, ICC setup, and the input file.
- The server never modifies the original source image. It writes session artifacts and sidecars in a managed workspace.
