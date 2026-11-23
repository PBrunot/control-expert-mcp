# Control Expert MCP Server

[![CI](https://github.com/PBrunot/control-expert-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/PBrunot/control-expert-mcp/actions/workflows/ci.yml)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-blue)
![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)

English · [Italiano](README.it.md)

Connect an MCP client to a local **EcoStruxure Control Expert** (Unity Pro) installation. Inspect, create, edit, and build PLC projects through Schneider Electric's UDE COM automation API.

This is an experimental project for LLM-assisted PLC programming and debugging.

[PyPI](https://pypi.org/project/control-expert-mcp/) · [Detailed guide](docs/guide.md) · [Benchmarks](benchmarks/README.md)

> [!WARNING]
> Online tools can download applications, start or stop controllers, and write process values. They are disabled by default. Use a simulator or a supervised test bench; production equipment requires qualified supervision.

## Features

- **Projects:** create, open, save, import, and export Control Expert projects.
- **Logic:** inspect and edit ST, LD, FBD, SFC, and IL; manage variables, DFBs, and DDTs.
- **Hardware and communications:** configure CPUs, racks, modules, DTMs, Ethernet services, and Modbus scan requests.
- **Validation:** validate exchange XML, analyze and build projects, and inspect diagnostics.
- **Documentation:** search locally converted vendor manuals with source citations.
- **Live access (opt-in):** use OFS OPC DA for symbolic values or Modbus TCP for located values; commission and test with PLC Simulator.

Availability depends on the installed Control Expert version, license, hardware catalog, and DTM libraries. Clients expose the tools' argument schemas and descriptions; see the [tool reference](docs/guide.md#tool-reference) and [guided workflows](docs/guide.md#guided-workflows).

## Requirements

- Windows with Python **3.11+**.
- A licensed local installation of **Control Expert or Unity Pro** and its registered UDE COM broker (`PSBroker.PServerBroker.1`). Tested with Control Expert 14.0 and 16.4.
- An MCP client supporting **stdio**, such as Claude Desktop, Claude Code, VS Code with GitHub Copilot, Codex, or DeepSeek Harness.

Run the server on the same machine as Control Expert. The UDE automation server is included with Control Expert; the separate UDE package is needed only for its documentation.

## Quick start

Install on the Windows machine running Control Expert:

```powershell
py -3.11 -m pip install --upgrade control-expert-mcp
```

Configure your MCP client to launch `control-expert-mcp` with no arguments. For clients using `mcpServers` JSON, such as Claude Desktop:

```json
{
  "mcpServers": {
    "control-expert": {
      "command": "control-expert-mcp",
      "args": [],
      "env": {
        "CE_MCP_ENABLE_ONLINE": "0"
      }
    }
  }
}
```

For Codex CLI:

```powershell
codex mcp add control-expert --env CE_MCP_ENABLE_ONLINE=0 -- control-expert-mcp
```

The client starts and manages the server. If it cannot find the command, use the executable's absolute path, or the installing Python interpreter with arguments `["-m", "control_expert_mcp"]`.

See the [client configuration guide](docs/guide.md#mcp-client-configuration) for Claude Desktop, Claude Code, VS Code, Codex, and DeepSeek Harness. Ready-to-edit examples are in [samples/](samples/).

## Usage

Start with a disposable project or a copy. Example requests:

- “Open this project and summarize its CPU, tasks, sections, and global variables.”
- “Create an ST section for a motor interlock, declare its variables, and build the project.”
- “Inspect the hardware tree and list the configured Modbus devices.”
- “Search the local manuals for `READ_VAR` and cite the relevant topic.”

Build after changes, inspect the result, and save explicitly. Imports can replace existing sections; `close_project` discards changes unless `save=true`. Opening a `.sta` archive creates an unsaved application: save it to an explicit `.stu` path.

A successful build does not prove runtime correctness. Check `build_state`, errors, and raw output alongside parsed diagnostics. For runtime tests, observe outputs against expected results and restore test inputs. See [authoring and build results](docs/guide.md#usage).

## Configuration

Set these variables in the MCP client's server environment:

| Variable | Purpose |
| --- | --- |
| `CE_MCP_ENABLE_ONLINE` | Set to `1` and restart to expose online tools. Disabled by default; session consent is still required. |
| `CE_MCP_OPC_PYTHON` | Python matching the OPC Automation DLL bitness, with `pywin32` installed. OFS commonly needs a separate 32-bit interpreter. |
| `CE_MCP_SCHEMA_DIR` | Override the auto-discovered Control Expert `SrcXmlSchema` directory. |
| `CE_MCP_MANUALS_DIR` | Converted and indexed local manuals. Set an absolute path for packaged installations. |
| `CE_MCP_SIMULATOR_EXE` | Optional simulator executable override for custom installation paths or startup without an open project. |

### PLC and simulator access

Enabling online tools does **not** grant access to a controller. Use `get_live_access_setup` and `configure_live_access` to record the user's choices for each server session. Confirm OFS availability and the device alias for OPC; obtain separate approval for closed-loop writes and PLC control.

Prefer **OFS OPC DA** for simulator tests and symbolic variables, including exposed unlocated variables and DFB members. The running application's data dictionary must expose the required symbols. **Modbus TCP** supports located `%M` / `%MW` values.

Follow the [live-access and commissioning guide](docs/guide.md#plc-and-simulator-access) for setup, dictionary settings, download steps, and the conditional “Family check failed” workaround.

### Local manuals

Manual search works without a COM session or PLC connection. Convert your locally installed help and build its index first; generated vendor content stays local. See [manual conversion and search](docs/guide.md#searchable-local-manuals).

## Troubleshooting

- **COM startup fails:** check licensing and UDE registration. If the broker reports an integrity error, restart it after checking the Windows `CommonProgramFiles` environment paths.
- **CPU or module not found:** use the exact reference and version from the installed catalog.
- **First call times out:** project loading can take 30–120 seconds; increase the client's tool timeout.
- **XML import fails:** export a similar object and run `validate_xml` before importing.

More cases are in the [troubleshooting guide](docs/guide.md#troubleshooting). Report reproducible problems in [GitHub Issues](https://github.com/PBrunot/control-expert-mcp/issues), with versions, tool calls, and sanitized errors.

## Benchmarks

The offline suite covers seven tasks: project inspection, threshold and temperature
logic changes, fault repair, gated hysteresis alarms, weighing analysis, and I/O
mapping. Each task runs on a disposable project copy in two conditions: without
and with installed-manual search. Edits are independently reopened and built;
inspection answers use deterministic grading, including a fixed Markdown table
format for I/O mappings. A separate M580 simulator test checks that `TEST_LLM`
increments once per second through OFS OPC DA observations.

![Benchmark overview: acceptance, I/O mapping correctness, time, and token usage](benchmarks/archive/overview.png)

Results are exploratory; offline acceptance does not establish PLC runtime
correctness. See the [benchmark guide](benchmarks/README.md) for test definitions,
scoring, setup, and limitations, and the [archived results](benchmarks/archive/README.md)
for individual run reports.

## Development

```powershell
git clone https://github.com/PBrunot/control-expert-mcp.git
cd control-expert-mcp
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[benchmark,test]"
.venv\Scripts\python.exe -m compileall -q src
.venv\Scripts\python.exe -m unittest discover -s tools -p "test_*.py"
```

For a source installation, point the MCP client to the absolute `.venv\Scripts\python.exe` path with arguments `["-m", "control_expert_mcp"]`.

See [AGENTS.md](AGENTS.md) for repository conventions, the [development guide](docs/guide.md#development-and-validation) for architecture and integration checks, and [packaging and releases](docs/guide.md#packaging-and-releases) for distribution commands. Review integration scripts before running them: they can modify projects or terminate Control Expert.

## License and credits

MIT, as declared in [pyproject.toml](pyproject.toml). Forked from [apexsotjo-blip/control-expert-mcp](https://github.com/apexsotjo-blip/control-expert-mcp) and inspired by [tiaportal-mcp](https://github.com/heilingbrunner/tiaportal-mcp).

Not affiliated with or endorsed by Schneider Electric. Control Expert and Unity Pro software, licenses, and documentation are supplied separately.
