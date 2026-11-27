"""Explicit deterministic inspection regrading; original paid-run evidence is immutable."""
from __future__ import annotations

import copy
from pathlib import Path

from .core import digest, read_json, write_json
from .tasks import RUBRIC_VERSION, inspect_grade, source, static_grade
from .alarms import ALARM_RUBRIC
from .demo import io_mapping_grade


def answer_file(attempt: Path) -> Path:
    """The graded answer: a structured submission when present, else the final message."""
    submitted = attempt / "graded-answer.txt"
    return submitted if submitted.exists() else attempt / "final-response.txt"


def regrade_alarms(run: Path, plan: dict) -> Path:
    """Re-prove saved alarm sections with the current interpreter; build/save evidence is retained."""
    fixture = Path(plan["snapshot"]["config"]["fixture"])
    if digest(fixture.read_bytes()) != plan["snapshot"]["fixture_sha256"]:
        raise ValueError("Fixture differs from the original campaign")
    baseline = source(fixture.read_text(encoding="utf-8-sig"))
    output = run / "regrades" / ALARM_RUBRIC
    for case in plan["schedule"]:
        if case["task"] != "alarms":
            continue
        for summary_path in sorted((run / case["case_id"]).glob("attempt-*/summary.json")):
            old = read_json(summary_path)
            section_path = summary_path.parent / "saved-section.xml"
            if old["fingerprint"] != plan["fingerprint"]:
                raise ValueError("Case fingerprint differs from campaign")
            if not section_path.exists():
                continue  # No saved artifact to regrade; the original result stands.
            prior = old["validation"]
            grade = {**prior, **static_grade("alarms", baseline, source(section_path.read_text(encoding="utf-8")))}
            success = old["status"] == "completed" and all((
                prior.get("declarations_pass"), prior.get("obtained_source_through_mcp"), prior.get("model_built"),
                prior.get("model_saved"), prior.get("compile_pass"),
                grade["scope"] == "pass", grade["static_behavior"] == "pass"))
            grade["success"] = success
            value = {"case_id": case["case_id"], "attempt_id": summary_path.parent.name,
                "fingerprint": plan["fingerprint"], "prior_rubric": prior.get("rubric"),
                "prior_success": old["success"], "rubric": ALARM_RUBRIC, "success": success,
                "summary_sha256": digest(summary_path.read_bytes()), "section_sha256": digest(section_path.read_bytes()),
                "grader_sha256": digest(Path(__file__).with_name("alarms.py").read_bytes()),
                "validation": grade, "method": "Saved-section static regrade; original build/save/declaration evidence retained. No API or CE calls."}
            path = output / case["case_id"] / (summary_path.parent.name + ".json")
            if path.exists() and read_json(path) != value:
                raise ValueError("Regrade already exists with different evidence; use a new rubric version")
            if not path.exists():
                write_json(path, value)
    return output


def regrade_inspection(results: Path, run_id: str, task: str = "inspect") -> Path:
    if Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ValueError("Invalid run ID")
    run = results / run_id
    plan = read_json(run / "plan.json")
    if task == "alarms":
        return regrade_alarms(run, plan)
    if task not in {"inspect", "io_mapping"}:
        raise ValueError("Unsupported answer regrade task")
    grader = inspect_grade
    rubric = RUBRIC_VERSION
    if task == "io_mapping":
        reference_path = Path(plan["snapshot"]["config"]["io_mapping_reference"])
        if digest(reference_path.read_bytes()) != plan["snapshot"]["demo_inputs"]["io_mapping_reference"]:
            raise ValueError("Reference differs from the original campaign")
        reference = reference_path.read_text(encoding="utf-8-sig")
        grader = lambda answer: io_mapping_grade(answer, reference)
        rubric = grader("")["rubric"]
    output = run / "regrades" / rubric
    for case in plan["schedule"]:
        if case["task"] != task:
            continue
        for summary_path in sorted((run / case["case_id"]).glob("attempt-*/summary.json")):
            old = read_json(summary_path)
            answer_path = answer_file(summary_path.parent)
            if old["fingerprint"] != plan["fingerprint"]:
                raise ValueError("Case fingerprint differs from campaign")
            grade = grader(answer_path.read_text(encoding="utf-8"))
            grade.update(scope=old["validation"].get("scope"), compile_pass=None,
                runtime_behavior="unverified", static_behavior=None,
                obtained_source_through_mcp=old["validation"].get("obtained_source_through_mcp"))
            success = (old["status"] == "completed" and grade["answer_pass"] and
                       grade["scope"] == "pass" and grade["obtained_source_through_mcp"] is True)
            grade["success"] = success
            value = {"case_id": case["case_id"], "attempt_id": summary_path.parent.name,
                "fingerprint": plan["fingerprint"], "prior_rubric": old["validation"].get("rubric"),
                "prior_success": old["success"], "rubric": rubric, "success": success,
                "summary_sha256": digest(summary_path.read_bytes()), "response_sha256": digest(answer_path.read_bytes()),
                "validation": grade, "method": "Answer-only deterministic regrade; original saved-artifact scope/read evidence retained. No API or CE calls."}
            if task == "io_mapping":
                value["reference_sha256"] = digest(reference_path.read_bytes())
                value["grader_sha256"] = digest(Path(__file__).with_name("demo.py").read_bytes())
                value["grader_dependencies"] = {name: digest(Path(__file__).with_name(name).read_bytes())
                                                for name in ("demo.py", "mapping_grade.py")}
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
    expected_task = ("io_mapping" if rubric.startswith("demo-io-mapping-") else
                     "alarms" if rubric.startswith("feeder-alarms-") else "inspect")
    if row["task"] != expected_task:
        return row
    run = summary_path.parents[2]
    path = run / "regrades" / rubric / row["case_id"] / (summary_path.parent.name + ".json")
    if expected_task == "alarms" and not path.exists():
        return row  # No saved section was available to regrade.
    grade = read_json(path)
    evidence, name = (("section_sha256", "saved-section.xml") if expected_task == "alarms"
                      else ("response_sha256", answer_file(summary_path.parent).name))
    if grade["summary_sha256"] != digest(summary_path.read_bytes()) or grade[evidence] != digest((summary_path.parent / name).read_bytes()):
        raise ValueError("Regrade source evidence changed")
    row = copy.deepcopy(row)
    row.update(success=grade["success"], validation=grade["validation"], scoring_view=rubric)
    return row
