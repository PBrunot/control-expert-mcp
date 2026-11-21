"""Explicit deterministic inspection regrading; original paid-run evidence is immutable."""
from __future__ import annotations

import copy
from pathlib import Path

from .core import digest, read_json, write_json
from .tasks import RUBRIC_VERSION, inspect_grade


def regrade_inspection(results: Path, run_id: str) -> Path:
    if Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ValueError("Invalid run ID")
    run = results / run_id
    plan = read_json(run / "plan.json")
    output = run / "regrades" / RUBRIC_VERSION
    for case in plan["schedule"]:
        if case["task"] != "inspect":
            continue
        for summary_path in sorted((run / case["case_id"]).glob("attempt-*/summary.json")):
            old = read_json(summary_path)
            answer_path = summary_path.parent / "final-response.txt"
            if old["fingerprint"] != plan["fingerprint"]:
                raise ValueError("Case fingerprint differs from campaign")
            grade = inspect_grade(answer_path.read_text(encoding="utf-8"))
            grade.update(scope=old["validation"].get("scope"), compile_pass=None,
                runtime_behavior="unverified", static_behavior=None,
                obtained_source_through_mcp=old["validation"].get("obtained_source_through_mcp"))
            success = (old["status"] == "completed" and grade["answer_pass"] and
                       grade["scope"] == "pass" and grade["obtained_source_through_mcp"] is True)
            grade["success"] = success
            value = {"case_id": case["case_id"], "attempt_id": summary_path.parent.name,
                "fingerprint": plan["fingerprint"], "prior_rubric": old["validation"].get("rubric"),
                "prior_success": old["success"], "rubric": RUBRIC_VERSION, "success": success,
                "summary_sha256": digest(summary_path.read_bytes()), "response_sha256": digest(answer_path.read_bytes()),
                "validation": grade, "method": "Answer-only deterministic regrade; original saved-artifact scope/read evidence retained. No API or CE calls."}
            path = output / case["case_id"] / (summary_path.parent.name + ".json")
            if path.exists() and read_json(path) != value:
                raise ValueError("Regrade already exists with different evidence; use a new rubric version")
            if not path.exists():
                write_json(path, value)
    return output


def regraded_row(summary_path: Path, rubric: str) -> dict:
    if Path(rubric).name != rubric or rubric in {".", ".."}:
        raise ValueError("Invalid rubric")
    row = read_json(summary_path)
    if row["task"] != "inspect":
        return row
    run = summary_path.parents[2]
    path = run / "regrades" / rubric / row["case_id"] / (summary_path.parent.name + ".json")
    grade = read_json(path)
    if grade["summary_sha256"] != digest(summary_path.read_bytes()) or grade["response_sha256"] != digest((summary_path.parent / "final-response.txt").read_bytes()):
        raise ValueError("Regrade source evidence changed")
    row = copy.deepcopy(row)
    row.update(success=grade["success"], validation=grade["validation"], scoring_view=rubric)
    return row
