"""Pure IEC trace grader; accepts independent evidence, never model assertions."""
from __future__ import annotations

from .iec_cases import Case
from .iec_fixtures import valid_value, vectors

RUBRIC = "iec-native-trace-1"
VERDICTS = ("pass", "artifact_invalid", "build_failed", "output_mismatch",
            "infrastructure_error", "unsupported_authoring")


def result(verdict: str, reason: str = "", **extra) -> dict:
    if verdict not in VERDICTS:
        raise ValueError("Unknown IEC verdict")
    return {"rubric": RUBRIC, "verdict": verdict, "success": verdict == "pass",
            "correctness_percent": extra.pop("correctness_percent", None),
            "matched_outputs": extra.pop("matched_outputs", None),
            "evaluated_outputs": extra.pop("evaluated_outputs", 0),
            "compile_pass": extra.pop("compile_pass", None),
            "runtime_behavior": ("pass" if verdict == "pass" else
                                 "fail" if verdict == "output_mismatch" else "unverified"),
            "reason": reason, **extra}


def grade(case: Case, evidence: dict, capture: dict | None, *, run_id: int,
          artifact_id: int) -> dict:
    """Missing evidence is infrastructure failure, not proof of an invalid artifact.

    Artifact/authoring/build evidence is supplied by the trusted harness. Captures
    contain either every cycle, or only the final cycle of each vector.
    """
    if evidence.get("authoring") == "unsupported":
        return result("unsupported_authoring", evidence.get("reason", "No verified native authoring path"))
    if evidence.get("artifact_valid") is False:
        return result("artifact_invalid", evidence.get("reason", "Native structure/interface rejected"))
    if evidence.get("artifact_valid") is not True:
        return result("infrastructure_error", "Artifact inspection unavailable")
    if evidence.get("build_ok") is False:
        return result("build_failed", "Candidate build failed", compile_pass=False)
    if evidence.get("build_ok") is not True:
        return result("infrastructure_error", "Build evidence unavailable")
    try:
        if not isinstance(capture, dict):
            raise ValueError("No capture")
        for key, expected in (("run_id", run_id), ("artifact_id", artifact_id)):
            if type(capture.get(key)) is not int or capture[key] != expected:
                raise ValueError("Capture identity mismatch: " + key)
        if capture.get("case_id") != case.id or capture.get("done") is not True:
            raise ValueError("Capture not complete for this case")
        fixture = vectors(case)
        mode = capture.get("mode")
        if mode not in {"all_cycles", "final_cycles"}:
            raise ValueError("Unknown capture mode")
        cycles = range(1, case.cycles + 1) if mode == "all_cycles" else [case.cycles]
        order = [(v, c) for v in range(1, len(fixture) + 1) for c in cycles]
        snapshots = capture.get("snapshots")
        if (not isinstance(snapshots, list) or len(snapshots) != len(order)
                or type(capture.get("count")) is not int or capture["count"] != len(order)):
            raise ValueError("Incomplete snapshot count")
        # Validate the whole capture before assigning functional blame.
        for snapshot, (v, c) in zip(snapshots, order):
            if not isinstance(snapshot, dict) or snapshot.get("good") is not True:
                raise ValueError("Bad or missing sample quality")
            if (type(snapshot.get("vector")) is not int or type(snapshot.get("cycle")) is not int
                    or (snapshot["vector"], snapshot["cycle"]) != (v, c)):
                raise ValueError("Snapshot order/index mismatch")
            for group, fields in (("inputs", case.inputs), ("outputs", case.outputs)):
                values = snapshot.get(group)
                if not isinstance(values, dict) or set(values) != {n for n, _ in fields}:
                    raise ValueError("Missing or unexpected snapshot fields")
                if any(not valid_value(values[n], t) for n, t in fields):
                    raise ValueError("Malformed typed sample")
            if snapshot["inputs"] != fixture[v - 1]["inputs"]:
                raise ValueError("Applied vector differs from fixture")
        mismatches = []
        for snapshot in snapshots:
            if snapshot["cycle"] != case.cycles:
                continue
            expected = fixture[snapshot["vector"] - 1]["outputs"]
            for name, _ in case.outputs:
                if snapshot["outputs"][name] != expected[name]:
                    mismatches.append({"vector": snapshot["vector"], "cycle": snapshot["cycle"],
                                       "inputs": snapshot["inputs"], "output": name,
                                       "expected": expected[name], "observed": snapshot["outputs"][name]})
        total = len(fixture) * len(case.outputs)
        matched = total - len(mismatches)
        per_vector = [{"vector": index, "matched_outputs": len(case.outputs) - sum(
            m["vector"] == index for m in mismatches), "total_outputs": len(case.outputs)}
            for index in range(1, len(fixture) + 1)]
        return result("output_mismatch" if mismatches else "pass", compile_pass=True,
                      correctness_percent=100.0 * matched / total, matched_outputs=matched,
                      evaluated_outputs=total, vector_scores=per_vector,
                      mismatches=mismatches, first_mismatch=mismatches[0] if mismatches else None,
                      snapshots=len(snapshots))
    except (KeyError, TypeError, ValueError) as exc:
        return result("infrastructure_error", str(exc), compile_pass=True)
