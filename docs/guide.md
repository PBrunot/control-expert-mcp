# Configuration and usage guide

[English README](../README.md) · [README italiano](../README.it.md)

## MCP client configuration

Examples use the PyPI command `control-expert-mcp`. Source installs: absolute `.venv\Scripts\python.exe` with args `-m control_expert_mcp`. Start with online access off.

```json
{
  "mcpServers": {
    "control-expert": {
      "command": "control-expert-mcp",
      "args": [],
      "env": { "CE_MCP_ENABLE_ONLINE": "0" }
    }
  }
}
```

| Client | Notes |
| --- | --- |
| Claude Desktop | Add the block above to `%APPDATA%\Claude\claude_desktop_config.json` ([sample](../samples/claude_desktop_config.json)). |
| Claude Code | Plugin (server + workflow skill, needs uv): `/plugin install control-expert --marketplace PBrunot/control-expert-mcp`. Manual: `claude mcp add control-expert -- control-expert-mcp`. |
| VS Code / Copilot | `.vscode/mcp.json`, top-level key `servers`, add `"type": "stdio"` ([sample](../samples/vscode-mcp.json)). |
| OpenAI Codex CLI | `codex mcp add control-expert --env CE_MCP_ENABLE_ONLINE=0 -- control-expert-mcp` (writes `%USERPROFILE%\.codex\config.toml`; loads [AGENTS.md](../AGENTS.md)). |
| DeepSeek Harness (DSH) | In `%USERPROFILE%\.dsh\profiles\<profile>\cordis.patch.yml`, `insert` a row `id: mcp-control-expert`, `name: '@deepseek-ai/dsh-mcp-client'`, `config: {serverName: control-expert, transport: stdio, command: control-expert-mcp, args: [], env: {...}}`. DSH scrubs the environment, so list every needed `CE_MCP_*` variable in `env`. Check with `dsh --profile web --dump-config`. |

Environment variables:

| Variable | Purpose |
| --- | --- |
| `CE_MCP_ENABLE_ONLINE=1` | Exposes PLC/OPC/Modbus tools. Does not grant consent. |
| `CE_MCP_MANUALS_DIR` | Absolute path to the converted manual corpus. |
| `CE_MCP_SCHEMA_DIR` | Explicit XSD schema folder for `validate_xml`. |
| `CE_MCP_SIMULATOR_EXE` | Simulator executable for custom layouts or startup without an open project. |
| `CE_MCP_OPC_PYTHON` | 32-bit Python with `pywin32` that hosts the OPC helper. |

## Usage

Work on a disposable project or a copy.

### Authoring logic

ST (MCP tool arguments, not Python):

```text
write_st_logic(task="MAST", section="MotorControl",
    st_source="MotorRun := StartButton AND NOT StopButton;",
    declare="StartButton:BOOL, StopButton:BOOL, MotorRun:BOOL")
build_project()
```

- `write_st_logic` creates the section or replaces its whole body.
- LD/FBD/SFC/IL: read `get_language_reference`, export a similar object (`export_xml`/`read_section`), check with `validate_xml`, then `import_xml`. Declare variables first or include them in the XML.
- Imports can replace existing sections. Build, inspect, and save explicitly. `close_project` discards changes unless `save=true`.

### Build results

- An empty diagnostic list does **not** prove a clean build. Check `build_state`, `error`, raw output and `diagnostics_summary` together.
- E1061 (undefined symbol) diagnostics add `undefined_symbol` and `candidates`: declared variables ranked by name similarity, with types. Pick by type and context; never replace the symbol with a constant or declare a dummy variable to hide the error.
- **Builds while connected are online changes** applied to the running target. `build_project` refuses them unless `allow_online_change=true`, which also needs closed-loop approval in `configure_live_access`. Otherwise call `plc_disconnect` first. Connected builds return `online_change_applied` and `target_after_build`; earlier runtime evidence no longer applies.

## Tool reference

Defined in [server.py](../src/control_expert_mcp/server.py); clients show full argument schemas.

| Area | Tools |
| --- | --- |
| Project lifecycle | `get_status`, `open_project`, `new_project`, `save_project`, `close_project`, `export_project` |
| Build and settings | `analyze_project`, `build_project`, `get_project_setting`, `set_project_settings` |
| Project structure | `get_project_structure`, `create_task`, `create_section`, `delete_section`, `read_section` |
| Logic authoring | `write_st_logic`, `get_language_reference`, `place_fb_in_ladder`, `use_fb_in_ladder` |
| Exchange XML | `validate_xml`, `import_xml`, `export_xml` |
| Variables and types | `list_variables`, `create_variable`, `update_variable`, `delete_variable`, `list_data_types` |
| Hardware | `get_hardware`, `add_io_module`, `remove_io_module`, `replace_io_module`, `add_drop`, `add_rack`, `replace_rack`, `change_cpu` |
| DTM topology | `list_dtms`, `add_dtm`, `delete_dtm`, `set_dtm_address` |
| DTM configuration | `get_dtm_control_parameters`, `set_dtm_control_parameters`, `get_dtm_dataset`, `set_dtm_dataset`, `get_master_dtm_dataset`, `set_master_dtm_dataset` |
| Ethernet and networks | `configure_cpu_ethernet`, `list_networks`, `add_network`, `set_network_ip` |
| Animation tables and UI | `list_animation_tables`, `create_animation_table`, `delete_animation_table`, `show_ui`, `open_animation_table` |
| Simulator process | `get_simulator_status`, `start_simulator`, `stop_simulator` |
| Local manuals | `get_documentation_status`, `search_manuals`, `get_manual_topic` |
| Live session setup (always available) | `get_live_access_setup`, `configure_live_access` |
| PLC connection (opt-in) | `plc_setup_connection`, `plc_connect`, `plc_disconnect`, `plc_state`, `plc_transfer`, `plc_command` |
| OPC symbolic values (opt-in, preferred) | `opc_connect`, `opc_disconnect`, `opc_status`, `opc_browse`, `opc_read_tags`, `opc_write_tags` |
| Modbus located values (opt-in) | `modbus_connect`, `modbus_disconnect`, `modbus_status`, `read_tags`, `write_tags` |

Notes:

- `export_project` falls back from `.xef` to `.zef` when required (e.g. M580); use the returned `exported` path.
- Modbus scan requests live in the master dataset's `ManagedModbusRequestList`; follow the `set_master_dtm_dataset` template (fresh `requestUniqueID` GUID).
- `place_fb_in_ladder` generates pin geometry for project DFBs; `use_fb_in_ladder` copies a template section (elementary blocks, exact GUI geometry).

## Guided workflows

Prompts in [prompts.py](../src/control_expert_mcp/prompts.py); pick them in the client. Tool descriptions already carry the essential rules.

| Prompt | Workflow |
| --- | --- |
| `scaffold_project` | Create a project with exact CPU/catalog versions, configure hardware, build, save. |
| `author_logic` | Read the language reference, author/import logic, build, fix errors. |
| `fb_in_ladder` | Place a function block in Ladder and bind its pins. |
| `add_modbus_device` | Add a Modbus TCP slave DTM and a scan request. |
| `export_project_backup` | Export the application to XEF/ZEF offline. |
| `inspect_project_archive` | Open and inspect a `.sta` archive offline. |
| `commission_simulator` | Build, start simulator, connect, transfer, run. |
| `setup_live_access` | Obtain consent, prefer OPC, record the OFS alias, approve closed loop separately. |
| `test_logic_opc` | Test symbolic variables (including DFB/array members) through OFS. |
| `test_logic_live` | Test located values over Modbus, with mirrors for DFB internals. |
| `consult_installed_manuals` | Search, retrieve, and cite local manuals. |
| `benchmark_training_project`, `iec_benchmark_workflow`, `benchmark_opc_live`, `benchmark_simulator_counter` | Benchmark workflows; see [benchmarks/README.md](../benchmarks/README.md). |

Runtime tests: define inputs, expected outputs and deadlines; report pass/fail/unverified; restore inputs.

## PLC and simulator access

Safety rules:

- Live tools are hidden by default. `CE_MCP_ENABLE_ONLINE=1` (then restart) only exposes them; every server process starts with live access blocked.
- Call `get_live_access_setup` first, then record the user's choices with `configure_live_access`: live or offline, protocol `opc` (preferred), `modbus`, or `engineering`, and the OFS alias for OPC.
- Closed-loop writes, transfers and PLC commands need explicit user approval (`allow_closed_loop=true`); OPC also needs `opc_server_confirmed_running=true`.
- No automatic protocol fallback. Setup lasts for the process; changing it disconnects. Revoke with `configure_live_access(allow_live_connection=false)`.

```text
configure_live_access(allow_live_connection=true, protocol="opc",
    ofs_alias="Dev_Alias_2", opc_server_confirmed_running=true, allow_closed_loop=true)
```

Use `allow_closed_loop=false` for read-only sessions. For a simulator download without tag access: `configure_live_access(allow_live_connection=true, protocol="engineering", allow_closed_loop=true)`.

### Simulator

- Simulator path: open Control Expert's `InstallationPath`, else `CE_MCP_SIMULATOR_EXE`.
- `get_simulator_status` works offline: `simulator_running` is process presence; `plc_state` needs an engineering connection, else `unknown`. `pc_equals_plc=true` means the deployed application matches.

Commissioning (see the `commission_simulator` prompt):

1. `build_project` and confirm `build_state="built_ok"`.
2. `start_simulator`.
3. `plc_setup_connection(target="simulator", address="127.0.0.1")`, then `plc_connect(target="simulator")`.
4. If not `no_conf`, `plc_command(command="stop")` and require STOP; then `plc_transfer(direction="pc_to_plc")`.
5. `plc_command(command="run")` and check `plc_state`.

> [!IMPORTANT]
> On **"Family check failed"**, seed the controller family once in the GUI: PLC → Simulation Mode → Connect → Transfer. Only needed when that error occurs.

Integration check (replaces the simulator application; report in `tmp/simulator-check.json`):

```powershell
python tools/check_simulator.py --approve-download --cold-start --verify-run
```

### OPC DA through OFS (symbolic, preferred)

- Expected setup: OFS connected to PLC Simulator, default alias `Dev_Alias_2` (`MBT:127.0.0.1/U`, M580) with `UsingDataDic` and `UnlocatedSupport` enabled.
- In **Project Settings → General → PLC embedded data**, enable **Data dictionary** and clear **Only HMI variables** (needed to write non-HMI variables). Rebuild and download after changes.
- `OPC.Automation` and its Python host must have matching bitness. A 64-bit server can use a 32-bit Python via `CE_MCP_OPC_PYTHON` with `pywin32`. Sample: [samples/opc-mcp.json](../samples/opc-mcp.json).

```text
opc_connect()
opc_browse(branches=["Dev_Alias_2", "Forming_motor"])
opc_read_tags(tags=["Start", "Forming_motor.running_left"])
opc_write_tags(values={"name": value})
opc_disconnect()
```

- Use short names or browsed `alias!symbol` IDs; page with `next_offset`.
- Reads drop bad/uncertain samples. Writes need canonical scalar types.
- A write acknowledgement does not mean the value held; observe outputs and restore inputs. Timeouts disconnect and are never retried.

Validation (needs a running demo and approval of reversible tests; omit `--exercise-demo` to browse only):

```powershell
.venv\Scripts\python.exe tools\check_opc.py --alias Dev_Alias_2 --allow-live --confirm-ofs-running --exercise-demo --report tmp\opc-validation.json
```

### Modbus TCP (located values)

```text
modbus_connect(host="127.0.0.1", port=502)
read_tags(tags="MotorRun, %MW0, %MW2:REAL")
write_tags(values={"%MW2:REAL": 4.0})
modbus_disconnect()
```

- Only located `%M` / `%MW` tags. Mirror unlocated DFB internals (e.g. `Pump1.Running`) to located variables first.
- Address forms: `%M3`, `%MW86`, `%MW2:REAL`, `%MW70:UDINT`, `%MW10.2`.
- 32-bit values are low word first; set `word_order="high_first"` if needed.
- Prefer OFS for the simulator.

## Searchable local manuals

Requires Windows, the help extras, and 7-Zip. From the repository root:

```powershell
.venv\Scripts\python.exe -m pip install -e . -r tools/requirements-help.txt
.venv\Scripts\python.exe tools/export_ce_help.py --list
.venv\Scripts\python.exe tools/export_ce_help.py --languages en --jobs 4
.venv\Scripts\python.exe tools/index_ce_help.py --manuals-dir manuals/ce-16.4
```

- Defaults: Control Expert 16.4 install folder in `Program Files (x86)`, output `manuals/ce-16.4`. Options: `--install-dir`, `--output`, `--languages`, `--include`, `--force`.
- Wheel installs can index an existing corpus: `python -m control_expert_mcp.documentation --manuals-dir C:\path\to\manuals\ce-16.4`.
- Set `CE_MCP_MANUALS_DIR` to the absolute corpus path.
- Use `get_documentation_status`, `search_manuals(query="TON")`, then `get_manual_topic(topic_id=...)`; follow `next_cursor` until null.
- MCP calls never convert, index, or download. Stale indexes are refused; rerun conversion/indexing after updates.
- No OCR. Generated manuals and indexes stay local and out of Git.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| COM broker creation fails | Check Control Expert installation and license; repair if COM registration is broken. |
| `Catalog object not found` or missing module | Match part number, spacing, and version exactly, e.g. `BMX P34 2020` / `02.70`. |
| `new_project` returns bare `Exception occurred` | Try the CPU in the GUI to check licensing and libraries. |
| Write access reserved by another client | Close the project in the other writable session. |
| First operation is slow | 30–120 s is normal; raise the client timeout. |
| XML import reports `Invalid file` | Mirror an exported object's schema; run `validate_xml` first. |
| DTM protocol ID invalid | Use the exact catalog name (e.g. `Modbus Device`) and protocol `Modbus`; see `tools/list_dtm_catalog.py`. |
| Master DTM dataset RPC error | Check XML against the tool template; `requestUniqueID` must be a fresh GUID. |
| `build_project` refuses while connected | Online change: disconnect, or approve closed loop and pass `allow_online_change=true`. |
| Manuals unavailable or stale | Check `get_documentation_status`; rerun conversion/indexing. |

Report bugs via [GitHub Issues](https://github.com/PBrunot/control-expert-mcp/issues) with versions, tool sequence, and sanitized errors; never attach customer projects.

## Development and validation

Offline checks:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[benchmark,test]"
.venv\Scripts\python.exe -m compileall -q src
.venv\Scripts\python.exe -m unittest discover -s tools -p "test_*.py"
```

[CI](../.github/workflows/ci.yml) runs these with mocked COM on Python 3.11–3.15.

Local Control Expert check (no PLC; review first, it can modify projects or kill Control Expert):

```powershell
.venv\Scripts\python.exe tools/check_ce_automation.py
.venv\Scripts\python.exe tools/check_ce_automation.py --exercise-project --report tmp/automation-check.json
```

Override the scratch CPU with `--cpu` and `--cpu-version`.

Extension rules: keep COM on the bridge's STA worker, preserve write-token handling, and match exchange-file extensions to XML roots.

Benchmarks (`ce-bench`, optional API providers): see the [benchmark guide](../benchmarks/README.md), [checkpoint](../benchmarks/CHECKPOINT.md) and [archive](../benchmarks/archive/README.md).

## Packaging and releases

```powershell
.venv\Scripts\python.exe -m pip install build twine
.venv\Scripts\python.exe -m build --outdir tmp/release-check
.venv\Scripts\python.exe -m twine check --strict tmp/release-check/*
.venv\Scripts\python.exe tools/check_distribution.py --dist-dir tmp/release-check
```

Use a fresh output directory. The audit rejects customer projects, generated manuals, and vendor extracts. CI keeps wheels as the `python-distributions` artifact for 14 days.

Release ([publish workflow](../.github/workflows/publish.yml), PyPI Trusted Publishing):

1. Set the version in `pyproject.toml`; let CI pass.
2. Tag `v<version>` and publish a GitHub Release.
3. Verify installation in a clean environment.

Manual dispatch targets TestPyPI. Published version numbers cannot be reused.
