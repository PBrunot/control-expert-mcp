# Control Expert MCP Server

[![CI](https://github.com/PBrunot/control-expert-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/PBrunot/control-expert-mcp/actions/workflows/ci.yml)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-blue)
![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)

Connect MCP clients to a local **EcoStruxure Control Expert** (formerly **Unity Pro**) installation. Inspect, create, edit, and build PLC projects through Schneider Electric's Unity Developer's Edition (UDE) COM automation API.

```text
MCP client ── stdio ──> control-expert-mcp ── COM ──> Control Expert
                                         └─ Modbus TCP ──> PLC / simulator (opt-in)
```

Inspired by [tiaportal-mcp](https://github.com/heilingbrunner/tiaportal-mcp). This project uses the Control Expert UDE broker (`PSBroker.PServerBroker`) through `pywin32`.

> [!WARNING]
> Online tools can download applications, start or stop controllers, and write process values. They are disabled by default. Enable them only for a simulator or a supervised test bench; production equipment requires qualified supervision.

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [MCP client configuration](#mcp-client-configuration)
- [Configuration](#configuration)
- [Usage](#usage)
- [Tool reference](#tool-reference)
- [Guided workflows](#guided-workflows)
- [PLC and simulator access](#plc-and-simulator-access)
- [Searchable local manuals](#searchable-local-manuals)
- [Troubleshooting](#troubleshooting)
- [Development and validation](#development-and-validation)
- [Packaging and releases](#packaging-and-releases)
- [Contributing](#contributing)
- [License and affiliation](#license-and-affiliation)

## Features

- **Project management:** create projects using installed CPU catalog entries; open and save `.stu` / `.sta`; import and export `.xef` / `.zef`.
- **Program authoring:** inspect and edit ST, LD, FBD, SFC, and IL sections. Write ST directly or import Control Expert exchange XML for graphical languages, variables, DFBs, and DDTs.
- **Hardware configuration:** inspect buses, drops, racks, and modules; add, replace, or remove supported hardware; change the CPU.
- **Communications:** manage DTMs, device addresses, M580 Modbus scan requests, CPU Ethernet services, and Premium/Quantum logical networks.
- **Validation:** check exchange XML against installed schemas, analyze and build projects, and retrieve build diagnostics.
- **Documentation:** search locally converted vendor manuals and retrieve topics with source citations, without opening Control Expert.
- **Monitoring and commissioning:** open animation tables and, when explicitly enabled, connect to a PLC or simulator and read or write located tags over Modbus TCP.

Availability depends on the installed Control Expert version, license, hardware catalog, and DTM libraries.

## Requirements

| Requirement | Details |
| --- | --- |
| Operating system | Windows for Control Expert COM automation |
| Python | 3.11 or newer, as declared in `pyproject.toml` |
| Control Expert | Licensed local installation of EcoStruxure Control Expert or Unity Pro; validated with versions 14.0 and 16.4 |
| Automation interface | Registered UDE COM broker (`PSBroker.PServerBroker.1`) |
| MCP client | A client supporting stdio servers, such as Claude Desktop, Claude Code, or VS Code with GitHub Copilot |

Run the server on the **same machine as Control Expert**. DCOM remoting is not configured. The UDE automation server ships with Control Expert; the separate UDE package is only needed for its documentation. Python dependencies are installed with the package.

## Quick start

Run these commands in PowerShell:

```powershell
git clone https://github.com/PBrunot/control-expert-mcp.git
cd control-expert-mcp
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

Configure your MCP client with the absolute path to `.venv\Scripts\python.exe` and arguments `["-m", "control_expert_mcp"]`, using an example below.

To launch the stdio server manually:

```powershell
.venv\Scripts\python.exe -m control_expert_mcp
```

The installed `control-expert-mcp` console command is equivalent. This is a stdio service; an MCP client normally starts and manages the process.

## MCP client configuration

Replace `C:\path\to\control-expert-mcp` with your checkout path. Keep online access disabled for initial setup.

### Claude Desktop

Add this entry to `%APPDATA%\Claude\claude_desktop_config.json`. A copy is available in [samples/claude_desktop_config.json](samples/claude_desktop_config.json).

```json
{
  "mcpServers": {
    "control-expert": {
      "command": "C:\\path\\to\\control-expert-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "control_expert_mcp"],
      "env": {
        "CE_MCP_ENABLE_ONLINE": "0"
      }
    }
  }
}
```

### Claude Code

```powershell
claude mcp add control-expert -- C:\path\to\control-expert-mcp\.venv\Scripts\python.exe -m control_expert_mcp
```

Online access remains disabled unless the server inherits an enabling environment variable.

### VS Code / GitHub Copilot

Add the server to `.vscode/mcp.json`. See [samples/vscode-mcp.json](samples/vscode-mcp.json).

```json
{
  "servers": {
    "control-expert": {
      "type": "stdio",
      "command": "C:\\path\\to\\control-expert-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "control_expert_mcp"],
      "env": {
        "CE_MCP_ENABLE_ONLINE": "0"
      }
    }
  }
}
```

## Configuration

Set environment variables in the MCP client's server configuration so they reach the server process.

| Variable | Default | Purpose |
| --- | --- | --- |
| `CE_MCP_ENABLE_ONLINE` | Disabled | Set to `1` to register `plc_*`, `modbus_*`, `read_tags`, and `write_tags`. Restart the server after changing it. |
| `CE_MCP_SCHEMA_DIR` | Auto-discovered | Override the path to Control Expert's installed `SrcXmlSchema` directory for XML validation. |
| `CE_MCP_MANUALS_DIR` | Repository-relative `manuals/ce-16.4` | Path to a converted and indexed local manual corpus. Set an absolute path for packaged installations. |

## Usage

Start with a disposable project or a copy of an existing project. Example requests to your connected AI client:

- “Open this project and summarize its CPU, tasks, sections, and global variables.”
- “Create an ST section for a motor interlock, declare its variables, and build the project.”
- “Inspect the hardware tree and list the configured Modbus devices.”
- “Search the installed manuals for `READ_VAR` and cite the relevant topic.”

### Authoring logic

For Structured Text, `write_st_logic` accepts IEC source directly. The following illustrates MCP tool arguments; it is not a standalone Python script:

```text
write_st_logic(
    task="MAST",
    section="MotorControl",
    st_source="MotorRun := StartButton AND NOT StopButton;",
    declare="StartButton:BOOL, StopButton:BOOL, MotorRun:BOOL"
)
build_project()
```

The tool creates the section or replaces its existing logic. For LD, FBD, SFC, and IL, consult `get_language_reference`, export a similar object when needed, validate the candidate XML with `validate_xml`, and import it with `import_xml`. Declare referenced variables first or include them in the exchange XML.

**Imports can replace existing sections.** Build after changes, inspect the result, and save explicitly. `close_project` discards changes unless `save=true`.

### Interpreting build results

`build_project` and `analyze_project` return `build_state`, raw `output`, an `error` when present, parsed `diagnostics`, and capture metadata. Recognized diagnostic lines include severity, code, task/section, and line/column where available; unknown or localized formats remain in raw output.

An empty diagnostic list does **not** prove a clean build. Check `build_state`, `error`, raw output, and `diagnostics_summary` together. `diagnostics_available` distinguishes an empty Build tab from unavailable output. Capture metadata reports freshness and snapshot/appended scope, but attribution remains `unverified`: the COM output API provides no operation identifier, and identical output may belong to a repeated build or an older operation.

## Tool reference

Tools are registered in [server.py](src/control_expert_mcp/server.py). The client exposes their full argument schemas and descriptions.

| Area | Tools |
| --- | --- |
| Project lifecycle | `get_status`, `open_project`, `new_project`, `save_project`, `close_project`, `export_project` |
| Build and settings | `analyze_project`, `build_project`, `get_project_setting`, `set_project_settings` |
| Project structure | `get_project_structure`, `create_task`, `create_section`, `delete_section`, `read_section` |
| Logic authoring | `write_st_logic`, `get_language_reference`, `place_fb_in_ladder`, `use_fb_in_ladder` |
| Exchange XML | `validate_xml`, `import_xml`, `export_xml` |
| Variables and types | `list_variables`, `create_variable`, `update_variable`, `delete_variable`, `list_data_types` |
| Hardware | `get_hardware`, `add_io_module`, `remove_io_module`, `replace_io_module`, `add_drop`, `add_rack`, `replace_rack`, `change_cpu` |
| DTM topology and addressing | `list_dtms`, `add_dtm`, `delete_dtm`, `set_dtm_address` |
| DTM configuration | `get_dtm_control_parameters`, `set_dtm_control_parameters`, `get_dtm_dataset`, `set_dtm_dataset`, `get_master_dtm_dataset`, `set_master_dtm_dataset` |
| Ethernet and networks | `configure_cpu_ethernet`, `list_networks`, `add_network`, `set_network_ip` |
| Animation tables and UI | `list_animation_tables`, `create_animation_table`, `delete_animation_table`, `show_ui`, `open_animation_table` |
| Simulator process | `start_simulator`, `stop_simulator` |
| Local manuals | `get_documentation_status`, `search_manuals`, `get_manual_topic` |
| PLC connection **(opt-in)** | `plc_setup_connection`, `plc_connect`, `plc_disconnect`, `plc_state`, `plc_transfer`, `plc_command` |
| Live values **(opt-in)** | `modbus_connect`, `modbus_disconnect`, `modbus_status`, `read_tags`, `write_tags` |

DTM scan-request configuration uses the master/CPU dataset's `ManagedModbusRequestList`. Follow the template in `set_master_dtm_dataset` and the `add_modbus_device` prompt, including GUID and numbering rules. `place_fb_in_ladder` generates pin geometry for project DFBs; `use_fb_in_ladder` provides a template-based fallback for elementary blocks or exact GUI geometry.

## Guided workflows

The server includes reusable MCP prompts in [prompts.py](src/control_expert_mcp/prompts.py). Select them through your client's prompt picker.

| Prompt | Workflow |
| --- | --- |
| `scaffold_project` | Create a project using exact CPU/catalog versions, configure hardware, build, and save. |
| `author_logic` | Consult language references, author or import logic, build, and resolve errors. |
| `fb_in_ladder` | Place a function block in Ladder and bind its pins. |
| `add_modbus_device` | Add a Modbus TCP slave DTM and configure a scan request. |
| `commission_simulator` | Build, start the simulator, connect, transfer, and run, including the first-transfer limitation. |
| `test_logic_live` | Test located values over Modbus, including mirrors for unlocated DFB internals. |
| `consult_installed_manuals` | Prepare, search, retrieve, and cite local documentation. |
| `benchmark_training_project` | Run the offline benchmark training workflow. |

## PLC and simulator access

Set `CE_MCP_ENABLE_ONLINE=1` in the server environment and restart it to expose online tools. Use the `commission_simulator` prompt for the complete procedure.

The commissioning sequence is:

1. Build the project and confirm `build_state="built_ok"`.
2. Launch the simulator with `start_simulator` or the installed `PLC_Simulator\sim.exe`.
3. Configure `plc_setup_connection(target="simulator", address="127.0.0.1")` and call `plc_connect(target="simulator")`.
4. Ensure the controller is stopped before `plc_transfer(direction="pc_to_plc")`.
5. Call `plc_command(command="run")` and inspect `plc_state`.

> [!IMPORTANT]
> A fresh simulator with no station loaded (`no_conf`) can reject API downloads with **“Family check failed.”** Seed it once through the Control Expert GUI: PLC → Simulation Mode → Connect → Transfer, using a project of the matching controller family. The station persists while `sim.exe` runs. Subsequent API downloads require the controller to be stopped.

### Live values over Modbus TCP

The UDE COM API exposes the offline project database, not live tag values. This server uses Modbus TCP for live reads and writes. Animation tables can display values in the GUI.

Example MCP tool calls against a simulator:

```text
modbus_connect(host="127.0.0.1", port=502)
read_tags(tags="MotorRun, %MW0, %MW2:REAL")
write_tags(values={"%MW2:REAL": 4.0})
modbus_disconnect()
```

- Only **located `%M` / `%MW` tags** are reachable. Mirror unlocated DFB internals such as `Pump1.Running` to located variables in the program first.
- Use global variable names or explicit addresses, optionally with a type: `%M3`, `%MW86`, `%MW2:REAL`, `%MW70:UDINT`, or `%MW10.2` for a word bit.
- 32-bit `REAL` / `DINT` values use Schneider's low-word-first order by default. Set `word_order="high_first"` when required by the target.
- The validated simulator endpoint is `127.0.0.1:502`.

## Searchable local manuals

Convert your locally installed Control Expert help, then build its search index. Conversion requires Windows, the optional help dependencies, and 7-Zip for CHM extraction.

From the repository root:

```powershell
.venv\Scripts\python.exe -m pip install -e . -r tools/requirements-help.txt
.venv\Scripts\python.exe tools/export_ce_help.py --list
.venv\Scripts\python.exe tools/export_ce_help.py --languages en --jobs 4
.venv\Scripts\python.exe tools/index_ce_help.py --manuals-dir manuals/ce-16.4
```

The converter defaults to `C:\Program Files (x86)\Schneider Electric\EcoStruxure Control Expert 16.4` and writes to `manuals/ce-16.4`. Use `--install-dir` and `--output` to override paths, `--languages en it` or `--languages all` for additional languages, and `--include baselib.chm` to select a source. Completed unchanged sources are cached; `--force` regenerates them. Failed or partial exports can be resumed.

Set `CE_MCP_MANUALS_DIR` to the absolute corpus path in your client configuration. Wheel installations can index an existing corpus with:

```powershell
python -m control_expert_mcp.documentation --manuals-dir C:\path\to\manuals\ce-16.4
```

Use `get_documentation_status`, then `search_manuals(query="TON")`, and retrieve a result with `get_manual_topic(topic_id=...)`. Searches return excerpts and citations; topic retrieval preserves original Markdown, tables, code, and source context. Follow `next_cursor` with the same topic and section until it is null.

Key behavior and limits:

- Conversion and indexing are explicit local operations. MCP requests never convert, index, or download manuals and require no COM session or PLC connection.
- Search accepts literal words and symbols. `language` selects the documentation language, not the PLC programming language; version filters require exact metadata matches.
- Citations include source paths/hashes, topic locations, language, converter metadata, and warnings. Unknown publication versions remain unknown; a manual match does not establish CPU applicability or installed-block availability.
- Stale indexes are refused. Rerun conversion after vendor updates and indexing after corpus or metadata changes. Freshness is checked against the conversion manifest, not a live scan of the vendor installation.
- Conversion performs no OCR. PDF layouts and tables may need comparison with the originals; pages without native text are reported. CHM scripts are not executed.
- Generated vendor manuals, indexes, and reports stay local and are excluded from Git and distributions. Treat manual content as reference data.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| COM broker creation fails | Confirm Control Expert is installed and licensed. Repair its installation if COM registration is broken. |
| `Catalog object not found` | Match CPU part number, spacing, and firmware exactly to the installed catalog; for example, `BMX P34 2020` / `02.70`. |
| Module reference is missing from the catalog | Supply the exact module reference and catalog version. Check the installed catalog rather than assuming a version. |
| `new_project` returns a bare `Exception occurred` | Try the same CPU in the GUI to check platform licensing and installed libraries. |
| Write access is reserved by another client | Close the project in the other writable GUI/automation session. The server holds one write token per session. |
| First project operation takes a long time | Startup and large-project loading can take 30–120 seconds. Increase the client's tool timeout. |
| XML import reports `Invalid file` | Export a similar object and mirror its schema, including headers. Run `validate_xml` before importing. |
| DTM protocol ID is invalid | Use the exact DTM catalog name, such as `Modbus Device`, and protocol `Modbus`. Inspect `tools/list_dtm_catalog.py` when needed. |
| Master DTM dataset update fails with an RPC error | Check request XML against the tool's template. `requestUniqueID` must be a fresh GUID. |
| Simulator transfer reports `Family check failed` | Complete the GUI seed transfer described under [PLC and simulator access](#plc-and-simulator-access). |
| Manuals are unavailable or stale | Check the corpus path with `get_documentation_status`, then rerun the required conversion/indexing step. |

Report reproducible bugs through [GitHub Issues](https://github.com/PBrunot/control-expert-mcp/issues). Include Python and Control Expert versions, CPU/firmware when relevant, the tool sequence, and sanitized errors. Exclude customer projects, credentials, and proprietary exports.

## Development and validation

### Repository layout

```text
src/control_expert_mcp/  MCP tools, COM bridge, Modbus access, schemas, prompts,
                        language references, documentation service, and benchmarks
samples/                MCP client configuration examples
tools/                  Diagnostics, offline tests, help conversion, and integration scripts
benchmarks/             Benchmark setup, checkpoints, and archived results
.github/workflows/      CI and package publishing
```

The DDT Mirror application has moved to a separate repository.

### Offline checks

```powershell
.venv\Scripts\python.exe -m pip install -e ".[test]"
.venv\Scripts\python.exe -m compileall -q src
.venv\Scripts\python.exe -m unittest discover -s tools -p "test_*.py"
```

[CI](.github/workflows/ci.yml) runs offline regression tests on Windows with Python 3.11–3.15, validates distributions, and tests the installed wheel in an isolated environment. These checks use synthetic documentation and mocked COM responses; they do not validate licensed COM integration or PLC runtime behavior.

### Local Control Expert validation

Review scripts before running them. Integration workflows can modify projects or terminate Control Expert processes.

```powershell
.venv\Scripts\python.exe tools/check_ce_automation.py
# Optional: create, build, export, reopen, and delete a disposable offline project.
.venv\Scripts\python.exe tools/check_ce_automation.py --exercise-project --report tmp/automation-check.json
```

The automation check does not connect to a PLC. The default scratch CPU is M340 `BMX P34 2020` / `02.70`; override `--cpu` and `--cpu-version` for your installed catalog.

Recorded local validation includes Control Expert 16.4 with an M340 scratch-project round trip and an offline M580 `BME P58 3040` / `03.20` demo check. The M580 check exercised analyze/build, an intentional undefined-symbol diagnostic, cleanup back to `built_ok`, and unchanged-output detection. These are environment-specific results, not a guarantee for every CPU or installation.

### Architecture and extension rules

- Keep all COM calls on the bridge's dedicated STA worker thread.
- Preserve session write-token handling. The bridge acquires and caches the project's write token once per session.
- Hardware and DTM automation use secondary COM interfaces; preserve the bridge's interface-query helpers.
- Exchange-file extensions must match XML roots because Control Expert selects import parsers by extension.
- Shared Modbus calls are serialized across concurrent MCP handlers.

See [bridge.py](src/control_expert_mcp/bridge.py), [schema.py](src/control_expert_mcp/schema.py), and [constants.py](src/control_expert_mcp/constants.py) for implementation details.

### Optional model benchmarks

The `ce-bench` CLI compares server revisions or manual-tool availability using configured OpenAI or DeepSeek API models. Provider packages and API calls are optional; normal server operation needs no provider key.

See the [benchmark guide](benchmarks/README.md), [validation checkpoint](benchmarks/CHECKPOINT.md), and [archived results](benchmarks/archive/README.md). Static artifact checks do not establish PLC runtime behavior, and API results do not reproduce ChatGPT UI orchestration.

## Packaging and releases

Build and validate distributions from the repository root using a fresh output directory:

```powershell
.venv\Scripts\python.exe -m pip install build twine
.venv\Scripts\python.exe -m build --outdir dist/0.9.0
.venv\Scripts\python.exe -m twine check --strict dist/0.9.0/*
.venv\Scripts\python.exe tools/check_distribution.py --dist-dir dist/0.9.0
```

Use the version declared in `pyproject.toml` when choosing the output directory. The wheel contains the runtime package; the source archive includes selected tools and samples listed in `MANIFEST.in`. The archive audit rejects unexpected content, including customer projects, generated manuals, and vendor extracts.

Successful CI runs retain a `python-distributions` artifact for 14 days. To install a downloaded wheel in a dedicated environment:

```powershell
py -3.11 -m venv C:\Tools\control-expert-mcp
C:\Tools\control-expert-mcp\Scripts\python.exe -m pip install .\control_expert_mcp-0.9.0-py3-none-any.whl
```

Use the actual downloaded filename, then point your client to that environment's Python executable. Disconnected installations also need a compatible dependency wheelhouse prepared on a connected Windows machine.

The [publish workflow](.github/workflows/publish.yml) reruns CI and uploads validated artifacts using PyPI Trusted Publishing with GitHub OIDC:

1. Update the version in `pyproject.toml` and let CI pass.
2. Create the matching `v<version>` tag and publish a GitHub Release for it.
3. Verify publication and installation in a clean environment.

Production publishing requires a tag matching the wheel version. Manual workflow dispatch defaults to TestPyPI; its publisher must be configured separately. Jobs use the `pypi` or `testpypi` GitHub environment. Published version filenames cannot be reused.

## Contributing

Bug reports, documentation improvements, and focused pull requests are welcome.

1. Describe the problem or intended behavior in an issue or pull request.
2. Follow the existing Python style: four-space indentation, type hints for public helpers, and concise docstrings.
3. Add or extend an MCP prompt for each new capability, including the validated tool sequence, prerequisites, and known gotchas.
4. Update the README tool reference when capabilities change.
5. Run the relevant offline checks and document local integration validation when available: CPU, Control Expert version, prerequisites, commands, and results. State any environment limitations.

Use concise, descriptive commit subjects. Keep customer exports, proprietary reference data, vendor binaries, generated archives, and credentials out of commits. See [AGENTS.md](AGENTS.md) for repository conventions.

## License and affiliation

The package declares the **MIT** license in [pyproject.toml](pyproject.toml).

This project is not affiliated with or endorsed by Schneider Electric. Control Expert and Unity Pro are Schneider Electric products; their software, licenses, and documentation are supplied separately.
