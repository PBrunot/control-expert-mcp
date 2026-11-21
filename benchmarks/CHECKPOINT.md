# Benchmark implementation checkpoint

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

Offline suite: `python -m unittest discover -s tools -p "test_*.py" -v` passed
36 tests (one existing platform/capability skip), both in the editable checkout
and an isolated installed wheel environment. Logs: `tmp/benchmark-full-tests.log`
and `tmp/benchmark-wheel-tests.log`. Syntax and `pip check` passed. Built wheel
and sdist in `tmp/benchmark-dist`; strict twine checks and
`tools/check_distribution.py --dist-dir tmp/benchmark-dist` passed. DeepSeek
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
preserved (6/8 accepted); a planned explicit `feeder-2` regrade will accept that
equivalent representation without changing the required facts or calling an API.
No model failure should be inferred from this overly strict formatting check.

Local ignored `benchmarks/local.json` selects DeepSeek and the ignored repository
`.secrets` credential file. `deepseek-flash` is explicitly marked a mutable alias,
not a guaranteed snapshot. Credential content was not logged or committed. Only
explicit user invocation of `run`/`resume` authorizes paid requests.

Remaining limitations: no OpenAI provider run; no simulator behavior validation;
static scoring supports a documented subset, otherwise unverified; no warm-server
experiment; opaque server wrappers have unknown source metadata; mutable provider
aliases cannot guarantee unchanged weights. Core comparison uses cold fresh MCP
servers, serial operations, and fresh conversations per case.

Next: preserve a commit matching the measured Python source, add the Git-safe
archive and explicit inspection regrade, rerun offline/distribution checks, then
push the requested implementation/results archive on a new feature branch.
