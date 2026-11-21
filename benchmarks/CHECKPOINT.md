# Benchmark implementation checkpoint

## Deterministic I/O regrades (2026-11-21)

Added `demo-io-mapping-3`: normalized row-local physical facts, exact addresses,
module/slot/channel contradiction checks, explicit slot/module joins to hardware
channel tables, memory declarations in prose, and per-check matched/missing/
incorrect diagnostics with coverage and evidence hashes. Versions 1 and 2 remain
available for audit. Regrade provenance binds both scorer modules as well as the
unchanged reference, response and original summary. No LLM or CE calls were made.

Regraded saved Luna campaign `20261121T211320Z-ec8c65a1`: A matches 23/29 checks,
B 22/29. Both lack device-DDT channel coverage and the explicitly required
Forming, Belt_running and Material_picked_off unmapped classifications; B also
omits Robot_one. These are omissions, not conflicting physical claims. Overall
acceptance remains A 6/7, B 6/7 (12/14).

Regraded preceding GPT-5.5 campaign `20261121T204037Z-e4c05842`: mapping A matches
14/29 checks and remains rejected; mapping B matches 29/29 and now passes using
the explicit hardware-table join. Overall observed acceptance changes from 4/7
to 5/7. This campaign remains incomplete (7/14 scheduled cases attempted),
including the original HTTP 429 failure; no paid run was resumed.

Both original scores and v2/v3 regrades are archived together. Prior uncommitted
archive snapshots are preserved under ignored `benchmarks/.local/` directories.
The current GPT-5.5 snapshot is
`archive/20261121T204037Z-e4c05842-partial-200738467d/`. Archive index, overview
PNG and provenance metadata were regenerated together. The existing DeepSeek
answers also pass v3 as a regression control; their committed archive is unchanged.
Final validation: 80 offline tests passed (one existing symlink-privilege skip),
syntax compilation passed, all 12 archived record/report checksums and plot
provenance hashes passed, and both scorer-module hashes matched the saved regrades.
The regenerated overview was visually inspected. Test log:
`tmp/grader-v3-final-tests.log`.

## Luna complete rerun (2026-11-21)

Campaign `20261121T211320Z-ec8c65a1` completed all 14 offline cases using OpenAI
`gpt-6-luna` (mutable alias), medium effort, A/B, one repetition, seed 1729.
Both arms accepted 6/7: inspection, threshold, temperature, repair, alarms and
weighing passed; I/O mapping failed in both arms. The explicit
`demo-io-mapping-2` regrade also rejects both mapping answers. Original evidence
is retained. All eight editing cases built successfully. Three tool errors
occurred (A: two, B: one); zero API retries and no missing usage samples.

Provider totals: 131 requests, 117 tool calls, 1,424,471 input tokens (1,177,257
cached), 21,772 output tokens, 1,446,243 total tokens. Summed model workflow time
was 326.014 seconds, excluding setup/evaluation. At the verified Standard Luna
rates ($0.10/M input, $0.01/M cached input, $0.50/M output), those token counts
estimate $0.04738 before cache-write charges, other adjustments or taxes. This
is a usage-based estimate, not an invoice total.

The launch removed incidental `CODEX_TOOL_CALL_ID` before the initial snapshot
to prevent the previous resume mismatch. No harness code was changed. The
measured checkout was dirty with earlier archive/checkpoint changes.
Sanitized records, reports, checksums, index, comparison files, overview PNG
and provenance metadata were regenerated together; raw evidence stays ignored.
The overview was visually inspected. Four archive regression tests and all
archived record/report checksums passed.

## OpenAI partial rerun (2026-11-21, after `c17ace0`)

Ran the current seven-task offline suite with OpenAI `gpt-5.5-2026-04-23`,
medium effort, A/B, one repetition, seed 1729. Campaign
`20261121T204037Z-e4c05842` stopped on HTTP 429 (`RateLimitError`) at alarms A.
Seven of 14 scheduled cases have durable results: four accepted (threshold and
temperature in both arms), two rejected I/O mapping answers, and one provider
failure. Seven cases remain unattempted. The explicit `demo-io-mapping-2`
regrade also rejects both mapping answers; original evidence is retained.

A resume attempt made no paid requests: immutable fingerprint validation
rejected the changed `CODEX_TOOL_CALL_ID` environment hash. Source and model
settings were unchanged. No fingerprint guard was bypassed and no new campaign
was started. Future runs should stabilize or exclude this incidental environment
variable before capturing their initial fingerprints.

Sanitized partial results are archived under
`archive/20261121T204037Z-e4c05842-partial-c2d66c173b/`, explicitly marked
incomplete. Archive stats/index, comparison files, overview PNG and provenance
metadata were regenerated together. Raw evidence and credentials remain ignored.
The overview was visually inspected; archive checksum tests passed.

## M580 weighing and I/O mapping (2026-11-21)

Added two optional read-only tasks using disposable copies of the full M580
sample, configured through `demo_project` and `io_mapping_reference` in both
provider examples. The approved mapping reference is private to the judge.
`demo-weighing-1` requires both Weighing_Material_A and Weighing_Material_B;
explanation semantics are not automatically scored. The mapping rubric checks
all 11 physical instances, both memory-only instances, 14 representative
unmapped signals and Robot_one; exhaustive software/leaf coverage is unverified.

Host: Windows, Python 3.11.5 x64, Control Expert V16.4. Feeder CPU: BMX P34 2020 /
02.70. Full demo CPU: BME P58 3040 / 03.20. Offline only. The vendor integrity
check required CommonProgramFiles to point to the 32-bit Common Files directory
in the server environment. No integrity check was disabled. Demo source SHA-256:
`5243304e7c0289eb56b63359b4c2c8fd406ec39612dd513293abda3cb2e45538`.
Reference SHA-256: `ae70a0f647ac3d404ed66eb014a0f876806b067ef38f0b07953a5a8233218888`.

Canonical validation: `benchmarks/.local/validate-657da39ed663`. All four Feeder
edits built before save and after reopening; the full demo sections and variable/
configuration exports were verified without modifying the source or copy.

Paid campaign `20261121T200704Z-5bbd9b33`, DeepSeek `deepseek-flash` mutable alias,
high effort, A/B, one repetition, seed 1729, completed all 14 cases. The credential
was supplied only to the parent process; raw credentials/evidence remain ignored.
All ten Feeder cases and both weighing cases passed. Original mapping rubric
`demo-io-mapping-1` rejected both correct table representations: module spacing,
channel labels, annotations and grouped unmapped rows were too strict.

Explicit `demo-io-mapping-2` formatting-only regrade accepted both mapping answers
against the unchanged reference, producing A 7/7 and B 7/7 (14/14 total), while
retaining original 6/7 per arm (12/14 total). Required facts/coverage were not
relaxed. Wrong addresses, modules, channels and invented physical mappings have
negative regression controls. Regrades bind the original response/summary,
reference and scorer hashes; they make no API or CE calls. The v1 scorer is
retained for audit. Six tool errors occurred in I/O case A; case B had none.
Final validation: 76 offline tests, one existing symlink-privilege skip, passed;
syntax and dependency checks passed. Logs: `tmp/benchmark-demo-final-frozen-tests.log`.
All four campaigns' record/report checksums, PNG/provenance hashes, the original
reference and regrade scorer hash were independently verified. The generated
visualization was visually inspected; unknown usage remains unknown.

Provider totals: 4,065,576 tokens, 107 requests, 164 tool calls, zero API retries.
Summed model workflow time: 492.568 seconds, excluding setup and evaluation.

```powershell
# DEEPSEEK_API_KEY supplied to the parent process, never to the MCP child:
ce-bench run --config benchmarks/local.json --condition A B --repeats 1 --seed 1729
ce-bench regrade --results benchmarks/results --run-id 20261121T200704Z-5bbd9b33 --task io_mapping
ce-bench archive --results benchmarks/results --run-id 20261121T200704Z-5bbd9b33 --archive benchmarks/archive
ce-bench visualize --archive benchmarks/archive --output benchmarks/archive/overview.png
```

Sanitized archive, original/regraded scores, source/reference hashes, checksums,
PNG and provenance metadata are stored together. The overview includes both
new task columns, uses compact campaign labels, preserves unknown usage, and
excludes read-only tasks from build denominators. The measured checkout was
dirty; no clean or verified-commit claim is made. The first uncommitted archive
render, superseded only for build-denominator metadata, is retained under ignored
`benchmarks/.local/superseded-demo-archive-v1/`.


## Earlier checkpoint: archive backlog and a CI regression (2026-11-21, after `c10a348`)

**At that checkpoint, nothing newer than `20261121T114513Z-a78f24bc` was archived.**
`benchmarks/archive/` held exactly those three campaigns; its index and graphics
were mutually consistent, and the offline suite passed including archive-integrity
and regrade tests.

Complete local campaigns that are **not** archived (raw evidence stays under the
ignored `benchmarks/results/`; harness revision `e7a1a5f`, `dirty: false` in each):

| Run | Suite | Provider / model | Cases | Result |
|---|---|---|---|---|
| `20261121T131404Z-b2cc4984` | five offline tasks, A/B | openai `gpt-5.5-2026-04-23`, medium | 10/10 | all accepted |
| `20261121T130812Z-opc-461b35db` | `ce-bench opc`, live | openai `gpt-5.5-2026-04-23`, medium | 3/3 | all passed, restoration verified |
| `20261121T130930Z-opc-44a5e26e` | `ce-bench opc`, live | openai `gpt-5.5-2026-04-23`, medium | 3/3 | all passed, restoration verified |
| `20261121T131110Z-opc-d434b70f` | `ce-bench opc`, live | deepseek `deepseek-flash` (alias), high | 3/3 | all passed, restoration verified |

`20261121T130836Z-opc-68604681` is a single positive-case smoke run of the same OPC
suite. Archive publication needs one documented campaign per provider and model, so
the two duplicate OpenAI OPC runs should not both be published; `archive` refuses a
run with missing cases unless `--allow-incomplete` is given, and a live OPC campaign
additionally requires verified restoration.

Incomplete campaigns, which have no `outcome.json` and no report:

- `20261121T132745Z-6e9d154f` (deepseek) stopped after 1 of 10 scheduled cases.
- `20261121T133045Z-756e0589` (deepseek, run against the separate clean checkout
  `control-expert-mcp-benchmark-e7a1a5`) completed 5 of 10 cases: `temperature-000-A`
  was interrupted mid-request (6 model requests, 5 responses, no `summary.json`), and
  `repair`/`inspect` never started. Neither the workspace nor the per-user guard holds
  `TAINTED.json`, so `resume` is permitted without `recover`, and the clean checkout
  still exists. A `ControlExpert.exe` instance started at 13:31 remains running.

Offline CI regression at tag `v0.9.1` (`dfc6111`): all five Python jobs failed in
`Run offline regression tests` with `ModuleNotFoundError: No module named 'httpx'` in
`test_benchmark.RuntimeTests.test_connection_retries_preserve_requests_and_do_not_replay_writes`
and `test_connection_retry_limit_and_non_connection_errors`. The workflow installed
`".[test]"`, which omits the `benchmark` extra supplying `openai` and therefore
`httpx`. `7317605` installs `".[benchmark,test]"` for both the checkout and the
isolated wheel, and CI and Publish have passed at every commit since, up to `c7b5e62`.
The README offline-check commands now state the same requirement.

## Fresh DeepSeek five-task campaign (2026-11-21)

Committed implementation, retry policy and prior sanitized results as
`c10a348e60d82a004f98582048277287c50716d8` before starting the paid run, as
requested. Harness and both server conditions recorded that exact revision with
`dirty: false`. The same existing native fixtures, CPU/CE version, five task
prompts, A/B policy, one repetition and seed 1729 were used.

```powershell
.venv\Scripts\ce-bench.exe run --config benchmarks/.local/deepseek.json --condition A B --repeats 1 --seed 1729
.venv\Scripts\ce-bench.exe archive --results benchmarks/results --run-id 20261121T114513Z-a78f24bc --archive benchmarks/archive
.venv\Scripts\ce-bench.exe visualize --archive benchmarks/archive --output benchmarks/archive/overview.png
```

Campaign `20261121T114513Z-a78f24bc`: `deepseek-flash` (mutable alias), high
reasoning effort, 8/10 accepted (A 4/5, B 4/5). All eight edit/repair cases passed
source/declaration/static checks and saved-project rebuilds, including alarms.
Both inspection answers incorrectly called `FE(Mixing_done)` a rising edge;
the source uses the falling edge. B additionally fenced its JSON, violating the
JSON-only output contract and producing the recorded parse failure. No regrade
or retry was used to hide these model errors. There were no connection failures,
so the new retry policy was not needed in this real campaign. Offline tests
exercise recovery and exhaustion independently for both providers.

Provider usage: 469,792 tokens, 68 API requests, 80 tool calls, zero API retries
and zero tool errors. API credentials were supplied only in the parent process
environment from ignored local secrets. Runtime behavior remains unverified.
Sanitized archive and overview are regenerated together; AGENTS.md now requires
this after every archived benchmark run. Historical campaigns stay separate.

## API connection retries (2026-11-21)

APIConnectionError now retries the identical provider request up to twice with
1/2-second backoff inside the workflow deadline. SDK retries remain disabled;
MCP operations are never replayed. Requests, failures, delays and retry counts
are durable evidence, and unknown usage on lost responses remains unknown.
The policy is captured in campaign fingerprints and sanitized archives.
HTTP errors, harness timeouts, cancellation and malformed responses are not retried.

The full offline suite passed 48 tests (one existing symlink-privilege skip),
including connection recovery before/after a tool call, identical request
replay, no repeated writes, retry exhaustion and non-connection failures.
Log: `tmp/benchmark-retry-tests.log`. Syntax and dependency checks passed.
The user requested a commit before the fresh five-task DeepSeek campaign.
The prior OpenAI archive remains immutable and predates this retry policy.

## OpenAI rerun and demo-derived alarms (2026-11-21)

Temperature rubric `feeder-temperature-2` accepts redundant parentheses around
the exact setpoint bounds. Added regression controls for exclusive bounds, OR,
wrong tolerances, arithmetic changes and out-of-scope edits.

Added the fifth task, `alarms`, from Stefan Probst's Heating/Alarming examples:
200/400 trip thresholds, new 205/395 hysteresis clear points, retained flags and
disable/reset gating. A separate native Feeder copy adds only three predeclared
EBOOLs; the original four tasks retain the original fixture. `feeder-alarms-1`
checks a restricted ST transition grammar across all INT comparison partitions,
enable states and both previous flags. Unsupported syntax and PLC runtime stay
unverified. Both conditional and Boolean implementations have regression tests.

Host: Windows, Python 3.11.5 x64, CE V16.4, BMX P34 2020 / 02.70, offline only.
Preparation: `benchmarks/.local/prepare-b552b7f47a07`; canonical validation:
`benchmarks/.local/validate-71188b6e31aa`. All four edit solutions built before
saving and after reopening, with source/declaration checks; alarm proof: 112
partition/state cases covering the full INT domain.

Validation commands: `python -m compileall -q src`, `python -m pip check`,
`python -m unittest discover -s tools -p "test_*.py" -v`: 46 tests, one existing
symlink-privilege skip. Wheel/sdist build, strict twine and distribution checks
passed (28 wheel files / 54 sdist files). Logs and distributions are under ignored
`tmp/benchmark-openai-*` and `tmp/benchmark-alarms-*` paths.

Fresh paid run (OPENAI_API_KEY supplied only to the parent process):

```powershell
.venv\Scripts\ce-bench.exe run --config benchmarks/.local/openai.json --condition A B --repeats 1 --seed 1729
.venv\Scripts\ce-bench.exe archive --results benchmarks/results --run-id 20261121T112555Z-608e42da --archive benchmarks/archive
.venv\Scripts\ce-bench.exe visualize --archive benchmarks/archive --output benchmarks/archive/overview.png
```

Campaign `20261121T112555Z-608e42da`, pinned `gpt-5.5-2026-04-23`, medium effort:
9/10 accepted (A 4/5, B 5/5). Both alarm cases and both temperature cases passed
scope, declarations, static checks and independent saved-project rebuilds.
`threshold-000-A` had `APIConnectionError` on its first request, before any model
response or tool call. It remains a recorded failure, with unknown request usage;
it was not retried or regraded. Known provider usage: 248,083 tokens, 64 request
attempts, 54 tool calls and zero tool errors. Runtime behavior is unverified.

The earlier OpenAI campaign `20261121T105143Z-d147bc8e` and stale comparisons were
removed from active results/archive navigation into ignored
`benchmarks/.local/superseded-openai-20261121T105143Z-d147bc8e/`; permanent deletion
was blocked by automatic approval review. DeepSeek evidence remains unchanged.
The new archive and regenerated overview retain failures and missing usage;
the older four-task campaign has no alarm measurement. Archive/image integrity
tests passed after regeneration. Measured source was dirty and is recorded with
its original fingerprints, without a clean-checkout or verified-commit claim.

## Previous checkpoint (before the OpenAI rerun)

Updated 2026-11-21. Base checkout: `dd3c8757b38dafb9eedbac11428ef42ae834ea9c`.
Paid DeepSeek testing was explicitly authorized after implementation. No OpenAI
provider run or simulator execution was performed.

Implemented: optional `benchmark` dependency and `ce-bench`; configuration and
provider adapters for OpenAI/DeepSeek Responses; public MCP stdio discovery and
controlled serial dispatch; A/B manual-tool filtering; fixture preparation and
canonical validation; four independent tasks; private rubric and conservative
static scoring; saved-project reopen/build checks; content-addressed evidence and
exact provider usage; randomized interleaved campaigns; immutable resume; reports;
per-user locking/taint recovery; synthetic offline tests and distribution integration.

Real host: Windows, Python 3.11.5 x64, licensed Control Expert `V16.4`, CPU
`BMX P34 2020` / `02.70`. Prepared installed corpus: 280 manuals, index current.

Executed successfully:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[benchmark,test]"
.venv\Scripts\python.exe -m control_expert_mcp.benchmark.cli doctor --config benchmarks/example.json
.venv\Scripts\python.exe -m control_expert_mcp.benchmark.cli prepare --config benchmarks/example.json
.venv\Scripts\python.exe -m control_expert_mcp.benchmark.cli validate --config benchmarks/example.json
```

Local preparation evidence: `benchmarks/.local/prepare-808d4b4322ae/`.
Baseline imported with all 15 declarations/initial values preserved, built_ok,
saved/reopened/rebuilt. Unique broken conversion operand produced E1061 for
`CE_BENCH_UNDEFINED_TEMP_7F93`, build_state not_built, explicit compiler failure;
reopening reproduced it. Diagnostic attribution remains unverified as reported by
the server; no assumption that changed output proves attribution.

Local canonical validation: `benchmarks/.local/validate-080811bdb4ef/`.
Threshold, inclusive ABS temperature tolerance and repair all built before saving
and after reopening; exported scope/declarations passed static checks. This was
direct scripted MCP validation, not a model run or simulator execution.

Final offline suite: `python -m unittest discover -s tools -p "test_*.py" -v`
passed 40 tests (one existing platform/capability skip), in both the editable
checkout (37.612 s) and an isolated installed wheel (34.016 s), including archive
privacy/immutability, regrade evidence and multi-model/version plot-data tests.
Logs: `tmp/benchmark-final-tests.log` and `tmp/benchmark-final-wheel-tests.log`.
Syntax and `pip check` passed. Final wheel/sdist in `tmp/benchmark-final-dist`:
strict twine and `tools/check_distribution.py` passed (27 wheel files / 52 sdist
files, generated archive/native projects/credentials excluded). DeepSeek
keyless dry-run generated the 40-case seeded schedule without a provider request.

Real paid command, explicitly requested by the user:

```powershell
.venv\Scripts\ce-bench.exe run --config benchmarks/local.json --condition A B --repeats 1 --seed 1729
.venv\Scripts\ce-bench.exe compare --results benchmarks/results --output benchmarks/comparison
```

Campaign `20261121T100834Z-be7edc84` completed all eight cases. All six edit/repair
cases passed saved-artifact/declaration/static checks and real evaluator rebuilds.
Both inspection answers gave the correct initialization assignment, but rubric
`feeder-1` rejected optional assignment/function-expression forms. Original summaries are
preserved (6/8 accepted); explicit `feeder-2` regrading accepted both equivalent
representations, giving 8/8 without changing required facts or calling an API.
No model failure should be inferred from this overly strict formatting check.
Provider-reported totals: 425,260 tokens, 59 API requests, 68 tool calls, zero
tool errors. Summed measured workflows: 150.67 seconds; setup/evaluation are separate.

The user requested a GitHub archive and graphical overview. Sanitized original
scores, explicit regrades, timing/token/tool metrics, source proof and checksums
are in `benchmarks/archive/20261121T100834Z-be7edc84/`. `overview.png` is generated
only from archived JSON; `overview.metadata.json` binds it to source-data hashes.
The generator supports multiple campaigns/models/revisions without pooling them.
Current archive: one model (`deepseek-flash` alias), one measured revision, A/B,
one repetition per task. Do not infer a significant documentation advantage.

Measured Python bytes were verified before subsequent code changes against
commit `d94539a9068ae11474460caeb9c3224462138d7f` (Git CRLF/LF normalized). The
original dirty-revision fingerprint remains recorded. Archive publishing code,
rubric v2, plotting and regression tests were added afterwards on
`feat/control-expert-benchmark`. No change to `main` or raw-evidence publication.

Local ignored `benchmarks/local.json` selects DeepSeek and the ignored repository
`.secrets` credential file. `deepseek-flash` is explicitly marked a mutable alias,
not a guaranteed snapshot. Credential content was not logged or committed. Only
explicit user invocation of `run`/`resume` authorizes paid requests.

Remaining limitations: no OpenAI provider run; no simulator behavior validation;
static scoring supports a documented subset, otherwise unverified; no warm-server
experiment; opaque server wrappers have unknown source metadata; mutable provider
aliases cannot guarantee unchanged weights. Core comparison uses cold fresh MCP
servers, serial operations, and fresh conversations per case.

Delivery branch: `feat/control-expert-benchmark`, with implementation, sanitized
archive data, PNG and provenance metadata committed together for the explicitly
requested GitHub push. Future runs:
`ce-bench run`, then `archive` and `visualize`; commit archive data/image/metadata
together. Use `regrade` only explicitly and retain all original scores.
