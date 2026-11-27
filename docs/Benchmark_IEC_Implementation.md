# IEC benchmark (`ce-bench iec`)

Five native-language cases authored by an LLM through MCP, built in Control
Expert, run on PLC Simulator M580 and graded from an in-PLC capture read via OFS.
Verified environment: CE V16.4, BME P58 3040 firmware 03.20, OFS 3.63 with
a 32-bit OPC Automation worker.

## Cases

Public contracts (interface, requirement, initial state, cycles) are in
`benchmark/iec_cases.py`; private ordered vectors and expected outputs are in
`benchmark/iec_fixtures.py`; scripted native references and single-fault mutants
are in `benchmark/iec_reference.py`. Logical names below are prefixed
`IEC_<lang>_` in the project (e.g. `Raw` -> `IEC_ST_Raw`).

| Case | Inputs -> outputs | Rule | Vectors x cycles | Mutant (first divergence) |
|---|---|---|---|---|
| `iec_st_clamp` | Raw, Offset: INT -> Result: INT | clamp(Raw - Offset, 0, 1000) over the full INT domain | 10 x 1 | limit 999 (vector 6) |
| `iec_ld_latch` | StartCmd, StopCmd, Permit -> Running | Stop or not Permit clears; else Start sets; else hold | 11 x 1 | Start priority (vector 4) |
| `iec_fbd_hysteresis` | LevelValue: INT, EnableCmd -> Demand | disabled clears; <=30 sets; >=70 clears; else hold | 12 x 1 | `>70` release (vector 6) |
| `iec_sfc_sequence` | StartCmd, DoneCmd, AckCmd -> Busy, Complete | native chart Idle -> Active -> Completed -> Idle, each step on its command alone | 13 x 4 | Start accepted with Done high (vector 3, cycle 4) |
| `iec_il_select` | SignalA, SignalB, OverrideCmd, EnableCmd -> Selected | Enable AND (Override OR (A XOR B)) | 16 x 1 | OR instead of XOR (vector 13) |

Unlisted types are BOOL; outputs start FALSE/0; state persists across vectors. SFC steps are `IEC_SFC_Idle`,
`IEC_SFC_Active`, `IEC_SFC_Completed`; optional combinational helpers are
`IEC_SFC_LLM_Pre`/`IEC_SFC_LLM_Post`.

## Setup

- Windows, licensed CE, PLC Simulator M580, OFS; `pip install -e ".[benchmark]"`.
- Copy `benchmarks/iec.example.json` to an ignored local file (paths are relative
  to the JSON). Set `fixture` (normally `samples/demo_ControlExpert_M580.STU`),
  `cpu`, `ce_version`, `model.id` (`run` refuses `REPLACE...`), provider and
  conditions A (no docs) / B (`documentation: true`).
- Set `CE_MCP_OPC_PYTHON` in the condition `env` to a Python whose bitness
  matches OPC Automation. Other vendor prerequisites: `benchmarks/README.md`.
- Every project is a disposable copy of the demo STU (hardware, tasks and
  sections preserved; source hashed).

## Commands

```powershell
# Plan only; no side effects.
ce-bench iec run --config <cfg> --case all --dry-run

# Build/reopen native references; no download.
ce-bench iec prepare --config <cfg> --condition A --case all

# Scripted acceptance: per case/condition, max(2, --repeats) clean references + 1 mutant.
ce-bench iec validate --config <cfg> --condition A --case all --alias <alias> <consent flags>

# Paid model authoring + private evaluation.
ce-bench iec run --config <cfg> --condition A B --case all --repeats 1 --alias <alias> <consent flags>

# Offline: replay a saved capture (IDs in capture-identity.json); overview of saved campaigns.
ce-bench iec grade --case iec_st_clamp --evidence evidence.json --capture capture.json --run-id <n> --artifact-id <n> --output validation.json
ce-bench iec overview --results benchmarks/results/iec --output benchmarks/results/iec/overview.png
```

`--case` takes `all` or one ID. `validate`/`run` also accept `--seed` (default
1729) and `--stop-on-infrastructure-error` (stop at a case boundary after cleanup).
Run `prepare` first; campaigns need its workspace `iec-manifest.json`.

## Consent and safety

`validate` and `run` require `--alias` plus all of `--allow-live
--confirm-ofs-running --allow-closed-loop --allow-simulator-replacement
--confirm-simulator-alias`. The alias must resolve to `MBT:127.0.0.1/U`; never
point it at physical hardware. Download targets only `simulator/127.0.0.1/TCPIP`.
The simulator application is replaced and not restored: use a dedicated
simulator and an idle CE session. A fresh simulator may need the manual
same-family bootstrap. The suite never kills processes, edits OFS aliases or
retries the single OPC start write.

## Authoring and isolation

The model gets a constrained adapter (no shell/filesystem): `submit_candidate`
(inline ST or native section XML plus scalar helpers), case-only section and
declaration reads, language references, analyze/build/save, and documentation in
condition B. Allowed: `IEC_<lang>_LLM_*` BOOL/INT/DINT helpers, typed decimal
literals, ST arithmetic/conversions/conditionals, IL boolean instructions, LD
contacts/coils, elementary boolean/INT-comparison FBD blocks and declared RS/SR
instances. Not allowed: loops, project FBs, located variables, system words,
external calls, `Bench_` access. SFC helpers are combinational and cannot replace
chart state. Fixtures, references, private projects and private results are
never exposed to the model.

## Evaluation

The frozen artifact is checked (language, declarations, structure), built and
hashed; only the candidate and helpers enter a fresh private demo copy. MAST section order:
`IEC_<lang>_Before` (applies the whole vector) -> SFC pre helper -> candidate ->
SFC post helper -> `IEC_<lang>_After` (records inputs/outputs/vector/cycle). Inputs
are compiled into scalar PLC variables; expected values stay on the host. The
runner verifies initial outputs and run/candidate identity before writing
`Bench_Start`, then validates capture quality, count, indices and applied inputs.

## Scoring (`iec_grade.py`)

Checked in order: `unsupported_authoring`, `artifact_invalid`, `build_failed`,
`infrastructure_error` (missing evidence or untrustworthy capture), then
`output_mismatch` / `pass`. For a valid capture:

`correctness_percent = 100 * matched_output_cells / evaluated_output_cells`

Evaluated cells: ST 10, LD 11, FBD 12, SFC 26, IL 16. Only the last cycle of each
vector is graded (SFC cycle 4; earlier cycles are diagnostic). Strict `pass`
needs 100%. The first four verdicts have `correctness_percent: null` (gray in
graphics), not 0. Results list per-vector scores and every mismatch (1-based vector/cycle,
expected/observed).

## Outputs

Each campaign directory holds `plan.json`, per-attempt `summary.json`,
`artifact.json`, build logs, `capture.json`, `capture-identity.json`,
`iec-report.json`/`.md`, `outcome.json` (`stop.json` if stopped early) and, with
matplotlib, `overview.png`/`.svg`/`.json`: a case x configuration correctness
matrix beside strict-verdict bars. Reports give cell-weighted correctness, the
mean over verified attempts and verified/unverified counts. Scripted
references/mutants (`validate`) are never reported as model performance. Keep
generated projects and raw evidence out of Git.
