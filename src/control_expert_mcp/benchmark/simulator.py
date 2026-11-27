"""Opt-in M580 demo edit/build/deploy/counter benchmark; OPC DA, not UA."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import math
from pathlib import Path
import re
import shutil
import sys
from time import monotonic
import uuid

from ..opc import OpcClient
from .core import (Events, ce_lock, digest, environment, environment_record,
                   load_config, read_json, snapshot, write_json)
from .provider import client_factory, workflow
from .runner import clean_build, require_build, verify_version
from .transport import Evidence, MCP, plain, tool_value, visible_payload

TAG = "TEST_LLM"
RUBRIC = "simulator-counter-1"
OBSERVATION = {"duration_seconds": 8.0, "poll_seconds": 0.1,
               "max_sample_gap": 0.35, "min_increments": 6,
               "interval_tolerance": 0.35, "mean_period_tolerance": 0.15}
SETTINGS = {"unity.dataDictionary": "1", "unity.dataDictionaryOnlyHMIvariables": "0"}
ORIENTATION = (
    "Work only on the disposable M580 demo copy named in the task. The operator "
    "approved replacing the local simulator application, live OPC DA access and "
    "closed-loop simulator control, confirmed OFS running and its loopback alias. "
    "The harness recorded consent; check get_live_access_setup, do not ask again. "
    "Only MAST/LLM and new TEST_LLM/LLM_* declarations are editable. Preserve the "
    "rest of the demo. Only the local simulator is available; no physical PLC, "
    "Modbus, OPC writes or arbitrary paths. Dictionary settings are prepared. "
    "Use the listed tools; MCP prompts/resources are not automatically loaded. "
    "The independent evaluator reads TEST_LLM over OPC DA after you finish. "
    "Leave the simulator running for evaluation; the harness stops/disconnects "
    "afterwards. Do not write the counter over OPC to fabricate increments."
)


def task_prompt(path: Path, alias: str) -> str:
    return (
        f"Open the disposable copy of demo_ControlExpert_M580 at {path}. "
        "Create a new ST section MAST/LLM and a numeric global TEST_LLM. Add logic "
        "so TEST_LLM increments by exactly 1 every second while the application "
        "runs. You may choose the implementation; helper variables must start "
        "with LLM_. Build, diagnose and fix any errors until built_ok with no "
        "error. Save the working copy, download to the local PLC Simulator and "
        "RUN. Verify application consistency, then connect to the approved OFS "
        f"OPC DA alias {alias}, discover TEST_LLM and read it repeatedly with "
        "good quality to check one-second increments. Report observed values "
        "and timing, not just build or transfer success. Leave RUN for the judge."
    )


def grade_samples(samples: list[dict]) -> dict:
    """Accept existence and repeated +1/second behavior, independent of model prose.

    Sampling cannot prove scan-level timing. Bad/missing quality and observation
    gaps exceeding the published resolution leave timing unverified.
    """
    checks = {"variable_exists": False, "unit_increments": False,
              "one_second_period": False}
    result = {"rubric": RUBRIC, "success": False, "runtime_behavior": "unverified",
              "runtime_checks": checks, "observation_policy": OBSERVATION}
    if len(samples) < 2:
        return result
    if not all(s.get("good") is True and isinstance(s.get("value"), (int, float))
               and not isinstance(s["value"], bool) and math.isfinite(s["value"])
               for s in samples):
        return result
    checks["variable_exists"] = True
    times = [s["elapsed"] for s in samples]
    gaps = [b - a for a, b in zip(times, times[1:])]
    if (not all(math.isfinite(t) for t in times) or not all(0 < g <= OBSERVATION["max_sample_gap"] for g in gaps)
            or times[-1] - times[0] < OBSERVATION["duration_seconds"] - 0.2):
        return result
    transitions = []
    unit = True
    for previous, current in zip(samples, samples[1:]):
        delta = current["value"] - previous["value"]
        if abs(delta) <= 1e-6:
            continue
        unit &= abs(delta - 1) <= 1e-6
        transitions.append(current["elapsed"])
    checks["unit_increments"] = unit and len(transitions) >= OBSERVATION["min_increments"]
    intervals = [b - a for a, b in zip(transitions, transitions[1:])]
    mean = sum(intervals) / len(intervals) if intervals else None
    checks["one_second_period"] = bool(intervals) and all(
        abs(period - 1) <= OBSERVATION["interval_tolerance"] for period in intervals
    ) and abs(mean - 1) <= OBSERVATION["mean_period_tolerance"]
    result.update(increments=len(transitions), intervals_seconds=intervals,
                  mean_period_seconds=mean, first_value=samples[0]["value"],
                  last_value=samples[-1]["value"])
    result["success"] = all(checks.values())
    result["runtime_behavior"] = "pass" if result["success"] else "fail"
    return result


async def observe(client, *, clock=monotonic, sleep=asyncio.sleep) -> list[dict]:
    start = clock()
    samples = []
    while True:
        began = clock()
        response = await asyncio.to_thread(client.read, [TAG])
        ended = clock()
        sample = response.get("samples", {}).get(TAG, {})
        samples.append({"elapsed": (began + ended) / 2 - start,
                        "read_seconds": ended - began,
                        "value": response.get("values", {}).get(TAG),
                        "good": sample.get("good") is True and not response.get("errors"),
                        "device_timestamp": sample.get("timestamp"),
                        "quality": sample.get("quality"), "errors": response.get("errors", {})})
        if ended - start >= OBSERVATION["duration_seconds"]:
            return samples
        await sleep(OBSERVATION["poll_seconds"])


def valid_declaration(name: str) -> bool:
    return name == TAG or bool(re.fullmatch(r"LLM_[A-Za-z0-9_]+", name))


class SimulatorMCP(MCP):
    """Restrict model edits to LLM and control to the explicitly approved simulator."""
    def __init__(self, condition, config, evidence, path: Path, alias: str, existing=()):
        super().__init__(condition, config, evidence)
        self.path, self.alias = path.resolve(), alias
        self.existing = {name.casefold() for name in existing}
        self.model_calls = []
        self.opened = self.built = self.deployed = self.simulator_connected = False
        self.downloaded = False  # This case transferred at least once.
        self.connection_configured = False

    def server_environment(self):
        return {**environment(self.condition), "CE_MCP_ENABLE_ONLINE": "1"}

    def adapter(self, task):
        allowed = {"get_live_access_setup", "get_status", "open_project", "get_project_structure",
                   "list_variables", "read_section", "get_language_reference", "create_variable",
                   "write_st_logic", "analyze_project", "build_project", "save_project",
                   "start_simulator", "plc_setup_connection", "plc_connect", "plc_state",
                   "plc_command", "plc_transfer", "opc_connect", "opc_status", "opc_browse",
                   "opc_read_tags", "opc_disconnect"}
        if allowed - {tool["name"] for tool in self.tools}:
            raise ValueError("Missing required simulator benchmark tools")
        return self.instructions + "\n" + ORIENTATION, [
            {"type": "function", "name": tool["name"], "description": tool.get("description", ""),
             "parameters": tool["input_schema"], "strict": False}
            for tool in self.tools if tool["name"] in allowed]

    def policy_error(self, name, args, schemas):
        if name not in {s["name"] for s in schemas}:
            return "Tool unavailable in simulator counter benchmark"
        if name == "open_project":
            if Path(args.get("path", "")).resolve() != self.path:
                return "Open only the disposable demo copy"
        elif name not in {"get_live_access_setup", "get_status"} and not self.opened:
            return "Open the disposable demo copy first"
        if name == "save_project" and args.get("path") and Path(args["path"]).resolve() != self.path:
            return "Save only the disposable demo copy"
        if name == "write_st_logic":
            if args.get("task") != "MAST" or args.get("section") != "LLM":
                return "Only MAST/LLM is editable"
            names = [pair.partition(":")[0].strip() for pair in args.get("declare", "").split(",") if pair.strip()]
            if any(not valid_declaration(n) or n.casefold() in self.existing for n in names):
                return "Only new TEST_LLM/LLM_* declarations are allowed"
        if name == "create_variable" and (not valid_declaration(args.get("name", ""))
                                          or args["name"].casefold() in self.existing or args.get("address")):
            return "Only new unlocated TEST_LLM/LLM_* variables are allowed"
        if name == "plc_setup_connection" and (
            args.get("target", "simulator") != "simulator" or args.get("address") != "127.0.0.1"
            or args.get("driver") != "TCPIP"):
            return "Only simulator/127.0.0.1/TCPIP is approved"
        if name == "plc_connect" and (not self.connection_configured
                                      or args.get("target", "simulator") != "simulator"
                                      or args.get("mode", "primary") != "primary"):
            return "Configure simulator/127.0.0.1/TCPIP first; connect only to that simulator"
        if name == "plc_transfer" and (args.get("direction", "pc_to_plc") != "pc_to_plc"
                                       or not self.built or not self.simulator_connected):
            return "Download requires a successful current build and simulator connection"
        if name == "plc_command" and (args.get("command") not in {"stop", "run"}
                                      or not self.simulator_connected
                                      or args.get("command") == "run" and not self.deployed):
            return "Only stop/run on the connected simulator; run requires this case's download"
        if name == "opc_connect" and (
            args.get("alias", self.alias) not in ("", self.alias)
            or args.get("progid", "Schneider-Aut.OFS.2") != "Schneider-Aut.OFS.2"
            or args.get("automation_progid", "OPC.Automation") != "OPC.Automation"):
            return "Only the approved OFS alias/server is available"
        if name == "opc_browse" and args.get("branches", []) not in ([], [self.alias]):
            return "Browse only the approved alias"
        if name == "opc_read_tags" and any(tag not in (TAG, self.alias + "!" + TAG) for tag in args.get("tags", [])):
            return "Only TEST_LLM is readable through OPC"
        return None

    async def dispatch(self, name, arguments, schemas):
        error = self.policy_error(name, arguments, schemas)
        if error:
            self.model_calls.append({"tool": name, "policy_violation": True})
            return {"is_error": True, "error": error}
        if name in {"open_project", "write_st_logic", "create_variable"}:
            self.built = self.deployed = False
        result = await self.call(name, arguments)
        value = {} if result.is_error else tool_value(result)
        if not result.is_error:
            if name == "open_project":
                self.opened = True
                self.downloaded = False
                self.connection_configured = False
            elif name == "plc_setup_connection":
                self.connection_configured = True
            elif name == "build_project":
                self.built = clean_build(value)
                # A connected build after this case's own download is an online change;
                # CE then reports the running application equal to the project.
                target = value.get("target_after_build") or {}
                if (self.built and self.downloaded and value.get("online_change_applied")
                        and target.get("pc_equals_plc") is True):
                    self.deployed = True
            elif name == "plc_connect":
                self.simulator_connected = value.get("connected") is True
            elif name == "plc_transfer":
                self.deployed = value.get("transferred") == "pc_to_plc"
                self.downloaded = self.downloaded or self.deployed
        self.model_calls.append({"tool": name, "arguments": arguments, "value": value,
                                 "is_error": result.is_error})
        return visible_payload(plain(result))


async def prepare(config: dict) -> Path:
    """Prepare a disposable native demo baseline offline; never download."""
    directory = Path(config["workspace"]) / ("prepare-" + uuid.uuid4().hex[:12])
    directory.mkdir(parents=True)
    output = directory / "baseline.stu"
    shutil.copyfile(config["fixture"], output)
    source_hash = digest(Path(config["fixture"]).read_bytes())
    evidence = Evidence(directory, Events(directory / "events.jsonl"))
    async with MCP(config["conditions"]["SIMULATOR"], config, evidence) as mcp:
        if (await mcp.checked("get_status")).get("session") != "no application open":
            raise RuntimeError("Use a dedicated CE session; a project is already open")
        await mcp.checked("open_project", path=str(output))
        status = await verify_version(mcp, config)
        if status.get("project", {}).get("cpu") is None or any(
            status["project"]["cpu"].get(key) != value for key, value in config["cpu"].items()
        ):
            raise ValueError("Demo CPU/version differs from benchmark configuration")
        structure = await mcp.checked("get_project_structure")
        if any(s["name"].casefold() == "llm" for t in structure["tasks"] for s in t["sections"]):
            raise ValueError("Demo must not already contain an LLM section")
        variables = await mcp.checked("list_variables", max_results=1000000)
        if variables["returned"] != variables["total_variables"]:
            raise RuntimeError("Incomplete declaration inventory")
        existing = [v["name"] for v in variables["variables"]]
        if TAG.casefold() in {n.casefold() for n in existing}:
            raise ValueError("Demo must not already contain TEST_LLM")
        await mcp.checked("set_project_settings", settings=SETTINGS)
        for key, value in SETTINGS.items():
            if int((await mcp.checked("get_project_setting", ident=key))["value"]) != int(value):
                raise RuntimeError("Required dictionary setting did not persist")
        build = await mcp.checked("build_project", rebuild_all=True)
        require_build(build)
        await mcp.checked("save_project")
        await mcp.checked("close_project", save=False)
    if digest(Path(config["fixture"]).read_bytes()) != source_hash:
        raise RuntimeError("Source demo changed during preparation")
    manifest = {"source_sha256": source_hash, "baseline": str(output),
                "baseline_sha256": digest(output.read_bytes()), "existing_variables": existing,
                "ce_status": status, "build": build, "settings": SETTINGS,
                "cpu": config["cpu"], "ce_version": config["ce_version"]}
    destination = Path(config["workspace"]) / "simulator-manifest.json"
    write_json(destination, manifest)
    return destination


async def scripted(mcp, schemas):
    """No-API feasibility path; not evidence of LLM performance."""
    async def call(name, **args):
        result = await mcp.dispatch(name, args, schemas)
        if result.get("is_error"):
            raise RuntimeError("Scripted simulator step failed: " + name)
        return result
    await call("open_project", path=str(mcp.path))
    await call("write_st_logic", task="MAST", section="LLM",
               st_source="LLM_Timer(IN := NOT LLM_Timer.Q, PT := T#1s);\n"
                         "IF LLM_Timer.Q THEN TEST_LLM := TEST_LLM + 1; END_IF;",
               declare="TEST_LLM:DINT, LLM_Timer:TON")
    await call("build_project")
    if not mcp.built:
        raise RuntimeError("Reference counter did not build")
    await call("save_project")
    await call("start_simulator")
    await call("plc_setup_connection", target="simulator", address="127.0.0.1", driver="TCPIP")
    await call("plc_connect", target="simulator")
    await call("plc_command", command="stop")
    await call("plc_transfer", direction="pc_to_plc")
    await call("plc_command", command="run")
    await call("opc_connect")
    await call("opc_read_tags", tags=[TAG])


async def run_case(config, case, manifest, directory, fingerprint, alias, mode, factory=None,
                   expected_context=None):
    directory.mkdir(parents=True)
    output = directory / "project.stu"
    shutil.copyfile(manifest["baseline"], output)
    evidence = Evidence(directory, Events(directory / "events.jsonl"))
    result = {**case, "fingerprint": fingerprint, "status": "startup_failure", "success": False,
              "requested_model": config["model"]["id"], "provider": config["provider"]["name"],
              "model_identity": config["model"].get("identity", "pinned"), "cold_start": True,
              "validation": {"success": False, "runtime_behavior": "unverified", "rubric": RUBRIC}}
    condition = config["conditions"]["SIMULATOR"]
    judge = OpcClient(python=condition.get("env", {}).get("CE_MCP_OPC_PYTHON"))
    started = monotonic()
    try:
        async with SimulatorMCP(condition, config, evidence, output, alias, manifest["existing_variables"]) as mcp:
            result.update(startup_seconds=mcp.startup_seconds, discovery_seconds=mcp.discovery_seconds)
            result["effective_context_sha256"] = digest([*mcp.adapter(case["task"]), mcp.initialization])
            if expected_context and result["effective_context_sha256"] != expected_context:
                raise ValueError("Server context changed after preflight; start a new campaign")
            await mcp.checked("configure_live_access", allow_live_connection=True, protocol="opc",
                              ofs_alias=alias, opc_server_confirmed_running=True, allow_closed_loop=True)
            try:
                result["status"] = "workflow_failure"
                mcp.phase = "workflow"
                try:
                    if mode == "run":
                        async with factory() as provider:
                            await workflow(mcp, case["task"], config, provider, evidence, result,
                                           prompt=task_prompt(output, alias))
                    else:
                        await scripted(mcp, mcp.adapter(case["task"])[1])
                        result["status"] = "completed"
                except Exception as exc:
                    result.update(status="timeout" if isinstance(exc, TimeoutError) else "workflow_failure",
                                  failure_reason=type(exc).__name__)
                if not mcp.tainted and mcp.deployed:
                    mcp.phase = "evaluation"
                    result["ce_status"] = await verify_version(mcp, config)
                    result["deployment_state"] = await mcp.checked("plc_state")
                    # State is evidence of target attribution, not an extra score.
                    state = result["deployment_state"]
                    if state.get("connected") and state.get("pc_equals_plc") and state.get("plc_state") == "run":
                        await asyncio.to_thread(judge.connect, "Schneider-Aut.OFS.2", alias)
                        samples = await observe(judge)
                        write_json(directory / "counter-samples.json", samples)
                        result["validation"] = grade_samples(samples)
                        evidence.events.emit("independent_evaluation", samples_ref=evidence.blob(samples),
                                             validation=result["validation"])
                    section = await mcp.checked("read_section", task="MAST", section="LLM")
                    (directory / "saved-section.xml").write_text(section["xml"], encoding="utf-8")
                    await mcp.checked("save_project")
                result["success"] = result["validation"]["success"]
            finally:
                result["validation"]["compile_pass"] = mcp.built
                result["model_calls_ref"] = evidence.blob(mcp.model_calls)
                if mcp.tainted:
                    result["cleanup"] = {"verified": False, "reason": "CE tainted; operator recovery required"}
                else:
                    mcp.phase = "cleanup"
                    try:
                        if mcp.simulator_connected:
                            state = await mcp.checked("plc_state")
                            if state.get("plc_state") == "run":
                                state = await mcp.checked("plc_command", command="stop")
                            if state.get("plc_state") not in {"stop", "no_conf"}:
                                raise RuntimeError("Simulator idle state not confirmed")
                            await mcp.checked("plc_disconnect")
                        await mcp.checked("opc_disconnect")
                        if mcp.opened:
                            await mcp.checked("close_project", save=False)
                        result["cleanup"] = {"verified": True}
                    except Exception as exc:
                        result["cleanup"] = {"verified": False, "error": type(exc).__name__}
    except Exception as exc:
        result["failure_reason"] = type(exc).__name__
        if result["status"] == "completed":
            result["status"] = "evaluation_failure"
        evidence.events.emit("case_exception", error=type(exc).__name__)
    finally:
        try:
            await asyncio.to_thread(judge.disconnect)
        except Exception as exc:
            result["judge_cleanup_error"] = type(exc).__name__
            result["cleanup"] = {"verified": False, "reason": "Judge disconnect failed"}
        # Artifact/provider failures do not change the requested behavioral rubric.
        result["success"] = result["validation"]["success"]
        result.update(total_seconds=monotonic() - started, durable_completed=True)
        (directory / "final-response.txt").write_text(result.get("final_response", ""), encoding="utf-8")
        write_json(directory / "validation.json", result["validation"])
        write_json(directory / "summary.json", result)
    return result


async def campaign(config, args):
    manifest = read_json(Path(config["workspace"]) / "simulator-manifest.json")
    if (digest(Path(config["fixture"]).read_bytes()) != manifest["source_sha256"]
            or digest(Path(manifest["baseline"]).read_bytes()) != manifest["baseline_sha256"]
            or config["cpu"] != manifest["cpu"] or config["ce_version"] != manifest["ce_version"]):
        raise ValueError("Demo/baseline changed; prepare a new simulator baseline")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-simulator-" + uuid.uuid4().hex[:8]
    directory = Path(config["results"]) / run_id
    schedule = [{"case_id": f"simulator-counter-{i:03d}", "task": "simulator_counter",
                 "repeat": i, "condition": "SIMULATOR"} for i in range(args.repeats)]
    snap = snapshot(config)
    snap.update(suite="simulator-counter", rubric_version=RUBRIC, orientation=ORIENTATION,
                prompts={"simulator_counter": task_prompt(Path("<disposable-demo-copy>"), args.alias)},
                observation_policy=OBSERVATION, baseline_sha256=manifest["baseline_sha256"])
    env = {**environment(config["conditions"]["SIMULATOR"]), "CE_MCP_ENABLE_ONLINE": "1"}
    snap["servers"]["SIMULATOR"]["environment"] = environment_record(env)
    evidence = Evidence(directory / "preflight", Events(directory / "preflight" / "events.jsonl"))
    async with SimulatorMCP(config["conditions"]["SIMULATOR"], config, evidence,
                            directory / "preflight.stu", args.alias) as mcp:
        context = digest([*mcp.adapter("simulator_counter"), mcp.initialization])
    fingerprint = digest([snap, schedule, args.alias, args.command, context])
    write_json(directory / "plan.json", {"run_id": run_id, "snapshot": snap, "schedule": schedule,
               "fingerprint": fingerprint, "seed": 0, "alias": args.alias, "protocol": "opc-da",
               "mode": args.command, "paid_requests": args.command == "run", "contexts": context})
    factory = client_factory(config) if args.command == "run" else None
    results = []
    try:
        for case in schedule:
            if digest(Path(manifest["baseline"]).read_bytes()) != manifest["baseline_sha256"]:
                raise ValueError("Prepared baseline changed during campaign")
            result = await run_case(config, case, manifest, directory / case["case_id"] / "attempt-001",
                                    fingerprint, args.alias, args.command, factory, context)
            results.append(result)
            if not result.get("cleanup", {}).get("verified"):
                raise RuntimeError("Simulator cleanup unverified; stop campaign and inspect local evidence")
    finally:
        write_json(directory / "outcome.json", {
            "success": len(results) == len(schedule) and all(r["success"] for r in results),
            "cleanup_verified": bool(results) and all(r.get("cleanup", {}).get("verified") for r in results),
            "cases": len(results), "mode": args.command})
    return directory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "validate", "run"):
        sub = subs.add_parser(command)
        sub.add_argument("--config", required=True)
        if command != "prepare":
            sub.add_argument("--alias", required=True, help="User-confirmed OFS alias pointing to PLC Simulator")
            for flag in ("allow-live", "confirm-ofs-running", "allow-closed-loop", "allow-simulator-replacement"):
                sub.add_argument("--" + flag, action="store_true", required=True)
            sub.add_argument("--repeats", type=int, default=1)
            sub.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if set(config["conditions"]) != {"SIMULATOR"}:
            raise ValueError("Configure exactly the SIMULATOR condition")
        if config["conditions"]["SIMULATOR"]["documentation"]:
            raise ValueError("Simulator suite uses the embedded language reference; set documentation=false")
        if Path(config["fixture"]).suffix.lower() != ".stu":
            raise ValueError("fixture must be the native demo_ControlExpert_M580.STU")
        if args.command != "prepare" and (args.repeats < 1 or not args.alias.strip()):
            raise ValueError("Positive repeats and an explicit OFS alias are required")
        if args.command != "prepare" and args.dry_run:
            print('{"paid_requests":0,"live_connections":0,"suite":"simulator-counter","protocol":"opc-da"}')
            return 0
        if args.command == "run" and "REPLACE" in config["model"]["id"]:
            raise ValueError("Configure an exact provider model before a paid run")
        with ce_lock(Path(config["workspace"])):
            output = asyncio.run(prepare(config) if args.command == "prepare" else campaign(config, args))
            print(output)
            if args.command == "validate" and not read_json(output / "outcome.json")["success"]:
                return 1
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        print("Simulator benchmark failed: " + type(exc).__name__, file=sys.stderr)
        if isinstance(exc, (ValueError, FileNotFoundError)):
            print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
