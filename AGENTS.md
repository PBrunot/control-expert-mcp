# Repository Guidelines

## Project Structure & Module Organization

`src/control_expert_mcp/` contains the server: `server.py` registers tools; `bridge.py` handles COM; `opc.py`/`opc_worker.py` provide symbolic live access; `modbus.py` handles located values; `live_access.py` manages consent; `schema.py` validates XML. Workflow prompts live in `prompts.py`; benchmark code lives in `benchmark/`.

`tools/` contains regression tests and diagnostics; `tools/lang_refs/` holds XML examples; `tools/bigtest/` contains integration workflows. `samples/` holds client configurations and Markdown inspection examples. `benchmarks/` holds benchmark configuration and archive guidance. DDT Mirror is maintained separately.

## Build, Test, and Development Commands

Use Python 3.11+; COM integration requires Windows and licensed Control Expert. Create `.venv` with `python -m venv .venv`, then activate it with `.venv\Scripts\Activate.ps1`. Commands below assume activation:

- `python -m pip install -e ".[benchmark,test]"`: install development dependencies.
- `python -m control_expert_mcp`: start the stdio server.
- `python -m unittest discover -s tools -p "test_*.py" -v`: run offline regressions.
- `python -m compileall -q src`: check syntax.

For packaging, install `build` and `twine`, run `python -m build --outdir tmp/release-check` into a fresh directory, then `python -m twine check --strict tmp/release-check/*` and `python tools/check_distribution.py --dist-dir tmp/release-check`.

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` functions/modules, `PascalCase` classes, type hints, and concise docstrings. No formatter or linter is configured.

Keep COM on its dedicated STA worker and preserve write-token handling. Add or extend workflow prompts for new capabilities.

## Testing Guidelines

Use `unittest` with `tools/test_*.py`; no coverage threshold is configured. CI tests Windows/Python 3.11–3.15 and validates isolated wheel installation. Review integration scripts before execution: they may modify projects or terminate Control Expert. For COM changes, validate import/analyze/build round trips and record CPU/version, prerequisites, commands, and results.

When archiving benchmarks, regenerate graphics and metadata with `ce-bench visualize`, verify integrity, and commit data, graphics, and metadata together.

A request to run the **full DeepSeek suite** includes both the seven-task offline A/B campaign (14 cases per repetition) and the M580 simulator `TEST_LLM` +1 every second campaign. Run them sequentially and report both results; the offline campaign alone is not the full suite. Use the existing local DeepSeek configurations and simulator/OFS prerequisites documented in `benchmarks/README.md`. Keep their evidence and acceptance results separate. Respect the simulator consent and target checks; do not substitute a physical PLC. Make documentation/source edits only after campaigns finish because source fingerprints are immutable during a campaign.

## Commit & Pull Request Guidelines

Use concise subjects with optional component prefixes. PRs should explain behavior, link issues, and report validation/limitations. Update README and prompts for capability changes. Releases require matching `pyproject.toml`, `plugin/.claude-plugin/plugin.json` and `plugin/.mcp.json` versions (checked by `tools/test_plugin.py`) and `vX.Y.Z` tags; publishing a GitHub release triggers validated PyPI publication.

## Security & Configuration

`CE_MCP_ENABLE_ONLINE=1` exposes live tools but does not grant session consent. Configure live access explicitly; prefer OPC, confirm OFS availability, and obtain approval before closed-loop writes. Use a simulator or supervised bench. Never commit customer data, vendor binaries, or generated project archives. Respect `.gitignore`; use `CE_MCP_SCHEMA_DIR` for explicit schema paths.
