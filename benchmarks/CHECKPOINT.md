# Benchmark implementation checkpoint

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
