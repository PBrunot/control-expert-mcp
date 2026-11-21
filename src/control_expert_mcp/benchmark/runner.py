"""Serial fixture lifecycle, resumable campaigns and independent evaluation."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
import json
from pathlib import Path
import random
import shutil
from time import perf_counter
import uuid

from .core import Events, ce_lock, digest, read_json, snapshot, write_json
from .provider import client_factory, workflow
from .tasks import (BROKEN_IDENTIFIER, PROMPTS, broken_source, declarations,
                    alarm_fixture, alarm_source, inspect_grade, normalize, source,
                    static_grade, threshold_source)
from .transport import Evidence, MCP
from .demo import DEMO_PROMPTS, weighing_grade, io_mapping_grade


def clean_build(build: dict) -> bool:
    return build.get("build_state") == "built_ok" and not build.get("error")


def require_build(build: dict):
    if not clean_build(build):
        raise RuntimeError("Control Expert did not report built_ok without error: " + str(build))


async def artifact(mcp, kind: str, **arguments) -> str:
    value = await mcp.checked("export_xml", kind=kind, **arguments)
    if "xml" not in value:
        raise RuntimeError("Expected inline fixture export; large external export is unsupported")
    return value["xml"]


async def verify_version(mcp, config):
    status = await mcp.checked("get_status")
    expected = config.get("ce_version", "16.4")
    if expected not in status.get("server_version", ""):
        raise RuntimeError(f"Expected CE {expected}; got {status.get('server_version')}")
    return status


async def prepare(config: dict, condition_name: str) -> Path:
    workspace = Path(config["workspace"])
    directory = workspace / ("prepare-" + uuid.uuid4().hex[:12])
    directory.mkdir(parents=True)
    evidence = Evidence(directory, Events(directory / "events.jsonl"))
    fixture_xml = Path(config["fixture"]).read_text(encoding="utf-8-sig")
    original = source(fixture_xml)
    broken = broken_source(original)
    with ce_lock(workspace):
        async with MCP(config["conditions"][condition_name], config, evidence) as mcp:
            await mcp.checked("new_project", cpu_part_number=config["cpu"]["part_number"],
                              cpu_version=config["cpu"]["version"])
            status = await verify_version(mcp, config)
            await mcp.checked("import_xml", kind="section", task="MAST", xml_content=fixture_xml)
            imported = source((await mcp.checked("read_section", task="MAST", section="Feeder"))["xml"])
            if normalize(imported) != normalize(original):
                raise RuntimeError("Imported executable fixture differs from source")
            baseline_build = await mcp.checked("build_project", rebuild_all=True)
            require_build(baseline_build)
            baseline = directory / "baseline.stu"
            await mcp.checked("save_project", path=str(baseline))
            await mcp.checked("close_project", save=False)
            await mcp.checked("open_project", path=str(baseline))
            require_build(await mcp.checked("build_project", rebuild_all=True))
            variables = await artifact(mcp, "variables")
            if len(declarations(variables)) != 15 or declarations(variables) != declarations(fixture_xml):
                raise RuntimeError("Imported declarations differ from fixture (including initial values)")
            await mcp.checked("write_st_logic", task="MAST", section="Feeder", st_source=broken)
            broken_build = await mcp.checked("build_project", rebuild_all=True)
            output = str(broken_build.get("diagnostics_output", ""))
            if clean_build(broken_build) or BROKEN_IDENTIFIER.lower() not in output.lower() or not broken_build.get("error"):
                raise RuntimeError("Injected compiler error not independently established: " + str(broken_build))
            broken_path = directory / "broken.stu"
            await mcp.checked("save_project", path=str(broken_path))
            await mcp.checked("close_project", save=False)
            await mcp.checked("open_project", path=str(broken_path))
            broken_persisted = source((await mcp.checked("read_section", task="MAST", section="Feeder"))["xml"])
            if normalize(broken_persisted) != normalize(broken):
                raise RuntimeError("Broken fixture did not persist")
            require_error = await mcp.checked("build_project", rebuild_all=True)
            if clean_build(require_error) or BROKEN_IDENTIFIER.lower() not in str(require_error).lower():
                raise RuntimeError("Reopened broken fixture did not reproduce compiler error")
            await mcp.checked("close_project", save=False)
            # Separate extension fixture: the original four tasks keep their exact
            # 15 declarations; only alarms receives the three predeclared EBOOLs.
            extended_xml = alarm_fixture(fixture_xml)
            await mcp.checked("new_project", cpu_part_number=config["cpu"]["part_number"],
                              cpu_version=config["cpu"]["version"])
            await mcp.checked("import_xml", kind="section", task="MAST", xml_content=extended_xml)
            require_build(await mcp.checked("build_project", rebuild_all=True))
            alarm_baseline = directory / "alarms-baseline.stu"
            await mcp.checked("save_project", path=str(alarm_baseline))
            await mcp.checked("close_project", save=False)
            await mcp.checked("open_project", path=str(alarm_baseline))
            require_build(await mcp.checked("build_project", rebuild_all=True))
            alarm_variables = await artifact(mcp, "variables")
            alarm_imported = source((await mcp.checked("read_section", task="MAST", section="Feeder"))["xml"])
            if declarations(alarm_variables) != declarations(extended_xml) or normalize(alarm_imported) != normalize(original):
                raise RuntimeError("Alarm baseline source/declarations differ from extension fixture")
            await mcp.checked("close_project", save=False)
    manifest = {"fixture_sha256": digest(Path(config["fixture"]).read_bytes()), "cpu": config["cpu"],
        "baseline": str(baseline), "baseline_sha256": digest(baseline.read_bytes()),
        "broken": str(broken_path), "broken_sha256": digest(broken_path.read_bytes()),
        "alarms_baseline": str(alarm_baseline), "alarms_baseline_sha256": digest(alarm_baseline.read_bytes()),
        "alarms_variables": alarm_variables,
        "source": original, "variables": variables, "status": status,
        "baseline_build": baseline_build, "broken_build": broken_build,
        "created_at": datetime.now(timezone.utc).isoformat()}
    write_json(directory / "manifest.json", manifest)
    write_json(workspace / "prepared.json", {"manifest": str(directory / "manifest.json")})
    return directory


def prepared(config: dict) -> dict:
    manifest = read_json(Path(read_json(Path(config["workspace"]) / "prepared.json")["manifest"]))
    if manifest["fixture_sha256"] != digest(Path(config["fixture"]).read_bytes()) or manifest["cpu"] != config["cpu"]:
        raise ValueError("Fixture/CPU changed; prepare a new baseline")
    for key in ("baseline", "broken", "alarms_baseline"):
        if key not in manifest:
            raise ValueError("Prepared fixtures predate alarm task; run prepare again")
        if digest(Path(manifest[key]).read_bytes()) != manifest[key + "_sha256"]:
            raise ValueError("Prepared project changed; prepare again")
    if config.get("demo_project"):
        manifest["demo_project"] = config["demo_project"]
        manifest["io_mapping_reference"] = Path(config["io_mapping_reference"]).read_text(encoding="utf-8-sig")
    return manifest


def task_fixture(manifest: dict, task: str) -> tuple[str, dict]:
    """Choose isolated input and expected declarations for one task."""
    if task in DEMO_PROMPTS:
        return manifest["demo_project"], manifest
    if task == "alarms":
        return manifest["alarms_baseline"], {**manifest, "variables": manifest["alarms_variables"]}
    return manifest["broken" if task == "repair" else "baseline"], manifest


async def validate_fixtures(config: dict, condition_name: str) -> Path:
    """Validate canonical training changes with CE, without an API/model request."""
    manifest = prepared(config)
    directory = Path(config["workspace"]) / ("validate-" + uuid.uuid4().hex[:12])
    evidence = Evidence(directory, Events(directory / "events.jsonl"))
    checks = {}
    with ce_lock(Path(config["workspace"])):
        async with MCP(config["conditions"][condition_name], config, evidence) as mcp:
            for task in ("threshold", "temperature", "repair", "alarms"):
                output = directory / (task + ".stu")
                input_path, expected_manifest = task_fixture(manifest, task)
                shutil.copyfile(input_path, output)
                await mcp.checked("open_project", path=str(output))
                await verify_version(mcp, config)
                original = manifest["source"]
                candidate = threshold_source(original) if task == "threshold" else original
                if task == "alarms":
                    candidate = alarm_source(original)
                if task == "temperature":
                    import re
                    candidate, count = re.subn(r"(?i)cmeasured_temp\s*=\s*setpoint_temp",
                        "ABS(cmeasured_temp-setpoint_temp)<=2.0", original)
                    if count != 1:
                        raise ValueError("Expected one temperature predicate")
                await mcp.checked("write_st_logic", task="MAST", section="Feeder", st_source=candidate)
                before = await mcp.checked("build_project", rebuild_all=True)
                require_build(before)
                await mcp.checked("save_project")
                await mcp.checked("close_project", save=False)
                await mcp.checked("open_project", path=str(output))
                section = await mcp.checked("read_section", task="MAST", section="Feeder")
                variables = await artifact(mcp, "variables")
                after = await mcp.checked("build_project", rebuild_all=True)
                require_build(after)
                grade = static_grade(task, original, source(section["xml"]))
                grade.update(before_save_build=before, reopened_build=after,
                             declarations_pass=declarations(variables) == declarations(expected_manifest["variables"]))
                if grade["static_behavior"] != "pass" or not grade["declarations_pass"]:
                    raise RuntimeError("Canonical training change not independently verified")
                (directory / (task + ".xml")).write_text(section["xml"], encoding="utf-8")
                checks[task] = grade
                write_json(directory / "validation.json", checks)
                await mcp.checked("close_project", save=False)
            if config.get("demo_project"):
                output = directory / "demo.stu"
                shutil.copyfile(config["demo_project"], output)
                await mcp.checked("open_project", path=str(output))
                status = await verify_version(mcp, config)
                for section_name in ("Weighing_Material_A", "Weighing_Material_B", "Mixer"):
                    value = await mcp.checked("read_section", task="MAST", section=section_name)
                    if not value.get("xml"):
                        raise RuntimeError("Demo source is unavailable")
                for kind in ("variables", "configuration"):
                    await artifact(mcp, kind)
                grade = io_mapping_grade(manifest["io_mapping_reference"], manifest["io_mapping_reference"])
                if not grade["answer_pass"]:
                    raise ValueError("Approved mapping reference fails its own rubric")
                await mcp.checked("close_project", save=False)
                if digest(output.read_bytes()) != digest(Path(config["demo_project"]).read_bytes()):
                    raise RuntimeError("Read-only demo validation changed its project file")
                checks["demo"] = {"status": status, "reference_self_check": grade, "read_only": True}
                write_json(directory / "validation.json", checks)
    return directory


def make_schedule(conditions: list[str], repeats: int, seed: int, tasks=None) -> list[dict]:
    if repeats < 1:
        raise ValueError("Positive repeats required")
    rng = random.Random(seed)
    schedule = []
    # Pair conditions within each task/repetition, randomizing both block and arm order.
    blocks = [(task, repeat) for repeat in range(repeats) for task in (PROMPTS if tasks is None else tasks)]
    rng.shuffle(blocks)
    for task, repeat in blocks:
        arms = conditions.copy()
        rng.shuffle(arms)
        for condition in arms:
            schedule.append({"task": task, "repeat": repeat, "condition": condition,
                             "case_id": f"{task}-{repeat:03d}-{condition}"})
    return schedule


async def evaluate(mcp, task: str, manifest: dict, output: Path, answer: str, model_events: list) -> dict:
    started = perf_counter()
    mcp.phase = "evaluation"
    if task in DEMO_PROMPTS:
        # Model has no mutation tools. Check the actual read-only project file.
        calls = [event for event in model_events if event["kind"] == "mcp_call"
                 and event.get("phase") == "workflow" and not event.get("is_error")]
        read = any(event["tool"] in {"read_section", "export_xml"} for event in calls)
        report = (weighing_grade(answer) if task == "weighing" else
                  io_mapping_grade(answer, manifest["io_mapping_reference"]))
        unchanged = digest(output.read_bytes()) == digest(Path(manifest["demo_project"]).read_bytes())
        report.update(scope="pass" if unchanged else "fail", compile_pass=None,
                      runtime_behavior="unverified", static_behavior=None,
                      obtained_source_through_mcp=read,
                      evaluator_seconds=perf_counter() - started,
                      success=report["answer_pass"] and unchanged and read)
        await mcp.checked("close_project", save=False)
        return report
    # Discard unsaved edits, independently reopen the model's saved file.
    await mcp.checked("close_project", save=False)
    await mcp.checked("open_project", path=str(output))
    section = await mcp.checked("read_section", task="MAST", section="Feeder")
    variables = await artifact(mcp, "variables")
    (output.parent / "saved-section.xml").write_text(section["xml"], encoding="utf-8")
    (output.parent / "saved-variables.xml").write_text(variables, encoding="utf-8")
    actual = source(section["xml"])
    declared = declarations(variables) == declarations(manifest["variables"])
    calls = [event for event in model_events if event["kind"] == "mcp_call" and event.get("phase") == "workflow"]
    read = any(event["tool"] == "read_section" and not event["is_error"] for event in calls)
    if task == "inspect":
        report = inspect_grade(answer)
        report.update(scope="pass" if normalize(actual) == normalize(manifest["source"]) and declared else "fail",
                      compile_pass=None, runtime_behavior="unverified", static_behavior=None)
        report["success"] = report["answer_pass"] and report["scope"] == "pass" and read
    else:
        report = static_grade(task, manifest["source"], actual)
        build = await mcp.checked("build_project", rebuild_all=True)
        report.update(build=build, compile_pass=clean_build(build), declarations_pass=declared)
        writes = [index for index, event in enumerate(calls) if event["tool"] == "write_st_logic" and not event["is_error"]]
        last_write = max(writes, default=-1)
        builds = [index for index, event in enumerate(calls) if event["tool"] == "build_project" and event.get("build_ok") and index > last_write]
        built = bool(builds)
        saved = built and any(event["tool"] == "save_project" and not event["is_error"] and index > max(builds)
                              for index, event in enumerate(calls))
        report.update(model_built=built, model_saved=saved)
        report["success"] = all((declared, read, built, saved, clean_build(build),
                                 report["scope"] == "pass", report["static_behavior"] == "pass"))
    report.update(obtained_source_through_mcp=read, evaluator_seconds=perf_counter() - started,
                  limitation="Static recognized-subset checks; PLC runtime behavior unverified")
    await mcp.checked("close_project", save=False)
    return report


async def run_case(config, case, manifest, directory, fingerprint, provider_factory, expected_context):
    directory.mkdir(parents=True, exist_ok=False)
    events = Events(directory / "events.jsonl")
    evidence = Evidence(directory, events)
    result = {**case, "fingerprint": fingerprint, "status": "startup_failure", "failure_reason": None,
              "cold_start": True, "requested_model": config["model"]["id"],
              "provider": config.get("provider", {}).get("name", "openai"),
              "model_identity": config["model"].get("identity", "pinned"), "validation": {"success": False}}
    started = perf_counter()
    output = directory / "project.stu"
    input_path, manifest = task_fixture(manifest, case["task"])
    shutil.copyfile(input_path, output)
    try:
        async with MCP(config["conditions"][case["condition"]], config, evidence) as mcp:
            result.update(startup_seconds=mcp.startup_seconds, discovery_seconds=mcp.discovery_seconds)
            reset_started = perf_counter()
            instructions, schemas = mcp.adapter(case["task"])
            if digest([instructions, schemas, mcp.initialization]) != expected_context:
                raise ValueError("Server instructions/schema/initialization changed since campaign preflight")
            await mcp.checked("open_project", path=str(output))
            result["ce_status"] = await verify_version(mcp, config)
            result["setup_seconds"] = perf_counter() - started
            result["reset_seconds"] = perf_counter() - reset_started
            result["status"] = "workflow_failure"
            mcp.phase = "workflow"
            try:
                async with provider_factory() as provider:
                    await workflow(mcp, case["task"], config, provider, evidence, result)
            except Exception as exc:
                result.update(status="timeout" if isinstance(exc, TimeoutError) else "workflow_failure",
                              failure_reason=type(exc).__name__, provider_failure_code=getattr(exc, "status_code", None))
            if not mcp.tainted:
                result["validation"] = await evaluate(mcp, case["task"], manifest, output,
                    result.get("final_response", ""), [json.loads(line) for line in events.path.read_text(encoding="utf-8").splitlines()])
    except Exception as exc:
        result["failure_reason"] = type(exc).__name__
        if result["status"] == "completed":
            result["status"] = "evaluation_timeout" if isinstance(exc, TimeoutError) else "evaluation_failure"
        events.emit("case_exception", error=type(exc).__name__, status=result["status"])
    result["total_seconds"] = perf_counter() - started
    result["success"] = result["status"] == "completed" and result["validation"].get("success", False)
    result["durable_completed"] = True
    (directory / "final-response.txt").write_text(result.get("final_response", ""), encoding="utf-8")
    write_json(directory / "validation.json", result["validation"])
    write_json(directory / "summary.json", result)
    return result


async def contexts(config, directory) -> dict:
    result = {}
    for name, condition in config["conditions"].items():
        evidence = Evidence(directory / name, Events(directory / name / "events.jsonl"))
        async with MCP(condition, config, evidence) as mcp:
            if condition["documentation"]:
                status = await mcp.checked("get_documentation_status")
                if not status.get("ready") or status.get("freshness") != "current":
                    raise ValueError("Condition requires a prepared, current documentation index")
            result[name] = {task: digest([*mcp.adapter(task), mcp.initialization]) for task in {**PROMPTS, **(DEMO_PROMPTS if config.get("demo_project") else {})}}
    return result


async def campaign(config: dict, conditions: list[str], repeats: int, seed: int,
                   run_id: str | None = None, provider_factory=None) -> Path:
    if provider_factory is None:
        provider_factory = client_factory(config)
    manifest = prepared(config)
    current = snapshot(config)
    current["prepared"] = {k: manifest[k] for k in ("baseline_sha256", "broken_sha256", "alarms_baseline_sha256", "status")}
    fingerprint = digest(current)
    root = Path(config["results"])
    if run_id is None:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
        directory = root / run_id
        directory.mkdir(parents=True, exist_ok=False)
        plan = {"run_id": run_id, "base_fingerprint": fingerprint, "fingerprint": fingerprint, "snapshot": current,
                "seed": seed, "schedule": make_schedule(conditions, repeats, seed, current["prompts"])}
        write_json(directory / "plan.json", plan)
    else:
        if Path(run_id).name != run_id or run_id in {".", ".."}:
            raise ValueError("Invalid run ID")
        directory = root / run_id
        plan = read_json(directory / "plan.json")
        if fingerprint != plan["base_fingerprint"]:
            raise ValueError("Immutable fingerprints changed; start a new campaign")
    with ce_lock(Path(config["workspace"])):
        actual_contexts = await contexts(config, directory / ("preflight-" + uuid.uuid4().hex[:8]))
        if "contexts" in plan and actual_contexts != plan["contexts"]:
            raise ValueError("Server context changed; start a new campaign")
        plan["contexts"] = actual_contexts
        fingerprint = digest([plan["base_fingerprint"], actual_contexts])
        plan["fingerprint"] = fingerprint
        write_json(directory / "plan.json", plan)
        for case in plan["schedule"]:
            parent = directory / case["case_id"]
            previous = sorted(parent.glob("attempt-*/summary.json"))
            if any(read_json(p).get("durable_completed") and read_json(p).get("fingerprint") == fingerprint for p in previous):
                continue
            # Never overwrite an interrupted attempt. Every retry starts from baseline.
            attempt = parent / ("attempt-" + uuid.uuid4().hex)
            print(f"{run_id}: {case['case_id']}", flush=True)
            if digest(snapshot(config)) != digest({k: v for k, v in current.items() if k != "prepared"}):
                raise ValueError("Configuration/source/corpus/environment changed during campaign")
            prepared(config)
            result = await run_case(config, case, manifest, attempt, fingerprint, provider_factory,
                                    plan["contexts"][case["condition"]][case["task"]])
            print(f"  {result['status']}; independently accepted={result['success']}", flush=True)
            if result.get("provider_failure_code") in {401, 403, 404, 429}:
                raise RuntimeError(f"Provider rejected request ({result['provider_failure_code']}); campaign stopped")
            if (Path(config["workspace"]) / "TAINTED.json").exists():
                raise RuntimeError("CE session tainted; campaign stopped before further operations")
    return directory
