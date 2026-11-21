# Local Control Expert benchmark

`ce-bench` compares MCP server configurations/revisions using one explicitly
configured API provider and model ID. OpenAI and DeepSeek use separate Responses
API parameter adapters. This measures the API client/model, not ChatGPT's hidden
system prompt or orchestration. A ChatGPT subscription does not supply API access
or an API key. Only `run` and `resume` can send paid requests; tests, `doctor`,
`prepare`, `validate`, `compare`, and `run --dry-run` never call a provider.

## Live OPC read/write benchmark

`ce-bench opc` is a separate, opt-in suite. The original Feeder suite below
always forces online access off. This suite expects **OFS connected to PLC
Simulator**, default alias **`Dev_Alias_2`**, device **`MBT:127.0.0.1/U`**. The
operator must confirm OFS is available/running and approve live connections and
closed-loop tests explicitly. `CE_MCP_OPC_PYTHON` must point to a Python with
pywin32 matching the installed Automation wrapper bitness (usually 32-bit).

The application must be **built and downloaded with Data dictionary enabled
and Only HMI variables cleared**, including **non-HMI variables with write
access**. Keeping non-HMI variables read-only does not meet this requirement.
Enable OFS dictionary use and unlocated support. The fixture deliberately uses
unlocated, non-HMI BOOL/INT/REAL variables; no Modbus addresses or mirrors.

`tools/lang_refs/OPC_Bench.xml` is an original simple ST fixture: when enabled,
`Output = INT_TO_REAL(Input) * Gain`; otherwise output is zero. `Positive`
reports output > 0; `Tick` advances every scan. Only Enable/Input/Gain are
model-writable. Seeded positive, negative and disabled cases require the model
to discover/read variables, write every requested input, then read inputs and
outputs with good quality. Independent OPC device reads verify inputs, outputs
and scan-counter movement. A correct final answer or write acknowledgement
alone cannot pass. Model tool policy prevents writing calculated outputs.

```powershell
Copy-Item benchmarks\opc.example.json benchmarks\.local\opc-openai.json
# Edit model/provider, paths and CE_MCP_OPC_PYTHON. JSON paths are relative to config.
ce-bench opc prepare --config benchmarks\.local\opc-openai.json
# Open the printed native fixture in Control Expert, build/download it explicitly
# to PLC Simulator and RUN. Preserve the original simulator application first.

# No API requests; validates all live cases through the real MCP/OPC path:
ce-bench opc validate --config benchmarks\.local\opc-openai.json --allow-live --confirm-ofs-running --allow-closed-loop

# Single paid smoke case before an official campaign:
ce-bench opc run --config benchmarks\.local\opc-openai.json --allow-live --confirm-ofs-running --allow-closed-loop --case positive --repeats 1

# Official run: all three cases; repeat separately for the DeepSeek config.
ce-bench opc run --config benchmarks\.local\opc-openai.json --allow-live --confirm-ofs-running --allow-closed-loop --repeats 1
ce-bench archive --results benchmarks/results --run-id PRINTED_RUN_ID --archive benchmarks/archive
ce-bench visualize --archive benchmarks/archive --output benchmarks/archive/overview.png
```

Use `--alias` to confirm a non-default alias. `run --dry-run` makes no live
connection or API request. `prepare` builds an offline native fixture with
dictionary settings checked, but never downloads it. `validate` is scripted
feasibility validation and cannot be archived as LLM performance. Only `run`
calls a provider; credentials, Responses parameters, connection-only retry
policy, usage reporting and model identity rules match the existing adapters.
Live cases use a fresh MCP process and model conversation. The judge records
initial inputs and attempts restoration in finally, verifies calculated outputs
after restoration, and records failures. Interruption or communication loss can
prevent restoration; inspect `outcome.json`. Archive publication requires verified
restoration. Raw evidence stays ignored; sanitized archives mark this suite as
live simulator execution and are displayed separately from offline checks.

## Setup and commands (PowerShell)

From the existing checkout:

```powershell
Set-Location E:\GitHub\control-expert-mcp
.venv\Scripts\python.exe -m pip install -e ".[benchmark,test]"

# Choose ONE provider template. Customize command paths, corpus and model.
Copy-Item benchmarks\example.json benchmarks\local.json
# Or, for DeepSeek (can read the ignored repository-root .secrets):
Copy-Item benchmarks\deepseek.example.json benchmarks\local.json
notepad benchmarks\local.json

.venv\Scripts\ce-bench.exe doctor --config benchmarks\local.json
.venv\Scripts\ce-bench.exe prepare --config benchmarks\local.json
.venv\Scripts\ce-bench.exe validate --config benchmarks\local.json
.venv\Scripts\ce-bench.exe run --config benchmarks\local.json --condition A B --repeats 5 --seed 1729 --dry-run

# PAID: invoke explicitly after checking the configuration and API account.
# Set OPENAI_API_KEY or DEEPSEEK_API_KEY in this shell, or use api_key_file.
.venv\Scripts\ce-bench.exe run --config benchmarks\local.json --condition A B --repeats 5 --seed 1729
.venv\Scripts\ce-bench.exe compare --results benchmarks\results --output benchmarks\comparison
.venv\Scripts\ce-bench.exe resume --run-id YOUR_RUN_ID --config benchmarks\local.json
```

The equivalent module invocation is
`.venv\Scripts\python.exe -m control_expert_mcp.benchmark.cli <command> ...`.
The interleaved A/B command is preferred: it persists a seeded randomized order,
pairing arms within each task/repetition. Separate invocations are supported:

```powershell
.venv\Scripts\ce-bench.exe run --config benchmarks\local.json --condition A --repeats 5
.venv\Scripts\ce-bench.exe run --config benchmarks\local.json --condition B --repeats 5
```

Separate campaigns have no paired differences. Five repetitions per task is a
starter experiment, not a strong statistical conclusion. All cases start a fresh
stdio server and conversation; the report labels cold server startup. CE/OS caches
may still be warm. A controlled warm-server experiment is not implemented.

OpenAI's template requires replacing the placeholder with an accessible exact
model snapshot. Omit unsupported sampling/effort parameters: only explicitly
configured settings are sent. DeepSeek's template uses `deepseek-flash`, marked
`identity: alias`. It cannot guarantee unchanged underlying weights across time.
Use a pinned identifier if the provider offers one; a matching returned public
ID alone cannot establish this. Both arms always use the same requested model
and parameter configuration; a different returned ID terminates that case.

## Configuration and preparation

Paths in JSON (`fixture`, `workspace`, `results`, condition `cwd`, provider
`api_key_file`) resolve relative to that JSON file. Use absolute executable and
manual paths. Commands use argument lists, including paths containing spaces.
For two revisions, set each condition's `command` to its own worktree/venv Python,
`args` to `["-m", "control_expert_mcp"]`, and `cwd` to that checkout. Install each
server's dependencies beforehand. The harness never checks out branches.

The selected Python interpreter is probed for its actual package path, source
tree hash, package versions, Git HEAD and dirty fingerprint (including untracked
files). Arbitrary wrapper commands cannot be reliably probed; their source
revision remains null. The harness revision is recorded independently. Secrets
are removed from child environments; unknown environment values are hashed.
`CE_MCP_ENABLE_ONLINE=0` is enforced even if enabled by a parent or condition.
Keep credentials outside the config in the appropriate environment variable or
an ignored file. A credential file accepts one bare `sk-...` key or one labeled
line, including `Deepseek API KEY : ...`; UTF-8 and BOM-marked UTF-16 work. It is
read only for an explicitly invoked paid command. Keys/auth headers are not logged.

`doctor` discovers real MCP schemas, checks documentation status and COM registry
presence without creating a CE application. Registry presence is not proof of a
working licensed installation. It reports missing API packages/credentials and
prepared fixtures without requiring them. `run --dry-run` adds the planned
schedule, with no project mutations or API request. Missing or stale manual
prerequisites are reported; a real B campaign requires a current index.

`prepare` uses a new broker application, configurable catalog CPU/version
(`BMX P34 2020` / `02.70` by default), and imports the complete existing
`tools/lang_refs/ST_2_Feeder.xml`. It checks source and all 15 declarations,
builds, saves and reopens a native baseline. It creates a separate broken project
by replacing exactly one conversion operand with a unique undefined identifier,
then requires actual compiler error evidence before and after reopening.
Unsupported catalog entries fail through the server with actionable tool evidence.
Each preparation gets its own directory; old outputs are retained.

`validate` checks canonical threshold, temperature, repair and alarm solutions through
real MCP build/save/reopen/rebuild cycles without a model. This checks training
fixture feasibility, not API-provider behavior. Generated native projects,
exports and evidence stay under the ignored workspace.

The Feeder extract is an offline injection-molding demo attributed in its header
to Stefan Probst (07.05.2003), distributed in Schneider's Premium example;
[Schneider provenance](https://www.se.com/us/en/faqs/FA364303/). No download is
needed. Its EBOOL inputs, initial values and executable statement order are kept.
This isolated section has **no upstream process simulation**: Mixing_done,
Forming, Sec, materials and temperatures require external stimulus. The harness
does not invent a ticking Sec assignment. Threshold changes are training tasks,
not claims that Schneider's original demo is defective.

### Demo-derived alarm extension

The fifth task, `alarms`, uses a separate native copy of the same Feeder project.
Its original 15 declarations and executable statements are preserved; only this
copy predeclares `Start_process`, `Temp_fault_1` and `Temp_fault_2` as EBOOLs.
The names and 200/400 temperature trip points come from Stefan Probst's
[`LD_1_Heating.xml`](../tools/lang_refs/LD_1_Heating.xml); the associated
[`IL_0_Alarming.xml`](../tools/lang_refs/IL_0_Alarming.xml) feeds these flags into
`ALRM_DIA` instances. These are demo examples, not an original automated test suite.

The training addition appends logic after all existing Feeder statements. While
enabled, low trips at <=200 and clears at >=205; high trips at >=400 and clears
at <=395. Both flags retain their previous states in their respective deadbands.
Disabling clears both, including on the next scan after either alarm trips.
The 5-degree hysteresis and disable/reset contract are new benchmark requirements,
not behavior attributed to the original author. No `ALRM_DIA` instances, simulation
inputs, timers or new model-authored declarations are needed.

Rubric `feeder-alarms-1` accepts a restricted ST grammar: nested IF/ELSIF/ELSE,
Boolean assignments, AND/OR/NOT, parentheses and numeric comparisons of
`Cmeasured_temp` with constants. Only the two fault flags may be assigned.
It preserves the complete original statement-token prefix and all declarations.
The evaluator partitions the entire INT domain [-32768,32767] at every candidate
and specification comparison constant, checks boundary neighbors and every
enable/prior-flag combination, and reports a counterexample for a wrong supported
transition. Without arithmetic or calls, comparison truth values are constant in
each remaining interval; this covers the full input domain without pretending to
execute a PLC. Unsupported syntax stays unverified. Regression tests include
heating/cooling sequences, retained alarms, disable/re-enable, exact boundaries,
INT extremes, changed thresholds and off-target writes.

Run `prepare` again when upgrading from four tasks: old manifests lack the alarm
baseline. One A/B repetition now schedules ten cases (five repetitions: fifty).
Older eight-case campaigns remain separate and show no alarm measurement in the
archive graphics. Their success rates must not be pooled with the expanded suite.

## Conditions and model context

- A: project automation and embedded language reference, with all three installed
  manual tools removed from discovery and blocked in dispatch.
- B: the same base policy, plus `get_documentation_status`, `search_manuals`, and
  `get_manual_topic`, backed by the same explicitly prepared corpus.

Both arms use the same neutral orientation and task prompts. B is not forced to
retrieve a manual. Corpus file/manifest/index hashes and status freshness are
recorded. Prepare manuals explicitly with `tools/export_ce_help.py` and
`tools/index_ce_help.py`; see the repository documentation service instructions.

The adapter snapshots initialization instructions and schemas. It removes the
existing exact documentation-only recommendation sentence from BOTH arms,
retaining all other server guidance. Changed/unrecognized guidance remains visible
and fingerprinted. MCP prompts/resources are not automatically loaded in either
arm; the embedded `get_language_reference` tool remains available. Models receive
no shell, filesystem, open-project or arbitrary path tool. Editing is restricted
to MAST/Feeder without declarations; saving accepts only the already-selected path.
Inspection exposes read tools only. This deliberately controlled tool subset
measures this client's policy, not every possible MCP client behavior.

MCP tools become Responses function schemas (`strict: false`, preserving optional
MCP parameters). Discovery follows public pagination. Returned MCP errors,
structured results and content blocks are retained. Only an exact duplicate JSON
text block is removed when the same structured object is present. This policy is
identical in both arms. Necessary reasoning/function-call response items are
replayed in original order; no history truncation is applied.

OpenAI uses `store: false` and encrypted reasoning items when reasoning effort is
configured. DeepSeek omits unsupported `store`/`include`/`parallel_tool_calls`
parameters and retains its plain `reasoning` content items. DeepSeek may emit
multiple calls; dispatch is always serial. Its adapter accepts explicit effort
`none`, `low`, `high` or `max`, and omits sampling knobs whose effect depends on
model/mode. See the official [OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)
and [DeepSeek Responses compatibility tables](https://api-docs.deepseek.com/guides/responses_api/).

## Reset, evidence, scoring and recovery

Before every task/repetition/condition/attempt the harness verifies baseline
hashes, copies a unique disposable project and opens it through MCP. Only repair
starts from the broken fixture. The evaluator closes without saving and reopens
the saved output, exports source/declarations, verifies scope and independently
rebuilds edits. Model-requested builds belong inside workflow time; evaluator
builds do not. Parsed empty diagnostics alone never establish build success;
`build_state=built_ok` with no `error` is required and capture metadata is retained.

The private `feeder-2` rubric grades inspection JSON deterministically. Gold data
and evaluation results are never sent to the model. Threshold/repair checks accept
the original normalized executable statement sequence with exactly the prescribed
change. Temperature checks accept unchanged surrounding statements with recognized
inclusive ABS or two-sided comparison predicates; the exact accepted family is in
`tasks.py`. Tests cover threshold 4/5/6, both previous request latch states,
reset/decrement ordering, integer conversion, inclusive temperature boundaries,
just-outside values, negative and nonintegral setpoints. Other potentially valid
implementations remain **unverified**, rather than a fabricated behavioral pass or
a claim that they are incorrect. This intentionally narrow static proof/check is
not PLC execution. `runtime_behavior` is always `unverified` in this release;
reports separate build, scope, static acceptance and runtime verification.

Temperature rubric `feeder-temperature-2` also accepts redundant parentheses
around the exact `Setpoint_temp +/- 2.0` bounds (including nested grouping).
Boolean/comparison grouping and all other arithmetic remain unchanged; exclusive
bounds, OR, wrong tolerances and unrelated edits remain unverified.

No simulator execution mode is implemented. Any later runtime experiment needs
explicit simulator isolation, the first-transfer CPU-family GUI seeding procedure,
and located `%M`/`%MW` tags (the fixture's unlocated variables are not Modbus-readable).
Do not mix such results with this offline benchmark.

Each attempt retains append-only fsynced `events.jsonl`, content-addressed JSON
blobs, `summary.json`, `final-response.txt`, `validation.json`, the native saved
project, and exported section/declarations when evaluation reaches them. Request
events reference exact instruction/schema/input blobs, avoiding repeatedly copying
large histories. A blob's filename is its canonical JSON SHA-256; reconstruct a
request from `model_context`, `model_request.parameters_ref` and ordered
`input_refs`. Raw responses and model-visible tool payloads have separate references
which can point to the same blob. All evidence remains local and can contain
project source/manual excerpts.

Usage accumulates provider input/output/total fields across every request. Cached
input and reasoning details are subsets, never added to total. Missing usage is
null; known partial totals are separate. `APIConnectionError` (including SDK connection
timeouts) retries the identical API request up to twice, after 1 and 2 seconds,
within the workflow timeout. Every attempt, error and delay is recorded; failed
requests retain unknown usage even when a retry succeeds. Responses/history and
MCP calls advance only after a received response, so writes are never replayed.
SDK-internal and MCP transport retries remain disabled. HTTP errors, malformed
responses, cancellation and harness timeouts are not retried. The policy is
fingerprinted and archived; retry time remains in workflow time. Model
repair cycles count writes following a failed model build. Wall time, request
elapsed time and MCP round-trip latency are recorded separately; MCP latency is
not pure COM time and remaining wall time is not labeled model thinking time.

Campaign plans persist immutable config/model/prompt/fixture/environment/source/
dependency/corpus/effective-schema fingerprints and randomized ordering. Resume
skips only matching durable terminal summaries, including recorded task failures;
an interrupted attempt gets a fresh directory and fixture. It never replays writes
into uncertain state. Changes require a new campaign; distinct fingerprints are
reported in separate groups. Reports retain failures/timeouts/interrupted attempts
and partial usage, per-task/overall rates, median/nearest-rank p95 with known/unknown
sample counts, successful-run efficiency and within-campaign paired differences.
Scheduled but unstarted cases are listed separately. JSON contains full details;
Markdown supplies a compact overview. API and manual/UI results are never combined.

A per-user OS lock serializes benchmark clients across workspaces. It does not
control independent third-party CE clients: leave their projects alone and let
write-token conflicts fail. No project/token stealing or process killing is used.
A timed-out/disconnected MCP operation taints both the workspace and per-user
guard; no subsequent CE operation is started. Verify the operation has stopped
and recover the disposable session before acknowledging recovery:

```powershell
.venv\Scripts\ce-bench.exe recover --config benchmarks\local.json --verified-idle
.venv\Scripts\ce-bench.exe resume --run-id YOUR_RUN_ID --config benchmarks\local.json
```

Recovery requires the operator's attestation because closing a client or timing
out does not prove that a COM worker stopped. Recovery evidence is retained.

## Optional manual ChatGPT procedure

Use a separate, clearly labeled `chatgpt_manual` experiment: reset a unique fixture,
start a new chat, use one task prompt and the same tool-availability policy, record
the displayed model label, times and exported artifacts, then independently evaluate
them. Public/manual UI inspection cannot guarantee a fixed hidden model snapshot
or expose complete internal orchestration. Record `input_tokens`, `output_tokens`,
`total_tokens`, cached/reasoning details and unavailable request IDs as **null**.
Do not infer them from MCP bytes. No website automation/private endpoints are used.

## GitHub archive and graphical overview

After a campaign, archive its sanitized metrics and regenerate the image:

```powershell
.venv\Scripts\ce-bench.exe archive --results benchmarks\results --run-id YOUR_RUN_ID --archive benchmarks\archive
.venv\Scripts\ce-bench.exe visualize --archive benchmarks\archive --output benchmarks\archive\overview.png
git add benchmarks/archive
git commit -m "Archive Control Expert benchmark results and overview"
```

Commit the data, PNG and `overview.metadata.json` together. The graphical overview
reads only archived JSON: task acceptance, workflow medians and provider tokens,
with separate rows for each campaign/model/measured source/condition. It expands
as more models and revisions are archived; incompatible experiments are not pooled.
The PNG's metadata sidecar records exact source-data and image hashes, plotting
code hash and matplotlib version. Offline tests detect data/image mismatches.
`--scoring original` plots original scores; the default `latest` applies the latest
explicit inspection regrade and shows original-to-current counts in the image.
See [the archived overview](archive/README.md).

Individual archive directories are immutable and checksummed. `index.json` and
README are derived navigation. Missing cases require `archive --allow-incomplete`,
which creates a separate labeled snapshot. Raw native projects, transcripts,
manual excerpts, credentials, local paths and machine names are not copied.
Allowlisted scores/metrics, source/dependency/corpus fingerprints and artifact
hashes are retained. Keep the original local evidence for detailed audits.

The first real run used rubric `feeder-1`: both factually correct inspection
answers included optional assignment/function-expression forms that it rejected.
Rubric `feeder-2` accepts these equivalent forms without relaxing any required
facts. Original summaries remain 6/8; explicit deterministic regrading gives 8/8:

```powershell
.venv\Scripts\ce-bench.exe regrade --results benchmarks\results --run-id 20261121T100834Z-be7edc84
.venv\Scripts\ce-bench.exe compare --results benchmarks\results --output benchmarks\comparison-feeder-2 --rubric feeder-2
```

Regrading sends no API requests and performs no new CE operations. It verifies
original summary/response hashes, retains saved-artifact scope evidence, and
appends a new rubric record. Both score versions are in the archive. The measured
dirty Python package was verified against commit `d94539a9068ae11474460caeb9c3224462138d7f`
before further code changes; the archive preserves that proof and original dirty
metadata rather than relabeling the run as a clean checkout.

## Offline checks

```powershell
.venv\Scripts\python.exe -m compileall -q src
.venv\Scripts\python.exe -m unittest discover -s tools -p "test_*.py" -v
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m build --outdir tmp\benchmark-dist
.venv\Scripts\python.exe -m twine check --strict tmp\benchmark-dist\*
.venv\Scripts\python.exe tools\check_distribution.py --dist-dir tmp\benchmark-dist
```

Offline integration uses a synthetic MCP stdio server and scripted provider; it
does not validate real Control Expert or either paid provider. See
[CHECKPOINT.md](CHECKPOINT.md) for exact host validations and next actions.
