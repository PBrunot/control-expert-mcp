# Dedicated IEC benchmark

The `ce-bench iec` suite implements the five cases in
[the IEC specification](Specifica_Benchmark_IEC_Control_Expert.md). It is separate
from the seven-task offline suite, `ce-bench opc`, and the one-second counter suite.

## Starting project and identifiers

Every project starts as a disposable copy of the configured native M580 demo
STU, normally `samples/demo_ControlExpert_M580.STU`. The suite does not create
hardware, a CPU, or a replacement project configuration. The source file is
hashed and preserved. The CPU/version in the configuration must match the demo.
Original declarations, tasks, section languages and section order are retained.

The specification uses logical interface names; the engineering project and
model prompt use a deterministic prefix to avoid collisions:

| Case | Candidate section in MAST | Example input/output | Helper prefix |
|---|---|---|---|
| `iec_st_clamp` | `IEC_ST_Candidate` | `IEC_ST_Raw`, `IEC_ST_Result` | `IEC_ST_LLM_` |
| `iec_ld_latch` | `IEC_LD_Candidate` | `IEC_LD_StartCmd`, `IEC_LD_Running` | `IEC_LD_LLM_` |
| `iec_fbd_hysteresis` | `IEC_FBD_Candidate` | `IEC_FBD_LevelValue`, `IEC_FBD_Demand` | `IEC_FBD_LLM_` |
| `iec_sfc_sequence` | `IEC_SFC_Candidate` | `IEC_SFC_StartCmd`, `IEC_SFC_Busy` | `IEC_SFC_LLM_` |
| `iec_il_select` | `IEC_IL_Candidate` | `IEC_IL_SignalA`, `IEC_IL_Selected` | `IEC_IL_LLM_` |

SFC step names are `IEC_SFC_Idle`, `IEC_SFC_Active`, `IEC_SFC_Completed`.
Its optional helper sections are `IEC_SFC_LLM_Pre` and `IEC_SFC_LLM_Post`.
Preparation rejects demo declarations/sections already using `IEC_` or `Bench_`.
The grader and saved capture retain the specification's logical names.

## Commands

Install the benchmark dependencies and activate the repository virtual
environment. Copy `benchmarks/iec.example.json` to an ignored local configuration.
If moving the JSON into `.local`, adjust paths: they are relative to the JSON.
Set the Python executable, demo path, actual CPU/firmware, model and provider.
For OFS configure a Python with matching OPC Automation bitness through
`CE_MCP_OPC_PYTHON`. Configure the indexed manuals for condition B as usual.
Local vendor prerequisites, including `CommonProgramFiles` when required, are
the same as those documented in `benchmarks/README.md`.

```powershell
# Configuration/schedule only: no COM, OPC, provider or simulator operations.
ce-bench iec run --config benchmarks/iec.example.json --case all --dry-run

# Engineering-only native reference imports/build round trips; zero API calls.
# Requires a dedicated idle CE session. Never downloads to a PLC or simulator.
ce-bench iec prepare --config benchmarks/iec.example.json --condition A --case all

# Scripted simulator acceptance: two clean reference executions and one mutant
# per selected case/condition. Replaces the simulator application and stops it.
ce-bench iec validate --config benchmarks/iec.example.json --condition A --case all --alias Dev_Alias_2 --allow-live --confirm-ofs-running --allow-closed-loop --allow-simulator-replacement --confirm-simulator-alias

# Paid model authoring followed by independent private evaluation.
ce-bench iec run --config benchmarks/iec.example.json --condition A B --case all --repeats 1 --alias Dev_Alias_2 --allow-live --confirm-ofs-running --allow-closed-loop --allow-simulator-replacement --confirm-simulator-alias

# Single case uses the same command with --case iec_st_clamp (or another ID).
# Read-only overview of saved campaigns: PNG + SVG + numeric JSON.
ce-bench iec overview --results benchmarks/results/iec --output benchmarks/results/iec/overview.png

# Replay a saved capture without CE, OFS or provider access. IDs are recorded
# in capture-identity.json. Evidence JSON contains trusted artifact_valid/build_ok.
ce-bench iec grade --case iec_st_clamp --evidence evidence.json --capture capture.json --run-id 123 --artifact-id 456 --output validation.json
```

`--confirm-simulator-alias` attests that the chosen alias resolves to
`MBT:127.0.0.1/U`; do not use an alias pointing at physical hardware. Engineering
deployment is restricted to `simulator/127.0.0.1/TCPIP`. Before the only OPC write
(`Bench_Start`), the runner must read the unique freshly downloaded run identity
and candidate identity with good quality. A different application cannot be
accepted merely because it exposes the same tag names. The suite does not
automatically inspect or change the OFS alias configuration.

For implementation/debug runs add `--stop-on-infrastructure-error`: the runner
finishes cleanup and stops at a case boundary, retaining the pending schedule.
Unexecuted slots are shown separately from actual infrastructure failures.
Preparation hashes the source demo, blank projects, CPU/version and fixtures.
Its recorded harness hash is provenance; later harness-only fixes do not require
recreating unchanged demo templates. Each campaign independently inspects/builds
its candidates and fingerprints the current harness and preparation manifest.
Source must remain unchanged throughout that campaign.

A fresh simulator may need the existing manual same-family bootstrap. A failed
bootstrap is an infrastructure error. The suite does not kill processes or
work around vendor configuration with GUI actions. It does not restore the
previous simulator application; use a dedicated simulator and preserve it first.

## Authoring and private evaluation

`iec_cases.py` holds only public task contracts. `iec_fixtures.py` holds the
private ordered inputs/expected values. `iec_reference.py` supplies scripted
native references and single-fault mutants; these are never model tools or
prompt resources. An implementation agent can read these files; the benchmark
model receives a constrained provider/MCP adapter, with no shell or filesystem.

The adapter exposes `submit_candidate`, case-only section/declaration reads,
language references, analyze/build/save, and documentation tools when enabled.
It does not expose arbitrary open/import/export paths, resources, live tags,
hardware operations or private projects. `submit_candidate` accepts inline ST
or native section XML plus declared scalar helpers. It validates the submission
before sending any engineering mutation. Original demo sections/declarations
are not exposed through the structure/declaration tools.

The permitted authoring subset is deliberately local: BOOL/INT/DINT helpers,
typed decimal integer literals, ST arithmetic/conversions and conditional
statements, boolean IL instructions, LD contacts/coils, and elementary
boolean/INT-comparison FBD blocks. FBD also permits explicitly declared native
RS/SR bistable instances. There are no arbitrary project function blocks,
loops, located variables, system words, external
calls or addresses. Unsupported syntax is returned as a public tool error.
SFC helpers are simple combinational assignments. A post helper can read native
step `.x` state and constants; it cannot read inputs/helper memory to implement
a separate state machine. Ordinary output assignments in inline native step
actions are supported, with action references resolved inside the candidate.
Constant output bugs remain functional mismatches with a percentage score.
A native three-step chart with initial Idle is required.
This restriction is part of the benchmark configuration, identical in A/B.

Generation operates on the public blank copy. After it ends, the adapter is
frozen. The trusted harness checks actual native language, declarations and
structure, builds and saves the candidate, and records its source/project hashes.
Only the candidate and allowed scalar helpers enter a fresh private demo copy.
No private failure feedback is returned for model repair.

The private project appends these sections after the original demo MAST logic:

1. `IEC_<language>_Before`: applies the whole input vector in the task.
2. SFC combinational pre helper, when applicable.
3. Native `IEC_<language>_Candidate`.
4. SFC step-state publication helper, when applicable.
5. `IEC_<language>_After`: records actual inputs, outputs, vector and cycle.

The runner verifies this order and preserves the original demo tasks and section
ordering. Capture is inside MAST, independent of host polling rate. Inputs are
compiled into the private instrumentation before download; expected outputs
remain on the host. This scalar-buffer implementation avoids requiring OFS
array access. SFC records all four scans and grades the fourth. Other cases
record and grade one scan per vector. The final buffer stays frozen after done.

Fixture inputs are preloaded into reserved scalar PLC variables before ready;
the task copies a whole vector from those variables before candidate execution.
OFS reads use a bounded readiness deadline, including symbol refresh after a
new application download. Every actual OPC reply, including bad-quality startup
replies, is retained in the evaluation evidence. No write is retried. Neither
readiness polling nor reading the frozen buffer determines PLC sampling time.

Each execution downloads a fresh private copy, initializes it, starts it with
neutral BOOL commands, verifies initial outputs and capture identity, and then
starts the scenario. The runner verifies good-quality data, completion/count,
indices, actual applied inputs, types and stable identity before grading.
Second reference executions validate reset independence in real simulator runs.
COM timeouts retain the existing lock/taint recovery rules; no mutation replay.

## Percentage and strict acceptance

For a structurally valid, built candidate with a complete valid capture:

`correctness_percent = 100 * matched_output_cells / evaluated_output_cells`

There are respectively 10, 11, 12, 26 and 16 evaluated output cells for ST, LD,
FBD, SFC and IL. SFC intermediate scans are diagnostic and add no denominator.
The report includes matched/evaluated counts, per-vector scores, every available
mismatch and the first mismatch with 1-based vector/cycle and expected/observed
values. A score below 100% has verdict `output_mismatch`. Strict `pass` also
requires valid structure, native language, successful build and trustworthy capture.

`artifact_invalid`, `build_failed`, `infrastructure_error` and
`unsupported_authoring` have **unknown correctness**, represented by JSON null
and gray cells in the graphic, rather than an invented 0%. Reports show verified
and unverified attempt counts. They provide both output-cell-weighted correctness
and a mean percentage over verified attempts; these are different denominators.

Each campaign writes `plan.json`, per-attempt `summary.json`, `artifact.json`,
build logs, capture/identity data, `iec-report.json`/`.md`, `outcome.json`, and
an `overview.png`/`.svg`/`.json` when matplotlib is installed. The overview is a
case/configuration correctness matrix beside a strict-verdict stacked bar chart.
Different campaigns, fingerprints, conditions and reference/mutant/model evidence
are displayed separately. Missing scheduled attempts remain visible as unverified.
The graphic labels model runs with the requested model and labels scripted
evidence explicitly. Its JSON records the graphic generator hash separately
from each immutable data fingerprint.
The generic compare/archive paths also retain IEC correctness fields.

Preparation proves native reference import/build/save/reopen support, not LLM
authoring or simulator semantics. A failed model submission on a supported path
is not `unsupported_authoring`. `validate` is scripted evidence, never model
performance. Native compatibility and live acceptance must be established on
the installed CE 16.4/M580/OFS environment; offline tests alone cannot establish them.

## Validation map

| Requirement | Automated offline evidence | Required installed-system evidence |
|---|---|---|
| Exact fixtures and interfaces | `FixtureTests`, independent oracle tests | Public/native project inspection |
| Six verdicts, typed comparisons and partial score | `GradeTests` | Real valid/invalid/build-failed candidates |
| Native authoring and isolation | `PolicyTests` | Five native import/build/reopen round trips; generated model artifacts |
| Deterministic capture | `CaptureTests`, order checks | Same-MAST execution, stable OFS scalar buffer |
| Reset and mutant acceptance | Two-reference schedule and mutant oracle tests | Two clean runs per native reference; mutant first divergences 6/4/6/3/13 |
| Wrong language and timeout | Policy/grader/timeout tests | Environment-specific integration where available |
| Reports and overview | `IntegrationTests` renders PNG/SVG/JSON | Saved actual campaign evidence |

The spec's minimal-new-project preparation is superseded here by the requested
demo-copy workflow and namespace mapping. Its logic, vectors, timing and verdict
requirements are retained. Full DeepSeek suite execution remains a separate task.

## Installed-system verification — 25 November 2026

Verified on Control Expert `V16.4` (native export header build `26196`), CPU
`BME P58 3040`, firmware `03.20`, PLC Simulator M580, OFS `3.63` with a 32-bit
OPC Automation worker. The operator approved simulator replacement/closed-loop
tests and confirmed `Dev_Alias_2` resolves to `MBT:127.0.0.1/U`.

The engineering preparation imported, built, saved, reopened and rebuilt all five
native references. The dedicated calibration campaign then passed all **15
acceptance checks**, with verified stop/disconnect/close cleanup:

| Language | Clean reference executions | Reference correctness | Mutant correctness | First mutant divergence |
|---|---:|---:|---:|---|
| ST | 2/2 pass | 100% | 70% | Vector 6, cycle 1 |
| LD | 2/2 pass | 100% | 81.82% | Vector 4, cycle 1 |
| FBD | 2/2 pass | 100% | 83.33% | Vector 6, cycle 1 |
| SFC | 2/2 pass | 100% | 96.15% | Vector 3, cycle 4 |
| IL | 2/2 pass | 100% | 93.75% | Vector 13, cycle 1 |

Local calibration evidence is under
`benchmarks/results/iec-development/20261125T195342Z-iec-cbf8bd13/`.
`outcome.json` records 15/15 completed and successful acceptance with cleanup
verified. The five expected mutant rejections are acceptance successes, not
strict functional passes. Reference/mutant graphics remain separate.

Three additional native authoring styles passed explicit Analyze, build and
simulator execution at **100%**: typed ST integer literals, a native RS-based FBD,
and SFC outputs assigned by inline native step actions without a publisher.
Their separate local evidence is under
`benchmarks/results/iec-development/20261125T203455Z-iec-authoring-365e6039/`,
including `authoring-analyze.json` with actual CE/CPU metadata.

The standalone offline `grade` command replayed the saved SFC mutant capture and
reproduced its 25/26 match count, 96.15% score and vector-3/cycle-4 mismatch.
Wrong-language, incomplete/bad-quality capture and timeout classification have
offline regressions. Readiness polling retains bad replies and never retries
the start write. Earlier infrastructure-development campaigns are retained
separately and are not pooled with these results.

These are **scripted engineering/simulator checks**, not LLM performance claims;
no paid provider requests were made. Model-generated delivery remains a separate
`run` campaign. Generated projects and raw local evidence stay ignored by Git.
The verification notes and authoring-policy refinements were made between
campaigns; each campaign retains its own source/data fingerprint.
