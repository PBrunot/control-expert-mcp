# Control Expert MCP Server

[![CI](https://github.com/PBrunot/control-expert-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/PBrunot/control-expert-mcp/actions/workflows/ci.yml)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-blue)
![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)

Connect MCP clients to a local **EcoStruxure Control Expert** (formerly **Unity Pro**) installation. Inspect, create, edit, and build PLC projects through Schneider Electric's Unity Developer's Edition (UDE) COM automation API.

This is an **experiment**, forked from the earlier [apexsotjo-blip/control-expert-mcp project on GitHub](https://github.com/apexsotjo-blip/control-expert-mcp). It explores LLM-assisted PLC programming and debugging; the benchmark results are exploratory.

[Install from PyPI](https://pypi.org/project/control-expert-mcp/) · [Benchmark overview image](https://github.com/PBrunot/control-expert-mcp/blob/main/benchmarks/archive/overview.png) · [Benchmark methods and commands](benchmarks/README.md)

```text
MCP client ── stdio ──> control-expert-mcp ── COM ──> Control Expert
                                         ├─ OFS OPC DA ──> PLC Simulator (opt-in, preferred)
                                         └─ Modbus TCP ──> PLC (opt-in)
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

Opening `.sta` restores the archive into an unsaved application using UDE `OpenArchive`;
use `save_project` with an explicit `.stu` path for the working copy.
Before COM activation, the bridge restores missing Windows `CommonProgramFiles`,
`CommonProgramFiles(x86)` and `CommonProgramW6432` paths from the registry. MCP
launchers may strip these variables, causing PServer startup to fail its integrity
check even though desktop Control Expert works. An already running broker retains
its launch environment and must be restarted after correcting these paths.
- **Program authoring:** inspect and edit ST, LD, FBD, SFC, and IL sections. Write ST directly or import Control Expert exchange XML for graphical languages, variables, DFBs, and DDTs.
- **Hardware configuration:** inspect buses, drops, racks, and modules; add, replace, or remove supported hardware; change the CPU.
- **Communications:** manage DTMs, device addresses, M580 Modbus scan requests, CPU Ethernet services, and Premium/Quantum logical networks.
- **Validation:** check exchange XML against installed schemas, analyze and build projects, and retrieve build diagnostics.
- **Documentation:** search locally converted vendor manuals and retrieve topics with source citations, without opening Control Expert.
- **Monitoring and commissioning:** open animation tables and, after explicit session setup, read/write symbolic variables through OFS OPC DA, including exposed unlocated variables and DFB members. Modbus TCP remains available for located tags.

Availability depends on the installed Control Expert version, license, hardware catalog, and DTM libraries.

## Requirements

| Requirement | Details |
| --- | --- |
| Operating system | Windows for Control Expert COM automation |
| Python | 3.11 or newer, as declared in `pyproject.toml` |
| Control Expert | Licensed local installation of EcoStruxure Control Expert or Unity Pro; validated with versions 14.0 and 16.4 |
| Automation interface | Registered UDE COM broker (`PSBroker.PServerBroker.1`) |
| MCP client | A client supporting stdio servers, such as Claude Desktop, Claude Code, VS Code with GitHub Copilot, OpenAI Codex CLI, or DeepSeek Harness (DSH) |

Run the server on the **same machine as Control Expert**. DCOM remoting is not configured. The UDE automation server ships with Control Expert; the separate UDE package is only needed for its documentation. Python dependencies are installed with the package.

## Quick start

### Install from PyPI (recommended)

On the Windows machine with Control Expert installed, run:

```powershell
py -3.11 -m pip install --upgrade control-expert-mcp
```

No Git checkout is required. Configure your MCP client to launch `control-expert-mcp` with no arguments, as shown below. The installed console command starts the stdio server; the MCP client normally manages that process. If the client cannot find the command on its PATH, use the absolute path to the installed executable, or to the same Python interpreter with arguments `["-m", "control_expert_mcp"]`.

### Install from source

For development, clone the repository and install into a virtual environment:

```powershell
git clone https://github.com/PBrunot/control-expert-mcp.git
cd control-expert-mcp
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

For a source installation, configure your MCP client with the absolute path to `.venv\Scripts\python.exe` and arguments `["-m", "control_expert_mcp"]`.

To launch the stdio server manually:

```powershell
.venv\Scripts\python.exe -m control_expert_mcp
```

The installed `control-expert-mcp` console command is equivalent. This is a stdio service; an MCP client normally starts and manages the process.

## MCP client configuration

These examples use the PyPI-installed console command. Keep online access disabled for initial setup. The files in `samples/` also show absolute Python paths for source installations.

### Claude Desktop

Add this entry to `%APPDATA%\Claude\claude_desktop_config.json`. A copy is available in [samples/claude_desktop_config.json](samples/claude_desktop_config.json).

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

### Claude Code

```powershell
claude mcp add control-expert -- control-expert-mcp
```

Online access remains disabled unless the server inherits an enabling environment variable.

### VS Code / GitHub Copilot

Add the server to `.vscode/mcp.json`. See [samples/vscode-mcp.json](samples/vscode-mcp.json).

```json
{
  "servers": {
    "control-expert": {
      "type": "stdio",
      "command": "control-expert-mcp",
      "args": [],
      "env": {
        "CE_MCP_ENABLE_ONLINE": "0"
      }
    }
  }
}
```

### OpenAI Codex CLI

Codex reads stdio servers from `%USERPROFILE%\.codex\config.toml` (or the directory named by `CODEX_HOME`). Register the server once:

```powershell
codex mcp add control-expert --env CE_MCP_ENABLE_ONLINE=0 -- control-expert-mcp
codex mcp list
```

The command writes the equivalent TOML, which can also be edited by hand:

```toml
[mcp_servers.control-expert]
command = "control-expert-mcp"

[mcp_servers.control-expert.env]
CE_MCP_ENABLE_ONLINE = "0"
```

For a source installation, set `command` to the absolute `.venv\Scripts\python.exe` path and add `args = ["-m", "control_expert_mcp"]`. Remove the entry with `codex mcp remove control-expert`.

Codex loads `AGENTS.md` from the repository root and its parent directories, so this repository's [AGENTS.md](AGENTS.md) applies without extra configuration. State which `.stu` to work on in the prompt; project state belongs to the server session, not to Codex's working directory. The first operation on a large project can take 30–120 seconds, so raise the client's tool timeout when a call is cut short (see [Troubleshooting](#troubleshooting)).

### DeepSeek Harness (DSH)

DSH composes every capability as a plugin row, so each MCP server is one `@deepseek-ai/dsh-mcp-client` row. Add it to a profile's user patch layer — `%USERPROFILE%\.dsh\profiles\<profile>\cordis.patch.yml`, or `%USERPROFILE%\.dsh\cordis.patch.yml` to apply it to every profile. Both files are a top-level YAML array of patch entries; an entry carrying an `insert` list appends rows:

```yaml
- insert:
    - id: mcp-control-expert
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: control-expert
        transport: stdio
        command: control-expert-mcp
        args: []
        env:
          CE_MCP_ENABLE_ONLINE: '0'
```

`serverName` namespaces the tools, which reach the model as `mcp__control-expert__<tool>`, for example `mcp__control-expert__open_project`. The client launches the server with a scrubbed environment, so every variable the server needs — `CE_MCP_ENABLE_ONLINE`, `CE_MCP_OPC_PYTHON`, `CE_MCP_MANUALS_DIR`, `CE_MCP_SCHEMA_DIR` — must be declared in `env`. For a source installation, set `command` to the absolute `.venv\Scripts\python.exe` path with `args: ['-m', 'control_expert_mcp']`.

Check the composed tree without booting it:

```powershell
dsh --profile web --dump-config
```

The `mcp-control-expert` row appears in the dump, and the tool list exposes the `mcp__control-expert__` entries at session start. A row that never activates is reported at boot. The package ships with `dsh`; if a profile cannot resolve it, install it with `dsh plugin --profile web add @deepseek-ai/dsh-mcp-client`. DSH also loads this repository's [AGENTS.md](AGENTS.md) as workspace instructions.

## Configuration

Set environment variables in the MCP client's server configuration so they reach the server process.

| Variable | Default | Purpose |
| --- | --- | --- |
| `CE_MCP_ENABLE_ONLINE` | Disabled | Set to `1` to register `plc_*`, `opc_*`, `modbus_*`, `read_tags`, and `write_tags`. Session setup and user approval are still required. Restart after changing it. |
| `CE_MCP_OPC_PYTHON` | Server Python | Python executable matching the installed OPC Automation DLL bitness, with `pywin32` installed. Usually a separate 32-bit Python for OFS. |
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

`export_project` retries an unsupported `.xef` export as `.zef` when Control Expert
requires it (for example, M580). Use the returned `exported` path. ZEF is a ZIP
archive containing `unitpro.xef` and DTM data. An existing fallback `.zef` is
protected; choose a new basename or explicitly request that `.zef` path to replace
it. The `export_project_backup` prompt describes this offline workflow.

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
| Simulator process and PLC execution state | `get_simulator_status`, `start_simulator`, `stop_simulator` |
| Local manuals | `get_documentation_status`, `search_manuals`, `get_manual_topic` |
| Live session setup (always available) | `get_live_access_setup`, `configure_live_access` |
| PLC connection **(opt-in)** | `plc_setup_connection`, `plc_connect`, `plc_disconnect`, `plc_state`, `plc_transfer`, `plc_command` |
| Symbolic live values **(opt-in, preferred)** | `opc_connect`, `opc_disconnect`, `opc_status`, `opc_browse`, `opc_read_tags`, `opc_write_tags` |
| Modbus live values **(opt-in)** | `modbus_connect`, `modbus_disconnect`, `modbus_status`, `read_tags`, `write_tags` |

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
| `setup_live_access` | Obtain session consent, prefer OPC, record the OFS alias, and separately approve closed-loop operation. |
| `test_logic_opc` | Browse and debug symbolic variables, including exposed unlocated variables and DFB/array members, through OFS. |
| `test_logic_live` | Test located values over Modbus, including mirrors for unlocated DFB internals. |
| `consult_installed_manuals` | Prepare, search, retrieve, and cite local documentation. |
| `benchmark_training_project` | Run the offline benchmark training workflow. |

## PLC and simulator access

Set `CE_MCP_ENABLE_ONLINE=1` in the server environment and restart it to expose online tools. This only makes the tools available; every server process starts with live access blocked.

Simulator startup uses the open Control Expert/Unity Pro application's
`InstallationPath`, so the executable follows that installation rather than a
hard-coded release or product folder name. For custom layouts or startup without
an open project, set `CE_MCP_SIMULATOR_EXE` to the matching simulator executable.
The server does not automatically fall back to another installed release.

Before live work, the LLM is instructed to call `get_live_access_setup`, reuse recorded user choices, and collect any missing choices: offline or live access, OPC (preferred) or Modbus, and the OFS device alias for OPC. Before closed-loop writes or PLC control, the user must explicitly approve that mode and confirm OFS is available and running for OPC. `configure_live_access` records these answers; the server enforces them before connecting, reading, writing, transferring, or issuing PLC commands. There is no automatic protocol fallback. Configuration lasts for the server process; restarting requires setup again. Changing setup disconnects existing connections. Cleanup and status calls remain available. MCP instructions guide the conversation; client support determines how the questions are displayed.

For example, **after** the user approves OPC connections, confirms the alias and running OFS, and approves closed-loop tests:

```text
configure_live_access(allow_live_connection=true, protocol="opc",
    ofs_alias="Dev_Alias_2", opc_server_confirmed_running=true, allow_closed_loop=true)
```

Use `allow_closed_loop=false` for read-only sessions. To revoke live access, call `configure_live_access(allow_live_connection=false)`. Tool arguments attest to answers obtained by the client; the server cannot independently authenticate a conversational user confirmation.

For an explicitly approved simulator download without live tag access, use
`configure_live_access(allow_live_connection=true, protocol="engineering", allow_closed_loop=true)`.
This enables engineering connections and deployment without requiring OFS; OPC
and Modbus tag access remain blocked. Configure those separately if requested.

`get_simulator_status` is available offline and does not start or connect anything.
It distinguishes `simulator_running` (the process exists) from `plc_state`
(`run`, `stop`, `no_conf`, `halt`, `default`, or `unknown`). PLC state is observed
only through an existing engineering connection with the simulator selected.
Otherwise it reports `unknown` and a reason, never an assumed STOP or RUN.
`pc_equals_plc=true` identifies a matching deployed application; process presence
alone proves neither deployment nor execution.

Use the `commission_simulator` prompt for the complete commissioning procedure.

The commissioning sequence is:

1. Build the project and confirm `build_state="built_ok"`.
2. Launch the simulator with `start_simulator` or the installed `PLC_Simulator\sim.exe`.
3. Configure `plc_setup_connection(target="simulator", address="127.0.0.1")` and call `plc_connect(target="simulator")`.
4. Inspect state: an empty `no_conf` simulator has nothing to stop. Otherwise call `plc_command(command="stop")` and require STOP before `plc_transfer(direction="pc_to_plc")`.
5. Call `plc_command(command="run")` and inspect `plc_state`.

> [!IMPORTANT]
> If an API download reports **“Family check failed,”** seed the matching controller family once through the Control Expert GUI: PLC → Simulation Mode → Connect → Transfer. Use this workaround only when that error occurs; an empty simulator can accept an initial API download directly.

Validated on 2026-11-23 with Control Expert 16.4 and the M580 demo, CPU
`BME P58 3040` version `03.20`: the stdio MCP sequence opened and fully rebuilt
the demo, launched a closed simulator, connected in `no_conf`, and downloaded
directly to STOP with `pc_equals_plc=true`. Build reported zero errors and one
gateway network warning. This verifies deployment, not functional process logic.

Repeat the local integration check from the repository root:
`python tools/check_simulator.py --approve-download --cold-start --verify-run`.
It replaces the simulator application, verifies closed/empty/STOP/RUN state
reporting, returns the PLC to STOP, and records version, diagnostics and results
in `tmp/simulator-check.json`. It never saves the source project. Omit
`--verify-run` for download-only validation or `--cold-start` to reuse the process.

### Symbolic live values through OFS OPC DA

The expected testing environment is a running **OFS server connected to PLC Simulator**. The default test device alias is **`Dev_Alias_2`**, configured for `MBT:127.0.0.1/U` (M580), with dictionary use (`UsingDataDic`) and unlocated support (`UnlocatedSupport`) enabled. Confirm this alias and that OFS is available/running during session setup; another alias may be explicitly selected.

The UDE COM API exposes the project database. OFS provides symbolic live access using the application's built/downloaded data dictionary. In Control Expert **Project Settings → General → PLC embedded data**, enable **Data dictionary** and clear **Only HMI variables** so the dictionary includes **non-HMI variables** with write access. **Keep other variables in Read Only** is insufficient for closed-loop tests that write non-HMI inputs. Include DFB/PU private variables if those internals are needed. Build the application with these settings and download that build to PLC Simulator. Changing settings without rebuilding/downloading does not update the running application's dictionary. If the running application already exposes the required symbols, no rebuild or transfer is needed. Only exposed symbols and scalar members can be accessed; browse DFB and array branches to discover exact IDs.

The installed `OPC.Automation` DLL and its Python host must have matching bitness. A 64-bit MCP server can use a separate 32-bit Python with `pywin32` through `CE_MCP_OPC_PYTHON`. For a normal installed 32-bit Python, install its dependency using `<32-bit-python.exe> -m pip install pywin32`. The helper script is shipped as Python source with this package; it does not require MCP installed in the helper interpreter. COM objects stay on the helper's single STA thread. No registry changes or UDE write token are needed.

See [samples/opc-mcp.json](samples/opc-mcp.json) for a client configuration. Device choice and permission are collected by session setup, rather than preapproved in the environment.

After completing setup:

```text
opc_connect()
opc_browse()
opc_browse(branches=["Dev_Alias_2"])
opc_browse(branches=["Dev_Alias_2", "Forming_motor"])
opc_read_tags(tags=["Start", "Material_A", "Forming_motor.running_left"])
opc_disconnect()
```

Use the configured alias for short names or exact browsed `alias!symbol` IDs belonging to that device. Browse results are paginated with `next_offset`; `flat=true` follows server semantics and may omit nested DFB members. Reads request the device, return quality/timestamp/type/access metadata, and exclude bad/uncertain samples from `values`. `opc_write_tags(values={"name": value})` uses canonical scalar types; booleans must be JSON booleans and integers must fit their type. Write success acknowledges the request; PLC logic may overwrite values. Observe outputs separately and restore test inputs. A timeout disconnects the helper and is never automatically retried, especially for writes.

Validation on 2026-11-21 used Control Expert 16.4, M580 `BME P58 3040` version `03.20`, OFS 3.63, and the running `samples/demo_ControlExpert_M580.STU` simulator application. Alias `Dev_Alias_2` used the PLC dictionary with unlocated support enabled. A 64-bit MCP Python called the installed 32-bit Automation wrapper through a 32-bit Python 3.11.9 helper with pywin32 312. Browsing found DFB members; device reads had quality `192` (good). Writing unlocated `Measured_temp` from `0` to `1` produced `Cmeasured_temp=1.0` and `Temp_ok=false`; restoring `0` restored both derived values. No logic change, build, or download was needed. This validates the tested symbols and configuration, not every project variable or OFS release.

Reproduce only after confirming the same demo is running and approving reversible tests, with the two environment variables above set:

```powershell
.venv\Scripts\python.exe tools\test_opc.py
.venv\Scripts\python.exe tools\test_mcp_runtime.py
.venv\Scripts\python.exe tools\check_opc.py --alias Dev_Alias_2 --allow-live --confirm-ofs-running --exercise-demo --report tmp\opc-validation.json
```

Omit `--exercise-demo` to browse without writing. The report stays local. Restoration is attempted in a `finally` step and failures are reported explicitly; process termination or loss of communication can prevent restoration.

For LLM evaluation, use the separate [`ce-bench opc` benchmark](benchmarks/README.md#live-opc-readwrite-benchmark). It builds a simple program with unlocated non-HMI BOOL/INT/REAL inputs, tests model-driven symbolic reads/writes, and independently verifies the running simulator's calculated outputs. The existing offline benchmark remains offline.

### Live values over Modbus TCP

Select Modbus explicitly in session setup when using a standard Modbus TCP endpoint. Animation tables can also display values in the GUI.

Example MCP tool calls against a Modbus endpoint after setup:

```text
modbus_connect(host="127.0.0.1", port=502)
read_tags(tags="MotorRun, %MW0, %MW2:REAL")
write_tags(values={"%MW2:REAL": 4.0})
modbus_disconnect()
```

- Only **located `%M` / `%MW` tags** are reachable. Mirror unlocated DFB internals such as `Pump1.Running` to located variables in the program first.
- Use global variable names or explicit addresses, optionally with a type: `%M3`, `%MW86`, `%MW2:REAL`, `%MW70:UDINT`, or `%MW10.2` for a word bit.
- 32-bit `REAL` / `DINT` values use Schneider's low-word-first order by default. Set `word_order="high_first"` when required by the target.
- Prefer OFS for simulator access; a simulator address accepting OFS traffic does not establish support for this Modbus client.

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
.venv\Scripts\python.exe -m pip install -e ".[benchmark,test]"
.venv\Scripts\python.exe -m compileall -q src
.venv\Scripts\python.exe -m unittest discover -s tools -p "test_*.py"
```

The `benchmark` extra is required for the full suite: the provider retry tests import `openai` (and therefore `httpx`), and the archive tests render the overview image when `matplotlib` is present. Installing only `.[test]` fails those tests with `ModuleNotFoundError: No module named 'httpx'`. The same extra is needed for an installed wheel, for example `pip install "control_expert_mcp-<version>-py3-none-any.whl[benchmark,test]"`.

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

Five training tasks cover inspection, threshold edits, temperature tolerance, compile repair, and a demo-derived extension with gated low/high alarm hysteresis. Two optional read-only M580 demo tasks cover weighing reverse engineering and I/O mapping against the approved sample answer. Temperature grading accepts redundant bound parentheses; alarm grading checks a restricted ST transition model across the full INT input range and prior alarm states.

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
