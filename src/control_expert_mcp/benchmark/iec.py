"""Dedicated native IEC benchmark: demo-based authoring, in-MAST capture and grading."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from importlib.util import find_spec
import json
from pathlib import Path
import random
import shutil
import sys
from time import monotonic
import uuid

from ..opc import OpcClient
from .core import (Events, ce_lock, digest, load_config, read_json, snapshot,
                   tree_fingerprint_python, write_json)
from .iec_artifact import validate_submission
from .iec_capture import RecordingClient, acquire, instrument
from .iec_cases import CASES, ORIENTATION, map_submission, physical_name, select, task_prompt
from .iec_fixtures import private_contract
from .iec_grade import RUBRIC, grade, result
from .iec_reference import MUTANT_VECTOR, reference
from .iec_report import overview, write_report
from .iec_runtime import (EvaluationMCP, IECMCP, create_public, extract, idle, inspect,
                          install, inventory, order)
from .provider import client_factory, workflow
from .runner import clean_build, verify_version
from .transport import Evidence, MCP

SETTINGS = {"unity.dataDictionary": "1", "unity.dataDictionaryOnlyHMIvariables": "0"}


def configuration(path: str) -> dict:
    config = load_config(path)
    if Path(config["fixture"]).suffix.lower() != ".stu":
        raise ValueError("IEC fixture must be the native M580 demo STU; no hardware creation is performed")
    if not config["cpu"].get("part_number", "").startswith("BME P58") or config["ce_version"] != "16.4":
        raise ValueError("IEC suite requires CE 16.4 and M580 CPU configuration")
    return config


def identifier() -> int:
    return uuid.uuid4().int % (2**31 - 1) + 1


def code_hash() -> str:
    return tree_fingerprint_python(Path(__file__).parents[1])


async def cleanup(mcp, *, connected=False, owned=True) -> dict:
    if mcp.tainted:
        return {"verified": False, "reason": "CE tainted; verify idle/recovery before further operations"}
    try:
        if connected:
            state = await mcp.checked("plc_state")
            if state.get("plc_state") == "run":
                await mcp.checked("plc_command", command="stop")
            state = await mcp.checked("plc_state")
            if state.get("plc_state") not in {"stop", "no_conf"}:
                raise RuntimeError("Simulator stop unverified")
            await mcp.checked("plc_disconnect")
        if owned:
            await mcp.checked("close_project", save=False)
        return {"verified": True}
    except Exception as exc:
        return {"verified": False, "reason": type(exc).__name__}


async def prepare(config: dict, selected: str, condition_name: str) -> Path:
    """Copy the demo; verify native imports/builds without any live connection."""
    directory = Path(config["workspace"]) / ("iec-prepare-" + uuid.uuid4().hex[:12])
    directory.mkdir(parents=True)
    source = Path(config["fixture"])
    source_hash = digest(source.read_bytes())
    entries = {}
    for case in select(selected):
        target = directory / case.id
        target.mkdir()
        path = target / "public.stu"
        shutil.copyfile(source, path)
        evidence = Evidence(target, Events(target / "events.jsonl"))
        entry = {"language": case.language, "authoring": "unknown", "status": "infrastructure_error"}
        async with MCP(config["conditions"][condition_name], config, evidence) as mcp:
            owned = False
            native_phase = False
            try:
                await idle(mcp)
                owned = True
                baseline = await create_public(mcp, case, config, path)
                entry.update(baseline=baseline, public=str(path), public_sha256=digest(path.read_bytes()))
                native_phase = True
                await install(mcp, case, reference(case))
                exported = await inspect(mcp, case, reference(case).get("helpers", {}), baseline)
                write_json(target / "reference-export.json", exported)
                build = await mcp.checked("build_project", rebuild_all=True)
                write_json(target / "reference-build.json", build)
                if not clean_build(build):
                    entry.update(authoring="unsupported", status="unsupported_authoring", reason="Native reference failed build; inspect reference-build.json")
                else:
                    roundtrip = target / "reference.stu"
                    await mcp.checked("save_project", path=str(roundtrip))
                    await mcp.checked("close_project", save=False)
                    await mcp.checked("open_project", path=str(roundtrip))
                    await inspect(mcp, case, reference(case).get("helpers", {}), baseline)
                    rebuilt = await mcp.checked("build_project", rebuild_all=True)
                    write_json(target / "roundtrip-build.json", rebuilt)
                    if clean_build(rebuilt):
                        entry.update(authoring="supported", status="prepared", native_import_verified=True,
                                     llm_authoring_verified=False, simulator_verified=False)
                    else:
                        entry.update(authoring="unsupported", status="unsupported_authoring", reason="Native round trip did not build")
            except Exception as exc:
                if native_phase and not mcp.tainted:
                    entry.update(authoring="unsupported", status="unsupported_authoring",
                                 reason="Native reference import/export/build path failed: " + type(exc).__name__ + "; inspect events.jsonl")
                else:
                    entry["reason"] = type(exc).__name__
                evidence.events.emit("prepare_exception", error=type(exc).__name__, detail=str(exc))
            finally:
                entry["cleanup"] = await cleanup(mcp, owned=owned)
        entries[case.id] = entry
        write_json(target / "capability.json", entry)
        if not entry["cleanup"]["verified"]:
            break
    if digest(source.read_bytes()) != source_hash:
        raise RuntimeError("Source demo changed during preparation")
    manifest = {"suite": "iec", "rubric": RUBRIC, "source_sha256": source_hash,
                "source": str(source), "code_sha256": code_hash(), "fixtures_sha256": digest(private_contract()),
                "cpu": config["cpu"], "ce_version": config["ce_version"], "cases": entries}
    output = directory / "manifest.json"
    write_json(output, manifest)
    # A selected-case prepare does not silently merge stale preparations.
    write_json(Path(config["workspace"]) / "iec-manifest.json", manifest)
    return output


async def evaluate(config, condition_name, case, submission, baseline, directory, alias) -> tuple[dict, dict]:
    """Only trusted infrastructure sees private vectors or controls the simulator."""
    path = directory / "instrumented.stu"
    shutil.copyfile(config["fixture"], path)
    evidence = Evidence(directory / "evaluation", Events(directory / "evaluation" / "events.jsonl"))
    run_id, artifact_id = identifier(), int(digest(submission)[:7], 16) + 1
    program = instrument(case, run_id, artifact_id)
    write_json(directory / "instrumentation.json", program)
    validation = result("infrastructure_error", "Evaluation did not finish", compile_pass=True)
    status = {"verified": False}
    condition = config["conditions"][condition_name]
    judge = OpcClient(python=condition.get("env", {}).get("CE_MCP_OPC_PYTHON"))
    async with EvaluationMCP(condition, config, evidence) as mcp:
        owned = connected = False
        try:
            await idle(mcp)
            owned = True
            await mcp.checked("open_project", path=str(path))
            await verify_version(mcp, config)
            if await inventory(mcp) != baseline["variables"] or await mcp.checked("get_project_structure") != baseline["structure"]:
                raise ValueError("Demo differs from prepared baseline")
            await mcp.checked("configure_live_access", allow_live_connection=True, protocol="opc", ofs_alias=alias,
                              opc_server_confirmed_running=True, allow_closed_loop=True)
            await mcp.checked("set_project_settings", settings=SETTINGS)
            for key, value in SETTINGS.items():
                if int((await mcp.checked("get_project_setting", ident=key))["value"]) != int(value):
                    raise RuntimeError("OFS dictionary setting did not persist")
            for name, kind in case.inputs + case.outputs:
                await mcp.checked("create_variable", name=physical_name(case, name), type_name=kind,
                                  initial_value="FALSE" if kind == "BOOL" else "0")
            for name, kind in program["declarations"].items():
                await mcp.checked("create_variable", name=name, type_name=kind,
                                  initial_value="FALSE" if kind == "BOOL" else "0")
            before, after = physical_name(case, "Before"), physical_name(case, "After")
            await mcp.checked("write_st_logic", task="MAST", section=before, st_source=program["before"])
            if case.language == "SFC":
                await mcp.checked("write_st_logic", task="MAST", section=physical_name(case, "LLM_Pre"), st_source="(* empty *)")
            await mcp.checked("create_section", task="MAST", name=physical_name(case, "Candidate"), language=case.language)
            if case.language == "SFC":
                await mcp.checked("write_st_logic", task="MAST", section=physical_name(case, "LLM_Post"), st_source="(* empty *)")
            await install(mcp, case, submission)
            # Reinspect the real native body after import, not the model manifest.
            imported = await extract(mcp, case, submission["helpers"])
            write_json(directory / "instrumented-candidate.json", imported)
            if imported != submission:
                # Vendor export formatting may differ, so compare normalized
                # executable XML/text rather than silently accepting a change.
                from .iec_artifact import executable_identity
                if executable_identity(imported) != executable_identity(submission):
                    raise ValueError("Candidate changed in instrumented project")
            await mcp.checked("write_st_logic", task="MAST", section=after, st_source=program["after"])
            names = [before] + ([physical_name(case, "LLM_Pre")] if case.language == "SFC" else [])
            names += [physical_name(case, "Candidate")]
            names += ([physical_name(case, "LLM_Post")] if case.language == "SFC" else []) + [after]
            await order(mcp, names, baseline["structure"])
            build = await mcp.checked("build_project", rebuild_all=True)
            write_json(directory / "instrumented-build.json", build)
            if not clean_build(build):
                raise RuntimeError("Instrumentation build failed; candidate already built independently")
            await mcp.checked("save_project")
            write_json(directory / "capture-identity.json", {"run_id": run_id, "artifact_id": artifact_id,
                       "candidate_sha256": digest(submission), "instrumented_sha256": digest(path.read_bytes())})
            await mcp.checked("start_simulator")
            await mcp.checked("plc_setup_connection", target="simulator", address="127.0.0.1", driver="TCPIP")
            connection = await mcp.checked("plc_connect", target="simulator")
            connected = connection.get("connected") is True
            if not connected:
                raise RuntimeError("Simulator not connected")
            await mcp.checked("plc_command", command="stop")
            transfer = await mcp.checked("plc_transfer", direction="pc_to_plc")
            if transfer.get("transferred") != "pc_to_plc":
                raise RuntimeError("This run was not downloaded")
            await mcp.checked("plc_command", command="init")
            await mcp.checked("plc_command", command="run")
            state = await mcp.checked("plc_state")
            write_json(directory / "deployment-state.json", state)
            if not state.get("connected") or not state.get("pc_equals_plc") or state.get("plc_state") != "run":
                raise RuntimeError("Simulator application attribution failed")
            ofs = await asyncio.to_thread(judge.connect, "Schneider-Aut.OFS.2", alias)
            write_json(directory / "ofs-connect.json", ofs)
            capture = await acquire(RecordingClient(judge, evidence), case, run_id, artifact_id,
                                    timeout=min(config["workflow_timeout"], 60))
            write_json(directory / "capture.json", capture)
            validation = grade(case, {"artifact_valid": True, "build_ok": True}, capture, run_id=run_id, artifact_id=artifact_id)
        except Exception as exc:
            validation = result("infrastructure_error", type(exc).__name__ + ": " + str(exc)[:1000], compile_pass=True)
            evidence.events.emit("evaluation_exception", error=type(exc).__name__, detail=str(exc))
        finally:
            try:
                await asyncio.to_thread(judge.disconnect)
            finally:
                status = await cleanup(mcp, connected=connected, owned=owned)
    return validation, status


async def _attempt(config, item, manifest, directory, fingerprint, alias, factory=None) -> dict:
    case = CASES[item["task"]]
    directory.mkdir(parents=True)
    started = monotonic()
    row = {**item, "fingerprint": fingerprint, "status": "startup_failure", "success": False,
           "requested_model": config["model"]["id"], "provider": config["provider"]["name"],
           "model_identity": config["model"].get("identity", "pinned"), "language": case.language,
           "cleanup": {"verified": True}, "validation": result("infrastructure_error", "No completed attempt")}
    entry = manifest["cases"].get(case.id, {})
    if entry.get("authoring") != "supported":
        row.update(status="blocked", validation=result("unsupported_authoring" if entry.get("authoring") == "unsupported"
                   else "infrastructure_error", entry.get("reason", "Case not prepared")))
    else:
        path = directory / "candidate.stu"
        shutil.copyfile(entry["public"], path)
        evidence = Evidence(directory, Events(directory / "events.jsonl"))
        submission = None
        async with IECMCP(config["conditions"][item["condition"]], config, evidence, case) as mcp:
            owned = False
            try:
                row.update(startup_seconds=mcp.startup_seconds, discovery_seconds=mcp.discovery_seconds, cold_start=True)
                await idle(mcp)
                owned = True
                await mcp.checked("open_project", path=str(path))
                await verify_version(mcp, config)
                row["effective_context_sha256"] = digest([*mcp.adapter(case.id), mcp.initialization])
                mcp.phase = "workflow"
                if item["variant"] == "model":
                    async with factory() as provider:
                        await workflow(mcp, case.id, config, provider, evidence, row, prompt=task_prompt(case))
                else:
                    source = reference(case, mutant=item["variant"] == "mutant")
                    payload = await mcp.dispatch("submit_candidate", map_submission(case, source), mcp.adapter(case.id)[1])
                    if payload.get("is_error"):
                        raise ValueError("Scripted native submission failed")
                    row["status"] = "completed"
                mcp.frozen = True
                mcp.phase = "artifact"
                if row.get("status") != "completed":
                    row["validation"] = result("infrastructure_error", "Generation incomplete: " + row["status"])
                elif not mcp.submitted:
                    row["validation"] = result("artifact_invalid", "No candidate submitted")
                else:
                    try:
                        submission = await inspect(mcp, case, mcp.helpers, entry["baseline"])
                    except ValueError as exc:
                        row["validation"] = result("artifact_invalid", str(exc))
                    else:
                        build = await mcp.checked("build_project", rebuild_all=True)
                        write_json(directory / "candidate-build.json", build)
                        if clean_build(build):
                            await mcp.checked("save_project")
                            write_json(directory / "artifact.json", {"submission": submission, "sha256": digest(submission),
                                       "project_sha256": digest(path.read_bytes()), "language": case.language})
                        else:
                            row["validation"] = result("build_failed", "Candidate build failed", compile_pass=False)
                            submission = None
            except Exception as exc:
                row.update(status="workflow_failure", validation=result("infrastructure_error", type(exc).__name__))
            finally:
                row["cleanup"] = await cleanup(mcp, owned=owned)
        if submission is not None and row["cleanup"]["verified"]:
            row["validation"], row["cleanup"] = await evaluate(config, item["condition"], case, submission,
                                                               entry["baseline"], directory, alias)
        row["success"] = row["validation"]["success"]
    row.update(total_seconds=monotonic() - started, durable_completed=True)
    if item["variant"] != "model":
        expected = "output_mismatch" if item["variant"] == "mutant" else "pass"
        row["acceptance_pass"] = row["validation"]["verdict"] == expected
        if item["variant"] == "mutant":
            mismatch = row["validation"].get("first_mismatch") or {}
            row["acceptance_pass"] &= (mismatch.get("vector"), mismatch.get("cycle")) == (MUTANT_VECTOR[case.id], case.cycles)
    write_json(directory / "summary.json", row)
    return row


async def attempt(config, item, manifest, directory, fingerprint, alias, factory=None) -> dict:
    """Retain a terminal infrastructure result even when transport startup fails."""
    try:
        return await _attempt(config, item, manifest, directory, fingerprint, alias, factory)
    except Exception as exc:
        row = {**item, "fingerprint": fingerprint, "status": "infrastructure_failure", "success": False,
               "language": CASES[item["task"]].language, "requested_model": config["model"]["id"],
               "provider": config["provider"]["name"], "durable_completed": True,
               "validation": result("infrastructure_error", type(exc).__name__),
               "cleanup": {"verified": False, "reason": "Lifecycle interrupted; inspect session before continuing"}}
        write_json(directory / "summary.json", row)
        return row


def schedule(selected: str, conditions: list[str], repeats: int, mode: str, seed: int) -> list[dict]:
    rows = []
    for condition in conditions:
        for case in select(selected):
            variants = ([('reference', i) for i in range(max(2, repeats))] + [('mutant', 0)]
                        if mode == "validate" else [('model', i) for i in range(repeats)])
            for variant, repeat in variants:
                rows.append({"case_id": f"{case.id}-{condition}-{variant}-{repeat:03d}", "task": case.id,
                             "condition": condition, "variant": variant, "repeat": repeat})
    random.Random(seed).shuffle(rows)
    return rows


async def campaign(config, args) -> Path:
    manifest = read_json(Path(config["workspace"]) / "iec-manifest.json")
    source_hash = digest(Path(config["fixture"]).read_bytes())
    initial_hash = code_hash()
    # Preparation is a hashed project template, not a frozen copy of the whole
    # harness. Record its original code provenance, then independently inspect
    # and build every current candidate. Campaign source stays immutable below.
    if (manifest.get("source_sha256") != source_hash
            or manifest.get("fixtures_sha256") != digest(private_contract()) or manifest.get("cpu") != config["cpu"]
            or manifest.get("ce_version") != config["ce_version"]):
        raise ValueError("IEC source/configuration changed; prepare again")
    conditions = args.condition or list(config["conditions"])
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-iec-" + uuid.uuid4().hex[:8]
    directory = Path(config["results"]) / run_id
    plan = schedule(args.case, conditions, args.repeats, args.command, args.seed)
    snap = snapshot(config)
    snap.update(suite="iec", rubric_version=RUBRIC, fixtures_sha256=digest(private_contract()),
                prompts={c.id: task_prompt(c) for c in select(args.case)}, orientation=ORIENTATION,
                preparation_sha256=digest(manifest), mode=args.command)
    fingerprint = digest([snap, plan, args.alias])
    write_json(directory / "plan.json", {"run_id": run_id, "snapshot": snap, "schedule": plan,
               "fingerprint": fingerprint, "seed": args.seed, "alias": args.alias, "mode": args.command})
    factory = client_factory(config) if args.command == "run" else None
    rows = []
    stop_reason = None
    try:
        for item in plan:
            if code_hash() != initial_hash or digest(Path(config["fixture"]).read_bytes()) != source_hash:
                raise ValueError("Source changed during IEC campaign")
            entry = manifest["cases"].get(item["task"], {})
            if entry.get("public") and digest(Path(entry["public"]).read_bytes()) != entry.get("public_sha256"):
                raise ValueError("Prepared public project changed")
            row = await attempt(config, item, manifest, directory / item["case_id"] / "attempt-001", fingerprint, args.alias, factory)
            rows.append(row)
            if not row["cleanup"]["verified"]:
                stop_reason = "cleanup_unverified"
                break
            if getattr(args, "stop_on_infrastructure_error", False) and row["validation"]["verdict"] == "infrastructure_error":
                stop_reason = "infrastructure_error"
                break
    finally:
        write_report(directory, rows)
        success = len(rows) == len(plan) and all(r.get("acceptance_pass", r["success"]) for r in rows)
        write_json(directory / "outcome.json", {"success": success, "cases": len(rows), "scheduled": len(plan),
                   "mode": args.command, "cleanup_verified": all(r["cleanup"]["verified"] for r in rows)})
        if stop_reason:
            write_json(directory / "stop.json", {"reason": stop_reason, "completed": len(rows), "scheduled": len(plan)})
        if rows and find_spec("matplotlib"):
            overview(directory, directory / "overview.png")
    return directory


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "validate", "run"):
        sub = subs.add_parser(command)
        sub.add_argument("--config", required=True)
        sub.add_argument("--case", choices=["all", *CASES], default="all")
        sub.add_argument("--condition", nargs="+" if command != "prepare" else None)
        sub.add_argument("--dry-run", action="store_true")
        if command != "prepare":
            sub.add_argument("--stop-on-infrastructure-error", action="store_true", help="Stop after a completed case with infrastructure failure; retain pending schedule")
            sub.add_argument("--repeats", type=int, default=1)
            sub.add_argument("--seed", type=int, default=1729)
            sub.add_argument("--alias", help="OFS alias confirmed to resolve to MBT:127.0.0.1/U")
            for flag in ("allow-live", "confirm-ofs-running", "allow-closed-loop", "allow-simulator-replacement", "confirm-simulator-alias"):
                sub.add_argument("--" + flag, action="store_true")
    sub = subs.add_parser("grade", help="Offline replay of saved independent evidence")
    sub.add_argument("--case", choices=list(CASES), required=True)
    for flag in ("evidence", "capture", "output"):
        sub.add_argument("--" + flag, type=Path, required=True)
    sub.add_argument("--run-id", type=int, required=True)
    sub.add_argument("--artifact-id", type=int, required=True)
    sub = subs.add_parser("overview", help="PNG/SVG correctness and verdict overview; no CE/provider calls")
    sub.add_argument("--results", type=Path, required=True)
    sub.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "overview":
            overview(args.results, args.output)
            print(args.output.with_suffix(".png"))
            return 0
        if args.command == "grade":
            value = grade(CASES[args.case], read_json(args.evidence), read_json(args.capture),
                          run_id=args.run_id, artifact_id=args.artifact_id)
            write_json(args.output, value)
            print(json.dumps(value, indent=2))
            return 0 if value["success"] else 1
        config = configuration(args.config)
        conditions = ([args.condition] if args.condition else [next(iter(config["conditions"]))]) if args.command == "prepare" else (args.condition or list(config["conditions"]))
        if not conditions or len(set(conditions)) != len(conditions) or any(c not in config["conditions"] for c in conditions):
            raise ValueError("Select distinct configured conditions")
        if args.command != "prepare" and args.repeats < 1:
            raise ValueError("Positive repeats required")
        if args.dry_run:
            print(json.dumps({"suite": "iec", "paid_requests": 0, "live_connections": 0, "com_connections": 0,
                              "source_demo": config["fixture"], "public_cases": [json.loads(task_prompt(c).split("\n", 1)[0]) for c in select(args.case)],
                              "schedule": [] if args.command == "prepare" else schedule(args.case, conditions, args.repeats, args.command, args.seed)}, indent=2))
            return 0
        if args.command != "prepare":
            if not args.alias or any(not getattr(args, flag) for flag in
                    ("allow_live", "confirm_ofs_running", "allow_closed_loop", "allow_simulator_replacement", "confirm_simulator_alias")):
                raise ValueError("Explicit live/closed-loop/replacement/OFS/loopback-alias consent flags are required")
        if args.command == "run" and "REPLACE" in config["model"]["id"]:
            raise ValueError("Configure an exact model ID before a paid run")
        with ce_lock(Path(config["workspace"])):
            output = asyncio.run(prepare(config, args.case, conditions[0]) if args.command == "prepare" else campaign(config, args))
        print(output)
        if args.command == "prepare":
            entries = read_json(output)["cases"]
            return 0 if len(entries) == len(select(args.case)) and all(e["status"] == "prepared" for e in entries.values()) else 1
        return 0 if read_json(output / "outcome.json")["success"] else 1
    except (Exception, KeyboardInterrupt) as exc:
        print("IEC benchmark failed: " + type(exc).__name__, file=sys.stderr)
        if isinstance(exc, (ValueError, FileNotFoundError)):
            print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
