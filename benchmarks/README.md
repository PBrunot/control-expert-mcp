# Local Control Expert benchmark

`ce-bench` compares MCP server configurations/revisions with one explicitly
configured provider and model ID (`openai`, `deepseek` or `claude-code`). It
measures the API client/model, not ChatGPT. Only `run` and `resume` send paid
requests; tests, `doctor`, `prepare`, `validate`, `compare`, `regrade` and
`run --dry-run` never call a provider. Results: [archive/README.md](archive/README.md).

| Suite | Command | Grading |
| --- | --- | --- |
| Offline Feeder + demo (7 tasks, A/B) | `ce-bench run` | Static/deterministic rubrics, no PLC execution |
| M580 simulator counter | `ce-bench simulator` | Independent OPC sampling of `TEST_LLM` |
| Live OPC read/write | `ce-bench opc` | Independent OPC device reads |
| Native IEC (ST/LD/FBD/SFC/IL) | `ce-bench iec` | Captured MAST traces graded through OFS |

## Setup and commands (PowerShell)

```powershell
.venv\Scripts\python.exe -m pip install -e ".[benchmark,test]"
Copy-Item benchmarks\example.json benchmarks\local.json   # or deepseek.example.json / claude-code.example.json

ce-bench doctor   --config benchmarks\local.json
ce-bench prepare  --config benchmarks\local.json
ce-bench validate --config benchmarks\local.json
ce-bench run      --config benchmarks\local.json --condition A B --repeats 5 --seed 1729 --dry-run

# PAID
ce-bench run     --config benchmarks\local.json --condition A B --repeats 5 --seed 1729
ce-bench resume  --run-id RUN_ID --config benchmarks\local.json
ce-bench compare --results benchmarks\results --output benchmarks\comparison [--rubric RUBRIC]
```

Module form: `python -m control_expert_mcp.benchmark.cli <command> ...`.
`--condition A B` interleaves both arms in a seeded randomized order (paired per
task/repetition); separate `--condition A` / `--condition B` campaigns have no
paired differences.

## Full DeepSeek suite

A **full DeepSeek suite** is the seven-task offline A/B campaign (14 cases per
repetition) followed by the M580 simulator `TEST_LLM` campaign. Run both,
sequentially, even if an offline case fails; report their acceptance separately.
Edit docs/source only after both finish (fingerprints are immutable during a campaign).

```powershell
ce-bench run --config benchmarks/local.json --condition A B --repeats 1 --seed 1729
ce-bench simulator run --config benchmarks/.local/simulator-deepseek.json --alias Dev_Alias_2 --allow-live --confirm-ofs-running --allow-closed-loop --allow-simulator-replacement --repeats 1
```

## Configuration

| Key | Notes |
| --- | --- |
| `provider` | `name` (`openai`/`deepseek`/`claude-code`), optional `api_key_env`, `api_key_file` |
| `model` | `id` (required), `identity` (`pinned`/`alias`), `reasoning_effort`, `max_output_tokens`, `temperature`, `top_p` |
| `cpu`, `ce_version` | Catalog CPU `{part_number, version}` (examples: `BMX P34 2020`, `02.70`) and Control Expert version (`16.4`) |
| `fixture`, `workspace`, `results` | Paths relative to the config file |
| `demo_project`, `io_mapping_reference` | Set together to add `weighing` and `io_mapping` |
| `tool_timeout`, `request_timeout`, `workflow_timeout`, `max_turns`, `max_tool_calls` | Positive values required |
| `conditions.<name>` | `command`, `args`, `cwd`, `env`, `documentation` (explicit boolean) |

- Credentials: `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` or an ignored `api_key_file`
  (bare `sk-...` or one labeled line). Read only by paid commands; never logged.
- DeepSeek requires `reasoning_effort` `none`/`low`/`high`/`max` and rejects
  `temperature`/`top_p`. OpenAI: send only parameters the snapshot supports.
- To compare revisions, point each condition's `command` at its own venv Python,
  `args` `["-m", "control_expert_mcp"]`, `cwd` at its checkout. The harness never
  checks out branches.
- `CE_MCP_ENABLE_ONLINE=0` is forced for offline cases. Secrets are stripped
  from child environments.
- Source tree, Git HEAD/dirty state, dependencies, corpus, schemas and prompts
  are fingerprinted; changes require a new campaign.

## Offline tasks

| Task | Rubric | Accepts |
| --- | --- | --- |
| `inspect` | `feeder-3` | Structured answer via `submit_answer`; all JSON facts correct (one whole-answer fence tolerated) |
| `threshold`, `repair` | static | Original statement sequence with exactly the prescribed change |
| `temperature` | `feeder-temperature-2` | Inclusive ABS or two-sided `Setpoint_temp +/- 2.0` predicate, rest unchanged |
| `alarms` | `feeder-alarms-2` | Hysteretic `Temp_fault_1`/`Temp_fault_2` logic proven over the whole INT domain |
| `weighing` | `demo-weighing-1` | Names `Weighing_Material_A` and `Weighing_Material_B` |
| `io_mapping` | `demo-io-mapping-6` | All 29 checks against the private reference (see [CHECKPOINT.md](CHECKPOINT.md)) |

- Unsupported but possibly valid code is **unverified**, not failed.
  `runtime_behavior` is always `unverified` offline.
- `prepare` imports `tools/lang_refs/ST_2_Feeder.xml`, builds a baseline, a
  broken repair fixture and the alarm baseline. `validate` runs canonical
  solutions through real MCP build/save/reopen without a model.
- Demo cases use read-only tools on copies of `samples/demo_ControlExpert_M580.STU`;
  the reference (`samples/demo_ControlExpert_M580_io_mapping.md`) never reaches the model.
  The required answer format is `IO_MAPPING_OUTPUT_FORMAT` in `benchmark/demo.py`.
- Conditions: **A** blocks the three manual tools; **B** adds
  `get_documentation_status`, `search_manuals`, `get_manual_topic` over a corpus
  prepared with `tools/export_ce_help.py` and `tools/index_ce_help.py`.
  Edits are limited to MAST/Feeder; no shell, filesystem or arbitrary paths.
- Evidence per attempt: `events.jsonl`, content-addressed blobs, `summary.json`,
  `final-response.txt`, `graded-answer.txt`, `validation.json`, saved project.
  Stays local.

## Claude Code CLI provider

`"provider": {"name": "claude-code"}` runs each case as one `claude -p` session:

- Uses the CLI's own login; no API key is read.
- Built-in tools off (`--tools ""`), no settings/slash commands/session
  persistence, `--permission-mode dontAsk`; server instructions are the system prompt.
- One relay MCP server (`control_expert_mcp.benchmark.claude_bridge`) forwards
  calls to the harness session, so tool policy and grading match API providers.
- `model` accepts only `id`, `identity`, `reasoning_effort` (`--effort`:
  `low`/`medium`/`high`/`xhigh`/`max`). `cost_usd` is the CLI's list-price estimate.
- The CLI version is fingerprinted; pin a frozen copy so auto-update cannot abort a campaign.

```powershell
$env:CE_BENCH_CLAUDE_EXE = "E:\GitHub\control-expert-mcp\benchmarks\.local\claude-cli\2.1.332\claude.exe"
ce-bench run --config benchmarks/.local/claude-haiku.json --condition A B --repeats 1 --seed 1729
```

[claude-code.example.json](claude-code.example.json) uses `claude-haiku-4-5-20251001`.
Haiku 4.5 results are in [archive/README.md](archive/README.md).

## M580 simulator counter benchmark

Opt-in OPC DA suite (rubric `simulator-counter-1`). The model edits a disposable
copy of `samples/demo_ControlExpert_M580.STU`: ST section `MAST/LLM`, numeric
`TEST_LLM` +1 every second (helpers `LLM_*`), build/fix/save, download, RUN.

**Acceptance:** independent OPC sampling for 8 s (100 ms poll) sees at least 6
increments of exactly +1, each interval within 0.35 s and mean period within
0.15 s of 1 s. Non-unit/negative steps, frozen counter or wrong rate fail;
bad quality or sample gaps > 0.35 s are unverified. The case must have
downloaded (or applied an online change with `pc_equals_plc`) and be in RUN.

**Safety and prerequisites:**

- Replaces the simulator's application and stops it after each case; preserve it first.
- The OFS alias must resolve to `MBT:127.0.0.1/U` (PLC Simulator), never a physical PLC.
- OFS running; `CE_MCP_OPC_PYTHON` matches the OPC Automation wrapper bitness.
- Fresh simulator or `Family check failed`: seed once with a manual CE GUI transfer.
- The model cannot write OPC values, edit other sections or save over the source.

```powershell
Copy-Item benchmarks\simulator.example.json benchmarks\.local\simulator.json
ce-bench simulator prepare --config benchmarks\.local\simulator.json
# Reference implementation, zero API requests; not LLM performance:
ce-bench simulator validate --config benchmarks\.local\simulator.json --alias Dev_Alias_2 --allow-live --confirm-ofs-running --allow-closed-loop --allow-simulator-replacement
ce-bench simulator run --config benchmarks\.local\simulator.json --alias Dev_Alias_2 --allow-live --confirm-ofs-running --allow-closed-loop --allow-simulator-replacement --dry-run
ce-bench simulator run --config benchmarks\.local\simulator.json --alias Dev_Alias_2 --allow-live --confirm-ofs-running --allow-closed-loop --allow-simulator-replacement --repeats 1
```

Evidence: `project.stu`, `saved-section.xml`, `counter-samples.json`,
`validation.json`, `summary.json`, `outcome.json`. No automatic resume; only
runs with verified cleanup can be archived.

## Live OPC read/write benchmark

Opt-in suite (rubric `opc-live-1`) against OFS + PLC Simulator, default alias
`Dev_Alias_2`, device `MBT:127.0.0.1/U`. Fixture `tools/lang_refs/OPC_Bench.xml`:
`Output = INT_TO_REAL(Input) * Gain` when enabled; only Enable/Input/Gain are
writable. Cases `positive`, `negative`, `disabled`: the model must write the
inputs and read inputs/outputs with good quality; independent OPC reads verify
values and scan-counter movement.

Prerequisites: build/download with Data dictionary enabled and Only HMI
variables cleared (non-HMI variables writable); `CE_MCP_OPC_PYTHON` with
matching pywin32 bitness; preserve the simulator application first.

```powershell
Copy-Item benchmarks\opc.example.json benchmarks\.local\opc-openai.json
ce-bench opc prepare --config benchmarks\.local\opc-openai.json
# Build/download the printed fixture to PLC Simulator manually and RUN.
ce-bench opc validate --config benchmarks\.local\opc-openai.json --allow-live --confirm-ofs-running --allow-closed-loop
ce-bench opc run --config benchmarks\.local\opc-openai.json --allow-live --confirm-ofs-running --allow-closed-loop --case positive --repeats 1
ce-bench opc run --config benchmarks\.local\opc-openai.json --allow-live --confirm-ofs-running --allow-closed-loop --repeats 1
```

`--alias` selects another alias; `run --dry-run` makes no connection. The judge
restores initial inputs; archiving requires verified restoration.

## Native IEC suite

`ce-bench iec prepare|validate|run|grade|overview`: five cases (ST/LD/FBD/SFC/IL)
on copies of the native M580 demo, rubric `iec-native-trace-1`, reporting
percentage correctness plus strict verdicts. Live commands take `--alias` and
`--allow-live --confirm-ofs-running --allow-closed-loop --allow-simulator-replacement --confirm-simulator-alias`.
See [iec.example.json](iec.example.json) and the
[IEC guide](../docs/Benchmark_IEC_Implementation.md).

## Recovery

A timed-out or disconnected CE call taints the workspace; no further CE
operations start. Confirm the operation actually stopped, then:

```powershell
ce-bench recover --config benchmarks\local.json --verified-idle
ce-bench resume  --run-id RUN_ID --config benchmarks\local.json
```

Resume skips completed cases and never replays writes. A per-user lock
serializes benchmark clients; no token stealing or process killing.

## Regrade, archive and overview

```powershell
ce-bench regrade --results benchmarks\results --run-id RUN_ID [--task inspect|io_mapping|alarms]
ce-bench archive --results benchmarks\results --run-id RUN_ID --archive benchmarks\archive [--rubric demo-io-mapping-6] [--allow-incomplete]
ce-bench visualize --archive benchmarks\archive --output benchmarks\archive\overview.png [--scoring original|latest]
```

- `regrade` makes no provider or CE calls; it verifies saved hashes and appends
  a new rubric record.
- `--rubric` writes a separate rubric snapshot; archives are immutable and
  contain no projects, transcripts, credentials or local paths.
- `overview.groups.json` joins run IDs (offline + simulator) into one display row.
- Commit archive data, `overview.png` and `overview.metadata.json` together.

## Offline checks

```powershell
python -m compileall -q src
python -m unittest discover -s tools -p "test_*.py" -v
```

These use a synthetic MCP server and scripted provider; they do not exercise
real Control Expert or paid providers.
