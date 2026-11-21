"""Append-only, allowlisted benchmark evidence suitable for a Git repository."""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import subprocess
import uuid

from .core import digest, read_json, write_json
from .report import aggregate, distribution
from .provider import Usage


def source_identity(value: dict) -> dict:
    return {key: value.get(key) for key in ("revision", "dirty", "dirty_fingerprint")}


def summarize_validation(value: dict) -> dict:
    result = {key: value[key] for key in (
        "rubric", "answer_pass", "scope", "static_behavior", "runtime_behavior", "compile_pass",
        "declarations_pass", "model_built", "model_saved", "success", "obtained_source_through_mcp",
        "evaluator_seconds", "partition_cases", "int_domain", "runtime_checks") if key in value}
    build = value.get("build", {})
    if build:
        capture = build.get("diagnostics_capture", {})
        result["build"] = {"build_state": build.get("build_state"), "error_present": bool(build.get("error")),
            "diagnostics_available": build.get("diagnostics_available"),
            "diagnostics_summary": {k: build.get("diagnostics_summary", {}).get(k) for k in ("process_status", "errors", "warnings")},
            "capture": {k: capture.get(k) for k in ("freshness", "attribution", "scope", "source_tab")}}
    return result


def interrupted_attempt(attempt: Path, case: dict, fingerprint: str) -> dict:
    usage = Usage()
    requested, tool_calls, errors, retries = 0, 0, 0, 0
    events = attempt / "events.jsonl"
    if events.exists():
        for line in events.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event["kind"] == "model_response":
                raw = read_json(attempt / "blobs" / (event["response_ref"] + ".json"))
                usage.add(raw.get("usage"))
            elif event["kind"] == "model_request_failure":
                usage.add(None)
            elif event["kind"] == "model_request":
                requested += 1
                retries += int(event.get("connection_attempt", 0) > 0)
            elif event["kind"] == "mcp_call" and event.get("phase") == "workflow":
                tool_calls += 1
                errors += int(event.get("is_error", False))
    for _ in range(max(0, requested - usage.requests)):
        usage.add(None)
    return {**case, "fingerprint": fingerprint, "status": "interrupted", "success": False,
            "durable_completed": False, "model_requests": requested, "usage": usage.result(),
            "tool_calls": tool_calls, "tool_errors": errors, "api_retries": retries}


def interaction_metrics(attempt: Path) -> dict:
    calls = defaultdict(list)
    requests = []
    event_path = attempt / "events.jsonl"
    if event_path.exists():
        for line in event_path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event["kind"] == "mcp_call" and event.get("phase") == "workflow":
                calls[event["tool"]].append(event["elapsed"])
            elif event["kind"] in {"model_response", "model_request_failure"}:
                requests.append(event["elapsed"])
    return {"model_request_seconds": distribution(requests),
            "mcp_round_trip_seconds": {name: distribution(values) for name, values in calls.items()}}


def verified_commit(server: dict, proof: dict) -> str:
    """Link a dirty run to a later commit only when every runtime Python file matches."""
    root = Path(server["source"]["root"])
    package = Path(server["runtime"]["package_path"]).relative_to(root).as_posix()
    commit = proof["commit"]
    resolved = subprocess.check_output(["git", "-C", str(root), "rev-parse", "--verify", commit + "^{commit}"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    paths = subprocess.check_output(["git", "-C", str(root), "ls-tree", "-r", "--name-only", resolved, "--", package]).decode().splitlines()
    hashes = {str(Path(path).relative_to(package).as_posix()): digest(subprocess.check_output(
        ["git", "-C", str(root), "show", f"{resolved}:{path}"]).replace(b"\r\n", b"\n")) for path in paths if path.endswith(".py")}
    if hashes != proof["canonical_file_sha256"] or digest(proof["raw_file_sha256"]) != server["runtime"]["package_tree"]:
        raise ValueError("Proposed source commit does not match the measured runtime package")
    return resolved


def archive_run(results: Path, run_id: str, destination: Path, *, allow_incomplete=False) -> Path:
    """Archive numeric/boolean metadata only; never copy raw project/model payloads."""
    if Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ValueError("Invalid run ID")
    run = results / run_id
    plan = read_json(run / "plan.json")
    snapshot = plan["snapshot"]
    config = snapshot["config"]
    live = snapshot.get("suite") == "opc-live"
    if live and plan.get("mode") != "run":
        raise ValueError("Scripted OPC validation is not an LLM benchmark run")
    if live and not read_json(run / "outcome.json").get("restoration_verified"):
        raise ValueError("OPC run did not verify restoration; preserve local evidence and investigate")
    proofs_path = run / "source-verification.json"
    proofs = read_json(proofs_path) if proofs_path.exists() else {}
    rows = []
    missing = []
    for case in plan["schedule"]:
        attempts = sorted((run / case["case_id"]).glob("attempt-*"))
        for attempt in attempts:
            summary_path = attempt / "summary.json"
            row = read_json(summary_path) if summary_path.exists() else interrupted_attempt(attempt, case, plan["fingerprint"])
            if row["fingerprint"] != plan["fingerprint"]:
                raise ValueError("Case fingerprint differs from campaign")
            safe = {key: row[key] for key in (
                "case_id", "task", "repeat", "condition", "fingerprint", "status", "failure_reason",
                "cold_start", "provider", "requested_model", "returned_models", "model_identity",
                "startup_seconds", "discovery_seconds", "setup_seconds", "reset_seconds", "workflow_seconds",
                "total_seconds", "tool_calls", "tool_errors", "repair_cycles", "api_retries", "transport_retries",
                "model_requests", "usage", "success", "durable_completed", "provider_failure_code") if key in row}
            safe["attempt_id"] = attempt.name
            safe["interaction_metrics"] = interaction_metrics(attempt)
            safe["validation"] = summarize_validation(row.get("validation", {}))
            safe["artifact_sha256"] = {name: digest((attempt / name).read_bytes())
                for name in ("project.stu", "saved-section.xml", "saved-variables.xml") if (attempt / name).exists()}
            rows.append(safe)
        if not any(row["case_id"] == case["case_id"] and row.get("durable_completed") for row in rows):
            missing.append(case["case_id"])
    if missing and not allow_incomplete:
        raise ValueError("Campaign has unfinished cases; use --allow-incomplete to archive a labeled snapshot")
    servers = {}
    for name, server in snapshot["servers"].items():
        corpus = server.get("documentation") or {}
        servers[name] = {"source": source_identity(server.get("source", {})),
            "runtime_package_sha256": server.get("runtime", {}).get("package_tree"),
            "dependencies": server.get("runtime", {}).get("dependencies"),
            "documentation_available": config["conditions"][name]["documentation"],
            "corpus_sha256": corpus.get("sha256"), "corpus_files": len(corpus.get("files", {})),
            "environment_sha256": digest(server.get("environment", {}))}
        if name in proofs:
            servers[name]["verified_source_commit"] = verified_commit(server, proofs[name])
            servers[name]["source_verification"] = proofs[name]
    groups = {}
    for condition in sorted({row["condition"] for row in rows}):
        selected = [row for row in rows if row["condition"] == condition]
        groups[condition] = {"overall": aggregate(selected),
            "tasks": {task: aggregate([row for row in selected if row["task"] == task])
                      for task in sorted({row["task"] for row in selected})}}
    pairs = defaultdict(dict)
    for row in rows:
        pairs[(row["task"], row["repeat"])][row["condition"]] = row
    differences = defaultdict(list)
    for (task, _), arms in pairs.items():
        if "A" not in arms or "B" not in arms:
            continue
        for metric in ("workflow_seconds", "total_tokens"):
            values = [arms[c].get(metric) if metric == "workflow_seconds" else
                      arms[c].get("usage", {}).get("tokens", {}).get(metric) for c in ("A", "B")]
            delta = values[1] - values[0] if all(v is not None for v in values) else None
            differences[f"{task}:{metric}:B_minus_A"].append(delta)
    record = {"archive_version": 1, "run_id": run_id, "fingerprint": plan["fingerprint"],
        "complete": not missing, "unfinished_cases": missing, "scheduled_cases": len(plan["schedule"]),
        "model": config["model"], "provider": config.get("provider", {}).get("name", "openai"),
        "cpu": config["cpu"], "ce_version": config.get("ce_version"),
        "machine_sha256": digest(snapshot["machine"]), "harness": source_identity(snapshot["harness"]),
        "dependencies": snapshot["dependencies"], "servers": servers,
        "fixture_sha256": snapshot["fixture_sha256"], "rubric_version": snapshot["rubric_version"],
        "prompt_sha256": {task: digest(prompt) for task, prompt in snapshot["prompts"].items()},
        "orientation_sha256": digest(snapshot["orientation"]), "contexts": plan.get("contexts"),
        "provider_retry_policy": snapshot.get("provider_retry_policy"),
        "seed": plan["seed"], "schedule": plan["schedule"], "cases": rows, "conditions": groups,
        "paired_differences": {key: distribution(values) for key, values in differences.items()},
        "suite": snapshot.get("suite", "offline-feeder"),
        "limitations": ["Small repetition counts are exploratory, not statistically strong comparisons.",
            ("Live scalar OPC input/output checks on PLC Simulator; no physical hardware validation."
             if live else "Static recognized-subset acceptance; PLC runtime behavior remains unverified."),
            "API client/model experiment, distinct from ChatGPT UI.",
            "Dirty source fingerprints identify uncommitted code; do not label them a clean revision."]}
    if live:
        outcome = read_json(run / "outcome.json")
        record["runtime_environment"] = {"ofs": {k: outcome.get("ofs", {}).get(k) for k in
            ("version", "worker_bits", "server_state")}, "restoration_verified": True,
            "alias_sha256": digest(plan["alias"])}
    regrades = []
    for path in sorted((run / "regrades").glob("*/*/*.json")):
        from .regrade import regraded_row
        grade = read_json(path)
        summary = run / grade["case_id"] / grade["attempt_id"] / "summary.json"
        regraded_row(summary, grade["rubric"])  # Validate source evidence hashes.
        regrades.append(grade)
    record["inspection_regrades"] = regrades
    record["regraded_conditions"] = {}
    for rubric in sorted({grade["rubric"] for grade in regrades}):
        revised = []
        for row in rows:
            value = dict(row)
            grade = next((g for g in regrades if g["rubric"] == rubric and g["case_id"] == row["case_id"] and g["attempt_id"] == row["attempt_id"]), None)
            if grade:
                value.update(success=grade["success"], validation=grade["validation"])
            revised.append(value)
        record["regraded_conditions"][rubric] = {condition: aggregate([row for row in revised if row["condition"] == condition])
                                               for condition in sorted({row["condition"] for row in rows})}
    if config["model"].get("identity") == "alias":
        record["limitations"].append("Mutable provider alias: matching model IDs do not guarantee identical weights over time.")
    target = destination / (run_id + ("-partial-" + digest(record)[:10] if missing else ""))
    if target.exists():
        if read_json(target / "record.json") != record:
            raise ValueError("Archive is immutable; use a new run ID for changed evidence")
        checksums = read_json(target / "checksums.json")
        if set(checksums) != {"record.json", "report.md"} or any(
                digest((target / name).read_bytes()) != expected for name, expected in checksums.items()):
            raise ValueError("Archive checksum mismatch; preserve and investigate existing evidence")
        update_index(destination)
        return target
    staging = destination.resolve() / (".staging-" + uuid.uuid4().hex)
    staging.mkdir(parents=True, exist_ok=False)
    write_json(staging / "record.json", record)
    lines = ["# " + run_id, "", f"Provider/model: `{record['provider']}` / `{record['model']['id']}`.",
             f"Harness base revision: `{record['harness']['revision']}`; dirty: `{record['harness']['dirty']}`.", "",
             *["- " + value for value in record["limitations"]], "",
             "| Condition | Task | Attempts | Accepted | Build passes | Median workflow s | Median total tokens |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for condition, group in groups.items():
        for task, value in {**group["tasks"], "overall": group["overall"]}.items():
            lines.append(f"| {condition} | {task} | {value['cases']} | {value['accepted']['pass']} | {value['build']['pass']} | "
                f"{value['all_attempts']['workflow_seconds']['median']} | {value['all_attempts']['total_tokens']['median']} |")
    lines += ["", "Original results above remain unchanged. Explicit inspection regrades:", ""]
    for rubric, conditions in record["regraded_conditions"].items():
        for condition, value in conditions.items():
            lines.append(f"- `{rubric}`, {condition}: {value['accepted']['pass']}/{value['cases']} accepted.")
    lines += ["", "Measured Python source verified against Git (CRLF/LF normalized):", ""]
    for condition, server in servers.items():
        if server.get("verified_source_commit"):
            lines.append(f"- {condition}: `{server['verified_source_commit']}` (original dirty-state metadata retained).")
    (staging / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(staging / "checksums.json", {name: digest((staging / name).read_bytes()) for name in ("record.json", "report.md")})
    if not staging.resolve().is_relative_to(destination.resolve()) or not target.resolve().is_relative_to(destination.resolve()):
        raise ValueError("Archive destination escaped intended directory")
    staging.rename(target.resolve())
    update_index(destination)
    return target


def update_index(destination: Path) -> None:
    # The index is derived; individual run directories are append-only.
    entries = []
    for path in sorted(destination.glob("*/record.json")):
        if path.parent.name.startswith("."):
            continue
        value = read_json(path)
        entries.append({"path": path.parent.name, "run_id": value["run_id"], "provider": value["provider"],
            "model": value["model"], "harness": value["harness"], "servers": value["servers"],
            "complete": value["complete"], "conditions": value["conditions"],
            "regraded_conditions": value.get("regraded_conditions", {})})
    write_json(destination / "index.json", entries)
    index = ["# Archived benchmark runs", "", "Sanitized results intended for Git history. Raw evidence stays local.", "",
             "![Graphical benchmark overview](overview.png)", "",
             "Regenerate from this archive with `ce-bench visualize --archive benchmarks/archive --output benchmarks/archive/overview.png`.", "",
             "| Run | Provider | Model | Measured source | Original accepted | Regraded accepted | Complete |", "|---|---|---|---|---|---|---|"]
    for value in entries:
        revisions = sorted({server.get("verified_source_commit") or server.get("source", {}).get("revision") or "unknown"
                            for server in value["servers"].values()})
        original = sum(arm["overall"]["accepted"]["pass"] for arm in value["conditions"].values())
        total = sum(arm["overall"]["cases"] for arm in value["conditions"].values())
        revised = "; ".join(f"{rubric}: {sum(arm['accepted']['pass'] for arm in arms.values())}/{sum(arm['cases'] for arm in arms.values())}"
                            for rubric, arms in value.get("regraded_conditions", {}).items()) or "none"
        index.append(f"| [{value['run_id']}]({value['path']}/report.md) | {value['provider']} | {value['model']['id']} | "
                     f"{', '.join(rev[:12] for rev in revisions)} | {original}/{total} | {revised} | {value['complete']} |")
    (destination / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")
