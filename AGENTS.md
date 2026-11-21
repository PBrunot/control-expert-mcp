# Repository Guidelines

## Project Structure & Module Organization

`src/control_expert_mcp/` contains the Python MCP server. `server.py` registers tools; `bridge.py` handles Control Expert COM automation; `modbus.py` provides live value access; `schema.py` validates exchange XML. Workflow prompts live in `prompts.py`, with language examples in `lang_reference.py` and enums in `constants.py`.

`samples/` contains MCP client configurations. `tools/` holds diagnostic scripts, `lang_refs/` XML examples, and numbered `bigtest/` integration workflows. The DDT Mirror application has moved to a separate repository.

## Build, Test, and Development Commands

Use Python 3.10+ on Windows with a licensed local Control Expert installation for COM integration.

- `python -m venv .venv`: create the development environment.
- `.venv\Scripts\python.exe -m pip install -e .`: install the package and dependencies for development.
- `.venv\Scripts\python.exe -m control_expert_mcp`: start the MCP stdio server; the installed `control-expert-mcp` command is equivalent.
- `.venv\Scripts\python.exe -m compileall -q src`: check Python syntax without exercising COM.
- From `tools/`, run `..\.venv\Scripts\python.exe validate_templates.py` to exercise template import/build validation against Control Expert. Inspect its setup before running.

Packaging uses setuptools through `pyproject.toml`.

## Coding Style & Naming Conventions

Follow existing Python style: four-space indentation, `snake_case` functions/modules, `PascalCase` classes, and `UPPER_CASE` constants. Use type hints and concise docstrings for public helpers. No formatter or lint configuration is currently declared.

Keep COM calls on the bridge's dedicated STA worker thread and preserve session write-token handling. For every new capability, add or extend an MCP prompt describing the validated tool sequence and relevant gotchas.

## Testing Guidelines

No automated test framework or coverage threshold is configured. Validate changed behavior with focused scripts and Control Expert import/analyze/build round trips. Record CPU/version, prerequisites, commands, and results. Existing integration scripts use numbered names such as `01_inventory.py`; they require local reference data and may modify projects or terminate Control Expert processes. Review them before execution.

## Commit & Pull Request Guidelines

Use concise, descriptive commit subjects; history includes optional component prefixes such as `gitignore:` and `Web UI:`. Explain behavior changes, link relevant issues, and document validation and environment limitations in pull requests. Update README tool documentation and workflow prompts when capabilities change.

## Security & Configuration

Keep online access opt-in through `CE_MCP_ENABLE_ONLINE=1`; validate against a simulator or supervised test bench. Never commit customer exports, proprietary reference data, vendor binaries, or generated project archives; respect `.gitignore`. Set `CE_MCP_SCHEMA_DIR` when schemas need an explicit installation path.
