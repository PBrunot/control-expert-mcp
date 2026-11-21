"""Opt-in live OPC benchmark. Only `run` sends paid model requests.

The operator deploys the simple fixture to PLC Simulator explicitly; the model
can only browse/read it and write three inputs. A separate OPC client grades
device values and restores the initial inputs. Offline benchmarks stay offline.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sys
import time
import uuid

from ..opc import OpcClient
from .core import (Events, ce_lock, digest, environment, environment_record,
                   load_config, snapshot, write_json)
from .provider import client_factory, workflow
from .transport import Evidence, MCP, plain, tool_value, visible_payload

ALIAS = "Dev_Alias_2"
INPUTS = ["OPCBench_Enable", "OPCBench_Input", "OPCBench_Gain"]
OUTPUTS = ["OPCBench_Output", "OPCBench_Positive", "OPCBench_Tick"]
TAGS = INPUTS + OUTPUTS
RUBRIC = "opc-live-1"
ORIENTATION = (
    "This is a live OPC benchmark on PLC Simulator via OFS. The operator explicitly "
    "approved live connections and closed-loop tests and confirmed OFS is running. "
    "The harness has already recorded those answers with configure_live_access. "
    "Use get_live_access_setup to check them; do not ask again. Only the three "
    "OPCBench inputs are writable. No logic editing, PLC commands, transfer, Modbus, "
    "or arbitrary device access is permitted. Leave requested inputs in place for "
    "independent grading; the harness restores the original inputs in finally. "
    "A write acknowledgement alone does not prove execution: read input and output "
    "values through OPC after writing and check good quality."
)


def cases(repeats: int, seed: int, selected: str = "all") -> list[dict]:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    rng = random.Random(seed)
    rows = []
    for repeat in range(repeats):
        for name in ("positive", "negative", "disabled"):
            if selected != "all" and name != selected:
                continue
            number = rng.randint(5, 70) * (-1 if name == "negative" else 1)
            gain = rng.choice([0.5, 1.25, 1.5, 2.5])
            inputs = dict(zip(INPUTS, [name != "disabled", number, gain]))
            rows.append({"case_id": f"opc-{name}-{repeat:03d}", "task": "opc_" + name,
                         "repeat": repeat, "condition": "OPC", "inputs": inputs})
    rng.shuffle(rows)
    return rows


def expected(inputs: dict) -> dict:
    output = inputs["OPCBench_Input"] * inputs["OPCBench_Gain"] if inputs["OPCBench_Enable"] else 0.0
    return {**inputs, "OPCBench_Output": float(output), "OPCBench_Positive": output > 0}


def matches(actual: dict, wanted: dict) -> bool:
    return all(key in actual and type(actual[key]) is type(value) and actual[key] == value
               for key, value in wanted.items())


def prompt(case: dict) -> str:
    return (
        "Using the already-approved OFS connection and configured alias, discover the "
        "OPCBench variables. The running program computes Output = INT_TO_REAL(Input) "
        "* Gain when Enable is true, otherwise Output = 0.0; Positive means Output > 0. "
        "Tick increments every scan. Names have the prefix OPCBench_. Read the current "
        "values, then write ALL three inputs to: " + json.dumps(case["inputs"]) + ". "
        "Read ALL three inputs plus Output, Positive and Tick after your writes, "
        "check quality and confirm the program's calculated result. Do not write "
        "outputs. Leave the requested inputs set for independent evaluation."
    )


def grade(case: dict, calls: list[dict], observed: dict, tick_changed: bool, status: str) -> dict:
    wanted = expected(case["inputs"])
    written, last_write, violations = {}, -1, 0
    for index, call in enumerate(calls):
        violations += int(call.get("policy_violation", False))
        if call["tool"] == "opc_write_tags":
            acknowledged = call.get("value", {}).get("written", {})
            if acknowledged:
                last_write = index
                written.update(acknowledged)
    read_after_write = any(
        call["tool"] == "opc_read_tags" and matches(call.get("value", {}).get("values", {}), wanted)
        for call in calls[last_write + 1:]
    ) if last_write >= 0 else False
    checks = {"model_wrote_inputs": matches(written, case["inputs"]),
              "model_read_after_write": read_after_write,
              "independent_device_values": matches(observed.get("values", {}), wanted),
              "scan_counter_changed": tick_changed, "policy_respected": violations == 0}
    success = status == "completed" and all(checks.values())
    return {"rubric": RUBRIC, "runtime_behavior": "pass" if success else "fail",
            "scope": "OFS/PLC Simulator scalar input/output execution", "success": success,
            "runtime_checks": checks}


class LiveMCP(MCP):
    def __init__(self, condition, config, evidence, alias):
        super().__init__(condition, config, evidence)
        self.alias = alias
        self.model_calls = []

    def server_environment(self):
        env = environment(self.condition)  # strips credentials, normally forces offline
        env["CE_MCP_ENABLE_ONLINE"] = "1"  # only this explicitly invoked suite opts in
        return env

    def adapter(self, task):
        allowed = {"get_live_access_setup", "opc_connect", "opc_disconnect", "opc_status",
                   "opc_browse", "opc_read_tags", "opc_write_tags"}
        available = {tool["name"] for tool in self.tools}
        if allowed - available:
            raise ValueError("Missing OPC benchmark tools")
        return self.instructions + "\n" + ORIENTATION, [
            {"type": "function", "name": tool["name"], "description": tool.get("description", ""),
             "parameters": tool["input_schema"], "strict": False}
            for tool in self.tools if tool["name"] in allowed]

    def short(self, name):
        return name.removeprefix(self.alias + "!")

    async def dispatch(self, name, arguments, schemas):
        error = None
        if name not in {tool["name"] for tool in schemas}:
            error = "Tool unavailable under live benchmark policy"
        elif name == "opc_write_tags":
            if any(self.short(tag) not in INPUTS for tag in arguments.get("values", {})):
                error = "Only OPCBench_Enable, OPCBench_Input and OPCBench_Gain are writable"
        elif name == "opc_read_tags":
            if any(self.short(tag) not in TAGS for tag in arguments.get("tags", [])):
                error = "Only OPCBench variables are readable in this benchmark"
        elif name == "opc_connect":
            if arguments.get("alias", self.alias) not in ("", self.alias) or arguments.get("progid", "Schneider-Aut.OFS.2") != "Schneider-Aut.OFS.2" or arguments.get("automation_progid", "OPC.Automation") != "OPC.Automation":
                error = "Only the approved OFS server/alias is available"
        elif name == "opc_browse" and arguments.get("branches", []) not in ([], [self.alias]):
            error = "Browse only the approved alias"
        if error:
            self.model_calls.append({"tool": name, "policy_violation": True})
            return {"is_error": True, "error": error}
        result = await self.call(name, arguments)
        value = {} if result.is_error else tool_value(result)
        for field in ("values", "written"):
            if field in value:
                value[field] = {self.short(key): item for key, item in value[field].items()}
        self.model_calls.append({"tool": name, "value": value})
        return visible_payload(plain(result))


def prepare(config: dict) -> Path:
    from ..bridge import ControlExpertBridge
    directory = Path(config["workspace"]) / ("prepare-" + uuid.uuid4().hex[:10])
    directory.mkdir(parents=True)
    bridge = ControlExpertBridge()
    with ce_lock(Path(config["workspace"])):
        try:
            report = {"new": bridge.new_project(config["cpu"]["part_number"], config["cpu"]["version"])}
            report["import"] = bridge.import_xml(
                xml_content=Path(config["fixture"]).read_text(encoding="utf-8"), file_path=None,
                kind="section", task_name="MAST", import_mode="normal")
            settings = {"unity.dataDictionary": "1", "unity.dataDictionaryOnlyHMIvariables": "0",
                        "unity.dataDictionaryKeepOtherVariablesInReadOnly": "0"}
            report["settings"] = bridge.set_project_settings(settings)
            if any("<not found>" in entry for entry in report["settings"]["changed"]):
                raise RuntimeError("Required data dictionary settings not available")
            report["verified_settings"] = {key: bridge.get_project_setting(key) for key in settings}
            if any(int(report["verified_settings"][key]["value"]) != int(value) for key, value in settings.items()):
                raise RuntimeError("Data dictionary settings did not persist")
            report["build"] = bridge.build_project(True)
            if report["build"].get("build_state") != "built_ok" or report["build"].get("error"):
                raise RuntimeError("OPC fixture failed to build")
            report["save"] = bridge.save_project(str(directory / "opc-bench.stu"))
            report["project"] = bridge.get_status()
            write_json(directory / "preparation.json", report)
        finally:
            bridge.shutdown()
    return directory / "opc-bench.stu"


async def device_read(client, tags):
    result = await asyncio.to_thread(client.read, tags)
    if result["errors"]:
        raise RuntimeError("OPC prerequisite/read failed: " + str(result["errors"]))
    return result


async def device_write(client, values):
    result = await asyncio.to_thread(client.write, values)
    if result["errors"]:
        raise RuntimeError("OPC write failed: " + str(result["errors"]))
    return result


async def exercise(config, args) -> Path:
    if args.command == "run" and "REPLACE" in config["model"]["id"]:
        raise ValueError("Configure an exact provider model before a paid run")
    schedule = cases(args.repeats, args.seed, args.case)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-opc-" + uuid.uuid4().hex[:8]
    directory = Path(config["results"]) / run_id
    directory.mkdir(parents=True)
    condition = config["conditions"]["OPC"]
    snap = snapshot(config)
    snap.update(suite="opc-live", rubric_version=RUBRIC, orientation=ORIENTATION,
                prompts={row["task"]: prompt(row) for row in schedule})
    env = environment(condition)
    env["CE_MCP_ENABLE_ONLINE"] = "1"
    snap["servers"]["OPC"]["environment"] = environment_record(env)
    fingerprint = digest([snap, schedule, args.alias])
    plan = {"run_id": run_id, "snapshot": snap, "fingerprint": fingerprint,
            "seed": args.seed, "schedule": schedule, "alias": args.alias,
            "mode": args.command, "paid_requests": args.command == "run"}
    write_json(directory / "plan.json", plan)
    judge = OpcClient(python=condition.get("env", {}).get("CE_MCP_OPC_PYTHON"))
    originals = None
    outcome = {"success": False, "restoration_verified": False}
    try:
        outcome["ofs"] = await asyncio.to_thread(judge.connect, "Schneider-Aut.OFS.2", args.alias)
        before = await device_read(judge, TAGS)
        originals = {tag: before["values"][tag] for tag in INPUTS}
        tick_before = before["values"]["OPCBench_Tick"]
        await asyncio.sleep(.15)
        if (await device_read(judge, ["OPCBench_Tick"]))["values"]["OPCBench_Tick"] == tick_before:
            raise RuntimeError("OPCBench scan counter is not changing; start the fixture in PLC Simulator")
        factory = client_factory(config) if args.command == "run" else None
        for case in schedule:
            attempt = directory / case["case_id"] / "attempt-001"
            evidence = Evidence(attempt, Events(attempt / "events.jsonl"))
            result = {**case, "fingerprint": fingerprint, "provider": config["provider"]["name"],
                      "requested_model": config["model"]["id"], "model_identity": config["model"].get("identity", "pinned"),
                      "cold_start": True, "status": "failed", "success": False}
            try:
                # A baseline different from the target prevents an idle model passing.
                await device_write(judge, dict(zip(INPUTS, [not case["inputs"][INPUTS[0]], 0, 1.0])))
                async with LiveMCP(condition, config, evidence, args.alias) as mcp:
                    await mcp.checked("configure_live_access", allow_live_connection=True, protocol="opc",
                                      ofs_alias=args.alias, opc_server_confirmed_running=True, allow_closed_loop=True)
                    result.update(startup_seconds=mcp.startup_seconds, discovery_seconds=mcp.discovery_seconds)
                    mcp.phase = "workflow"
                    start_tick = (await device_read(judge, ["OPCBench_Tick"]))["values"]["OPCBench_Tick"]
                    if factory:
                        async with factory() as provider:
                            await workflow(mcp, case["task"], config, provider, evidence, result, prompt=prompt(case))
                    else:
                        _, schemas = mcp.adapter(case["task"])
                        await mcp.dispatch("opc_connect", {}, schemas)
                        await mcp.dispatch("opc_write_tags", {"values": case["inputs"]}, schemas)
                        await asyncio.sleep(.1)
                        await mcp.dispatch("opc_read_tags", {"tags": TAGS}, schemas)
                        result["status"] = "completed"
                    observed = await device_read(judge, TAGS)
                    changed = observed["values"]["OPCBench_Tick"] != start_tick
                    validation = grade(case, mcp.model_calls, observed, changed, result["status"])
                    evidence.events.emit("independent_evaluation", observation_ref=evidence.blob(observed), validation=validation)
                    result.update(validation=validation, success=validation["success"])
            except Exception as exc:
                result.update(status="failed", failure_reason=type(exc).__name__)
                raise
            finally:
                result["durable_completed"] = True
                write_json(attempt / "summary.json", result)
        outcome["success"] = True
    finally:
        if originals is not None:
            try:
                await device_write(judge, originals)
                await asyncio.sleep(.1)
                restored = await device_read(judge, TAGS)
                outcome["restoration_verified"] = matches(restored["values"], expected(originals))
                if not outcome["restoration_verified"]:
                    outcome["success"] = False
            except Exception as exc:
                outcome.update(success=False, restore_error=type(exc).__name__)
        judge.disconnect()
        write_json(directory / "outcome.json", outcome)
    if not outcome["restoration_verified"]:
        raise RuntimeError("Original OPC benchmark inputs were not restored; inspect outcome.json")
    return directory


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "validate", "run"):
        sub = subs.add_parser(command)
        sub.add_argument("--config", required=True)
        if command != "prepare":
            sub.add_argument("--alias", default=ALIAS)
            sub.add_argument("--allow-live", action="store_true", required=True)
            sub.add_argument("--confirm-ofs-running", action="store_true", required=True)
            sub.add_argument("--allow-closed-loop", action="store_true", required=True)
            sub.add_argument("--repeats", type=int, default=1)
            sub.add_argument("--seed", type=int, default=1729)
            sub.add_argument("--case", choices=["all", "positive", "negative", "disabled"], default="all")
            if command == "run":
                sub.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if set(config["conditions"]) != {"OPC"}:
            raise ValueError("Live OPC configuration must contain exactly the OPC condition")
        if args.command == "prepare":
            print(prepare(config))
        elif args.command == "run" and args.dry_run:
            print(json.dumps({"paid_requests": 0, "live_connections": 0,
                              "alias": args.alias, "schedule": cases(args.repeats, args.seed, args.case)}, indent=2))
        else:
            with ce_lock(Path(config["workspace"])):
                print(asyncio.run(exercise(config, args)))
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        print("OPC benchmark failed: " + type(exc).__name__, file=sys.stderr)
        if isinstance(exc, (ValueError, FileNotFoundError)):
            print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
