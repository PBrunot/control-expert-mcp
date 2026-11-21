"""Failure-inclusive aggregation; no token or runtime estimates."""
from __future__ import annotations

from collections import defaultdict
import math
from pathlib import Path
from statistics import median

from .core import read_json, write_json


def distribution(values: list) -> dict:
    known = sorted(v for v in values if v is not None)
    return {"n": len(values), "known_n": len(known), "unknown_n": len(values) - len(known),
            "median": median(known) if known else None,
            "p95": known[max(0, math.ceil(.95 * len(known)) - 1)] if known else None}


def aggregate(rows: list) -> dict:
    def rate(values):
        known = [value for value in values if value is not None]
        return {"pass": sum(value is True for value in known), "n": len(values),
                "verified_n": len(known), "rate_all": sum(value is True for value in known) / len(values) if values else None}
    def metrics(selected):
        return {"workflow_seconds": distribution([r.get("workflow_seconds") for r in selected]),
                **{key: distribution([r.get("usage", {}).get("tokens", {}).get(key) for r in selected])
                   for key in ("input_tokens", "output_tokens", "total_tokens")}}
    return {"cases": len(rows), "completion": rate([r.get("status") == "completed" for r in rows]),
            "accepted": rate([r.get("success", False) for r in rows]),
            "build": rate([r.get("validation", {}).get("compile_pass") for r in rows]),
            "static_behavior": rate([True if r.get("validation", {}).get("static_behavior") == "pass" else None for r in rows]),
            "runtime_behavior": rate([True if r.get("validation", {}).get("runtime_behavior") == "pass" else None for r in rows]),
            "all_attempts": metrics(rows), "accepted_attempts": metrics([r for r in rows if r.get("success")]),
            "known_partial_tokens": {key: sum(r.get("usage", {}).get("known_partial_tokens", {}).get(key, 0) for r in rows)
                                     for key in ("input_tokens", "output_tokens", "total_tokens")},
            "tool_errors": sum(r.get("tool_errors", 0) for r in rows),
            "repair_cycles": sum(r.get("repair_cycles", 0) for r in rows),
            "statuses": {status: sum(r["status"] == status for r in rows) for status in sorted({r["status"] for r in rows})}}


def compare(results: Path, output: Path) -> dict:
    groups = defaultdict(list)
    pairs = []
    interrupted = []
    aliases = []
    pending = []
    for plan_path in sorted(results.glob("*/plan.json")):
        plan = read_json(plan_path)
        if plan["snapshot"]["config"]["model"].get("identity") == "alias":
            aliases.append(plan["run_id"])
        for case in plan["schedule"]:
            attempts = sorted((plan_path.parent / case["case_id"]).glob("attempt-*"))
            if not attempts:
                pending.append({"run_id": plan["run_id"], **case})
            summaries = []
            for attempt in attempts:
                path = attempt / "summary.json"
                if path.exists():
                    row = read_json(path)
                    if row.get("fingerprint") != plan["fingerprint"]:
                        raise ValueError("Summary does not match campaign fingerprint")
                    summaries.append(row)
                else:
                    # Include partial usage retained before interruption.
                    partial = {**case, "status": "interrupted", "success": False,
                               "fingerprint": plan["fingerprint"], "usage": {"tokens": {}, "known_partial_tokens": {}}}
                    path = attempt / "events.jsonl"
                    if path.exists():
                        from .provider import Usage
                        import json
                        usage = Usage()
                        requested = 0
                        for line in path.read_text(encoding="utf-8").splitlines():
                            try:
                                event = json.loads(line)
                            except ValueError:
                                continue  # Crash can leave a partial final event.
                            if event["kind"] == "model_response":
                                blob = read_json(attempt / "blobs" / (event["response_ref"] + ".json"))
                                usage.add(blob.get("usage"))
                            elif event["kind"] == "model_request_failure":
                                usage.add(None)
                            elif event["kind"] == "model_request":
                                requested += 1
                        for _ in range(max(0, requested - usage.requests)):
                            usage.add(None)
                        partial["usage"] = usage.result()
                    groups[plan["fingerprint"]].append(partial)
                    interrupted.append(str(attempt))
            if summaries:
                groups[plan["fingerprint"]].extend(summaries)
                # Pair only within the same scheduled crossover campaign.
                pairs.append((plan["run_id"], case["task"], case["repeat"], summaries[-1]))
    report = {"groups": {}, "interrupted_attempts": interrupted, "scheduled_not_started": pending,
              "mutable_alias_campaigns": aliases,
              "limitations": ["API client/model results differ from ChatGPT UI orchestration.",
                              "Static acceptance does not validate PLC runtime semantics.",
                              "Cold server startup only; no mixed warm-run population.",
                              "Five repetitions is a starter experiment."]}
    if aliases:
        report["limitations"].append("Mutable model aliases cannot establish an unchanged underlying model snapshot, even when returned IDs match.")
    for fingerprint, rows in groups.items():
        conditions = sorted({r["condition"] for r in rows})
        report["groups"][fingerprint] = {
            condition: {"overall": aggregate([r for r in rows if r["condition"] == condition]),
                        "tasks": {task: aggregate([r for r in rows if r["condition"] == condition and r["task"] == task])
                                  for task in sorted({r["task"] for r in rows})}}
            for condition in conditions}
    paired = defaultdict(dict)
    for run_id, task, repeat, row in pairs:
        paired[(row["fingerprint"], run_id, task, repeat)][row["condition"]] = row
    deltas = defaultdict(lambda: defaultdict(list))
    for (fingerprint, _, task, _), arms in paired.items():
        if "A" in arms and "B" in arms:
            for key in ("workflow_seconds", "total_tokens"):
                vals = [arms[arm].get(key) if key == "workflow_seconds" else
                        arms[arm].get("usage", {}).get("tokens", {}).get(key) for arm in ("A", "B")]
                delta = vals[1] - vals[0] if all(v is not None for v in vals) else None
                deltas[fingerprint][f"{task}:{key}:B_minus_A"].append(delta)
    report["paired_differences"] = {fp: {key: distribution(vals) for key, vals in series.items()} for fp, series in deltas.items()}
    write_json(output.with_suffix(".json"), report)
    lines = ["# Control Expert API benchmark", "", *report["limitations"], "",
             "Distinct immutable fingerprints are reported separately. p95 uses nearest rank.", "",
             "| Group | Condition | Cases | Accepted | Built | Runtime verified | Median seconds | Median tokens |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for fp, conditions in report["groups"].items():
        for name, value in conditions.items():
            overall = value["overall"]
            lines.append(f"| {fp[:12]} | {name} | {overall['cases']} | {overall['accepted']['pass']} | "
                         f"{overall['build']['pass']} | {overall['runtime_behavior']['pass']} | "
                         f"{overall['all_attempts']['workflow_seconds']['median']} | {overall['all_attempts']['total_tokens']['median']} |")
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
