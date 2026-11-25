"""Offline IEC contracts, native authoring policy, capture, scoring and graphics."""
from __future__ import annotations

import asyncio
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from control_expert_mcp.benchmark.core import write_json
from control_expert_mcp.benchmark.iec import main, schedule
from control_expert_mcp.benchmark.iec_artifact import validate_submission
from control_expert_mcp.benchmark.iec_capture import acquire, decode, instrument, layout
from control_expert_mcp.benchmark.iec_cases import CASES, map_submission, physical_name, task_prompt, translate
from control_expert_mcp.benchmark.iec_fixtures import vectors
from control_expert_mcp.benchmark.iec_grade import grade, result
from control_expert_mcp.benchmark.iec_reference import MUTANT_VECTOR, alternative_reference, reference
from control_expert_mcp.benchmark.iec_report import overview, summarize, write_report
from control_expert_mcp.benchmark.iec_runtime import IECMCP, create_public, extract, order
from control_expert_mcp.benchmark.transport import Evidence
from control_expert_mcp.benchmark.transport import MCP
from control_expert_mcp.benchmark.core import Events


EVIDENCE = {"artifact_valid": True, "build_ok": True}


def capture(case, *, mutant=False):
    """Independent test oracle, not simulator execution evidence."""
    state = False
    step = "Idle"
    rows = []
    for index, vector in enumerate(vectors(case), 1):
        x = vector["inputs"]
        for cycle in range(1, case.cycles + 1):
            if case.language == "ST":
                y = {"Result": min(999 if mutant else 1000, max(0, x["Raw"] - x["Offset"]))}
            elif case.language == "LD":
                state = ((not x["StopCmd"] and state or x["StartCmd"]) and x["Permit"] if mutant else
                         (x["StartCmd"] or state) and x["Permit"] and not x["StopCmd"])
                y = {"Running": state}
            elif case.language == "FBD":
                state = x["EnableCmd"] and (x["LevelValue"] <= 30 or state and
                            not (x["LevelValue"] > 70 if mutant else x["LevelValue"] >= 70))
                y = {"Demand": state}
            elif case.language == "IL":
                state = (x["SignalA"] or x["SignalB"]) if mutant else x["SignalA"] != x["SignalB"]
                y = {"Selected": x["EnableCmd"] and (x["OverrideCmd"] or state)}
            else:
                start, done, ack = (x[n] for n in ("StartCmd", "DoneCmd", "AckCmd"))
                if step == "Idle" and start and not ack and (mutant or not done):
                    step = "Active"
                elif step == "Active" and done and not start and not ack:
                    step = "Completed"
                elif step == "Completed" and ack and not start and not done:
                    step = "Idle"
                y = {"Busy": step == "Active", "Complete": step == "Completed"}
            rows.append({"vector": index, "cycle": cycle, "good": True, "inputs": dict(x), "outputs": dict(y)})
    return {"case_id": case.id, "run_id": 11, "artifact_id": 22, "done": True,
            "count": len(rows), "mode": "all_cycles", "snapshots": rows}


def score(case, data=None, evidence=None):
    return grade(case, evidence if evidence is not None else EVIDENCE,
                 capture(case) if data is None else data, run_id=11, artifact_id=22)


class FixtureTests(unittest.TestCase):
    def test_native_reference_shapes_against_installed_schema_when_available(self):
        from control_expert_mcp.schema import find_schema_dir, validate
        directory = find_schema_dir()
        if directory is None:
            self.skipTest("Installed CE schemas unavailable; no COM required")
        for case in CASES.values():
            data = map_submission(case, reference(case))
            if "xml" in data:
                checked = validate(data["xml"], directory)
                self.assertTrue(checked["valid"], checked["errors"])
        fbd = map_submission(CASES["iec_fbd_hysteresis"], reference(CASES["iec_fbd_hysteresis"]))["xml"]
        rejected = validate(fbd.replace('nbColumns="36"', 'nbColumns="40"'), directory)
        self.assertFalse(rejected["valid"])
        self.assertTrue(any("36 columns is the maximum" in error for error in rejected["errors"]))

    def test_exact_sizes_and_typed_initial_states(self):
        self.assertEqual([len(vectors(c)) for c in CASES.values()], [10, 11, 12, 13, 16])
        self.assertEqual([c.cycles for c in CASES.values()], [1, 1, 1, 4, 1])
        st = vectors(CASES["iec_st_clamp"])
        self.assertEqual(st[-2]["inputs"], {"Raw": 32767, "Offset": -32768})
        self.assertEqual(st[-1]["outputs"], {"Result": 0})

    def test_public_projection_has_no_private_fields_and_is_namespaced(self):
        for case in CASES.values():
            prompt = task_prompt(case)
            public = json.loads(prompt.split("\n", 1)[0])
            self.assertEqual(set(public), {"id", "language", "inputs", "outputs", "requirement", "initial", "cycles", "section", "helpers_prefix"})
            self.assertTrue(all(n.startswith("IEC_" + case.language + "_") for n, _ in public["inputs"] + public["outputs"]))
            self.assertNotIn("snapshots", prompt)
            self.assertNotIn("first_mismatch", prompt)

    def test_native_references_mutants_and_physical_mapping(self):
        for case in CASES.values():
            for mutant in (False, True):
                original = reference(case, mutant=mutant)
                self.assertEqual(validate_submission(case, original),
                                 validate_submission(case, map_submission(case, map_submission(case, original), reverse=True)))
        case = CASES["iec_st_clamp"]
        self.assertEqual(translate(case, "Result := Raw - Offset;"),
                         "IEC_ST_Result := IEC_ST_Raw - IEC_ST_Offset;")
        self.assertEqual(translate(case, "Bench_Count := Bench_Count + 1;"), "Bench_Count := Bench_Count + 1;")


class GradeTests(unittest.TestCase):
    def test_oracles_match_every_fixture_and_mutants_fail_at_specified_vector(self):
        for case in CASES.values():
            good = score(case)
            self.assertEqual(good["verdict"], "pass")
            self.assertEqual(good["correctness_percent"], 100)
            bad = score(case, capture(case, mutant=True))
            self.assertEqual(bad["verdict"], "output_mismatch")
            self.assertEqual(bad["first_mismatch"]["vector"], MUTANT_VECTOR[case.id])
            self.assertEqual(bad["first_mismatch"]["cycle"], case.cycles)
            self.assertLess(bad["correctness_percent"], 100)

    def test_percent_counts_output_cells_including_sfc_two_outputs(self):
        case = CASES["iec_sfc_sequence"]
        data = capture(case)
        data["snapshots"][3]["outputs"]["Busy"] = True
        value = score(case, data)
        self.assertEqual(value["matched_outputs"], 25)
        self.assertEqual(value["evaluated_outputs"], 26)
        self.assertAlmostEqual(value["correctness_percent"], 100 * 25 / 26)
        self.assertEqual(value["vector_scores"][0]["matched_outputs"], 1)
        self.assertFalse(value["success"])

    def test_sfc_intermediate_cycles_are_diagnostic_and_final_only_is_supported(self):
        case = CASES["iec_sfc_sequence"]
        data = capture(case)
        data["snapshots"][0]["outputs"] = {"Busy": True, "Complete": True}
        self.assertEqual(score(case, data)["verdict"], "pass")
        data["snapshots"] = [r for r in data["snapshots"] if r["cycle"] == 4]
        data.update(mode="final_cycles", count=13)
        self.assertEqual(score(case, data)["verdict"], "pass")

    def test_all_verdicts_and_unknown_scores(self):
        case = CASES["iec_st_clamp"]
        for evidence, verdict in (({}, "infrastructure_error"), ({"authoring": "unsupported"}, "unsupported_authoring"),
                                  ({"artifact_valid": False}, "artifact_invalid"),
                                  ({"artifact_valid": True, "build_ok": False}, "build_failed")):
            value = score(case, evidence=evidence)
            self.assertEqual(value["verdict"], verdict)
            self.assertIsNone(value["correctness_percent"])
            self.assertEqual(value["evaluated_outputs"], 0)

    def test_malformed_or_incomplete_trace_is_infrastructure_even_with_early_mismatch(self):
        case = CASES["iec_ld_latch"]
        for mutate in (
            lambda d: d.update(run_id=12), lambda d: d.update(artifact_id=True),
            lambda d: d.update(done=False), lambda d: d.update(count=10),
            lambda d: d["snapshots"].pop(), lambda d: d["snapshots"].reverse(),
            lambda d: d["snapshots"][1].update(vector=1),
            lambda d: d["snapshots"][-1].update(good=False),
            lambda d: d["snapshots"][-1]["outputs"].update(Running=1),
            lambda d: d["snapshots"][-1]["inputs"].update(Permit=False),
        ):
            data = capture(case)
            data["snapshots"][0]["outputs"]["Running"] = True
            mutate(data)
            value = score(case, data)
            self.assertEqual(value["verdict"], "infrastructure_error")
            self.assertIsNone(value["correctness_percent"])


class PolicyTests(unittest.TestCase):
    def test_typed_literals_bistables_and_inline_native_actions_are_valid_styles(self):
        for name in ("iec_st_clamp", "iec_fbd_hysteresis", "iec_sfc_sequence"):
            case = CASES[name]
            value = alternative_reference(case)
            self.assertEqual(validate_submission(case, value),
                             validate_submission(case, map_submission(case, map_submission(case, value), reverse=True)))

    def test_bistable_instances_must_be_scoped_and_match_the_declared_type(self):
        case = CASES["iec_fbd_hysteresis"]
        value = alternative_reference(case)
        value["helpers"]["LLM_Bistable"] = "BOOL"
        with self.assertRaisesRegex(ValueError, "Declare each native bistable"):
            validate_submission(case, value)
        with self.assertRaises(ValueError):
            validate_submission(CASES["iec_st_clamp"], {"st_source": "Result := 0;", "helpers": {"LLM_State": "RS"}})

    def test_native_actions_cannot_call_demo_actions_or_replace_the_chart_with_input_logic(self):
        case = CASES["iec_sfc_sequence"]
        for old, new in (("Busy := FALSE;", "Busy := StartCmd;"),
                         ("<sectionName>LLM_IdleOutputs</sectionName>", "<sectionName>Init_Robot</sectionName>")):
            value = alternative_reference(case)
            value["xml"] = value["xml"].replace(old, new)
            with self.assertRaises(ValueError):
                validate_submission(case, value)

    def test_native_actions_may_compute_local_transition_conditions_without_feedback(self):
        case = CASES["iec_sfc_sequence"]
        value = alternative_reference(case)
        value["xml"] = value["xml"].replace("Busy := FALSE;", "LLM_StartOnly := StartCmd AND NOT DoneCmd AND NOT AckCmd; Busy := FALSE;", 1)
        validate_submission(case, value)
        value["xml"] = value["xml"].replace("LLM_StartOnly := StartCmd", "LLM_StartOnly := LLM_StartOnly OR StartCmd")
        with self.assertRaises(ValueError):
            validate_submission(case, value)

    def test_native_import_rejection_returns_public_tool_error_for_repair(self):
        with tempfile.TemporaryDirectory() as temp:
            case = CASES["iec_st_clamp"]
            mcp = IECMCP({"documentation": False}, {}, Evidence(Path(temp), Events(Path(temp) / "events.jsonl")), case)
            with patch("control_expert_mcp.benchmark.iec_runtime.install", new=AsyncMock(side_effect=RuntimeError("native syntax error"))):
                payload = asyncio.run(mcp.dispatch("submit_candidate", {"st_source": "Result := 0;"}, [{"name": "submit_candidate"}]))
            self.assertTrue(payload["is_error"])
            self.assertIn("native syntax error", payload["error"])
            self.assertFalse(mcp.submitted)

    def test_reject_external_access_loops_input_writes_and_reserved_names(self):
        case = CASES["iec_st_clamp"]
        for source in ("Raw := 7;", "Result := %MW0;", "WHILE TRUE DO Result := 0; END_WHILE;",
                       "Result := Bench_Count;", "Result := READ_VAR(1);", "Result := DemoTemperature;",
                       "Result := 0; (* nested (* comment *) Bench_Count := 3; *)"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                validate_submission(case, {"st_source": source})

    def test_wrong_language_multiple_sections_declarations_entities_and_il_store(self):
        case = CASES["iec_ld_latch"]
        for xml in (reference(CASES["iec_il_select"])["xml"],
                    reference(case)["xml"].replace("</LDExchangeFile>", '<dataBlock/></LDExchangeFile>'),
                    reference(case)["xml"].replace("</LDExchangeFile>", '<program><identProgram name="Other"/></program></LDExchangeFile>'),
                    '<!DOCTYPE X [<!ENTITY a SYSTEM "file:///secret">]><LDExchangeFile/>'):
            with self.assertRaises(ValueError):
                validate_submission(case, {"xml": xml})
        il = CASES["iec_il_select"]
        with self.assertRaises(ValueError):
            validate_submission(il, {"xml": reference(il)["xml"].replace("ST Selected", "ST SignalA")})

    def test_sfc_requires_real_chart_and_combinational_helpers(self):
        case = CASES["iec_sfc_sequence"]
        for key, value in (("pre", "LLM_StartOnly := LLM_StartOnly OR StartCmd;"),
                           ("post", "Busy := StartCmd; Complete := AckCmd;"),
                           ("xml", reference(case)["xml"].replace('stepType="initialStep"', 'stepType="step"'))):
            submission = reference(case)
            submission[key] = value
            with self.assertRaises(ValueError):
                validate_submission(case, submission)

    def test_constant_output_bug_remains_functionally_scored_in_a_native_chart(self):
        case = CASES["iec_sfc_sequence"]
        submission = reference(case)
        submission["post"] = "Busy := TRUE; Complete := FALSE;"
        validate_submission(case, submission)
        data = capture(case)
        for row in data["snapshots"]:
            row["outputs"] = {"Busy": True, "Complete": False}
        value = score(case, data)
        self.assertEqual(value["verdict"], "output_mismatch")
        self.assertEqual(value["first_mismatch"]["vector"], 1)
        self.assertAlmostEqual(value["correctness_percent"], 100 * 14 / 26)

    def test_model_adapter_exposes_no_paths_or_live_tools_and_frozen_session_rejects_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            case = CASES["iec_st_clamp"]
            mcp = IECMCP({"documentation": False}, {}, Evidence(Path(temp), Events(Path(temp) / "events.jsonl")), case)
            allowed = ["read_section", "get_project_structure", "list_variables", "get_language_reference", "analyze_project", "build_project", "save_project"]
            mcp.tools = [{"name": name, "input_schema": {}} for name in allowed + ["open_project", "import_xml", "opc_read_tags", "export_xml"]]
            mcp.instructions = ""
            _, schemas = mcp.adapter(case.id)
            self.assertEqual({s["name"] for s in schemas}, set(allowed) | {"submit_candidate"})
            mcp.call = AsyncMock(side_effect=AssertionError("Must not reach server"))
            for name, args in (("open_project", {"path": "private.stu"}),
                               ("read_section", {"task": "MAST", "section": "Bench_Capture"}),
                               ("save_project", {"path": "elsewhere.stu"}),
                               ("submit_candidate", {"file_path": "fixture.xml"})):
                self.assertTrue(asyncio.run(mcp.dispatch(name, args, schemas))["is_error"])
            mcp.frozen = True
            self.assertTrue(asyncio.run(mcp.dispatch("build_project", {}, schemas))["is_error"])


class CaptureTests(unittest.TestCase):
    def test_layout_and_instrumentation_are_in_task_and_namespaced(self):
        for case in CASES.values():
            code = instrument(case, 11, 22)
            self.assertEqual(len(layout(case)), len(vectors(case)) * case.cycles)
            self.assertIn("IF Bench_Active THEN", code["before"])
            self.assertIn("Bench_V1_", code["before"])
            self.assertLess(code["before"].index("Bench_V1_"), code["before"].index("Bench_Initialized := TRUE"))
            self.assertIn("IF Bench_Active THEN", code["after"])
            self.assertIn(physical_name(case, case.inputs[0][0]), code["before"])
            self.assertIn("Bench_Done := TRUE", code["after"])
            self.assertNotIn("expected", json.dumps(code))

    def test_explicit_opc_decode(self):
        self.assertIs(decode(-1, "BOOL"), True)
        self.assertIs(decode(0, "BOOL"), False)
        for value, kind in ((2, "BOOL"), (True, "INT"), (3.0, "INT"), (32768, "INT")):
            with self.assertRaises(ValueError):
                decode(value, kind)

    def test_acquire_stable_buffer_and_stale_identity_blocks_start_write(self):
        case = CASES["iec_st_clamp"]
        expected = capture(case)

        class Client:
            def __init__(self, stale=False):
                self.started = False
                self.stale = stale
            def read(self, tags):
                values = {"Bench_RunId": 12 if self.stale else 11, "Bench_ArtifactId": 22,
                          "Bench_Ready": not self.started, "Bench_Done": self.started,
                          "Bench_Count": 10 if self.started else 0, "IEC_ST_Result": 0}
                for row in expected["snapshots"]:
                    prefix = f"Bench_S{row['vector']}_"
                    values.update({prefix + "Vector": row["vector"], prefix + "Cycle": row["cycle"]})
                    values.update({prefix + n: v for n, v in (row["inputs"] | row["outputs"]).items()})
                return {"values": {t: values[t] for t in tags}, "samples": {t: {"good": True} for t in tags}, "errors": {}}
            def write(self, values):
                self.started = True
                return {"written": values, "errors": {}}

        client = Client()
        actual = asyncio.run(acquire(client, case, 11, 22))
        self.assertEqual(score(case, actual)["verdict"], "pass")
        client = Client(stale=True)
        with self.assertRaises(ValueError):
            asyncio.run(acquire(client, case, 11, 22, timeout=0))
        self.assertFalse(client.started)

    def test_transient_symbol_quality_is_waited_out_before_the_only_start_write(self):
        case = CASES["iec_st_clamp"]
        good_capture = capture(case)
        class Client:
            started = False
            reads = 0
            writes = 0
            def read(self, tags):
                self.reads += 1
                if self.reads == 1:
                    return {"values": {}, "errors": {t: "symbol refresh" for t in tags},
                            "samples": {t: {"good": False, "quality": 0} for t in tags}}
                values = {"Bench_RunId": 11, "Bench_ArtifactId": 22, "Bench_Ready": not self.started,
                          "Bench_Done": self.started, "Bench_Count": 10 if self.started else 0, "IEC_ST_Result": 0}
                for row in good_capture["snapshots"]:
                    prefix = f"Bench_S{row['vector']}_"
                    values.update({prefix + "Vector": row["vector"], prefix + "Cycle": row["cycle"]})
                    values.update({prefix + n: v for n, v in (row["inputs"] | row["outputs"]).items()})
                return {"values": {t: values[t] for t in tags}, "samples": {t: {"good": True} for t in tags}}
            def write(self, values):
                self.writes += 1
                self.started = True
                return {"written": values}
        client = Client()
        actual = asyncio.run(acquire(client, case, 11, 22, sleep=AsyncMock()))
        self.assertEqual(score(case, actual)["verdict"], "pass")
        self.assertEqual(client.writes, 1)

    def test_permanently_bad_quality_has_a_deadline_and_never_writes(self):
        client = type("Client", (), {})()
        client.read = lambda tags: {"values": {}, "errors": {t: "not ready" for t in tags}}
        client.write = lambda values: self.fail("No write is allowed without readiness")
        with self.assertRaisesRegex(TimeoutError, "OFS readiness deadline"):
            asyncio.run(acquire(client, CASES["iec_st_clamp"], 11, 22, timeout=0))

    def test_timeout_is_not_a_functional_failure(self):
        class Client:
            def read(self, tags):
                values = {"Bench_RunId": 11, "Bench_ArtifactId": 22, "Bench_Ready": False,
                          "Bench_Done": False, "Bench_Count": 0}
                return {"values": values, "samples": {t: {"good": True} for t in tags}}
        with self.assertRaises(TimeoutError):
            asyncio.run(acquire(Client(), CASES["iec_st_clamp"], 11, 22, timeout=0))


class IntegrationTests(unittest.TestCase):
    def test_export_section_order_is_not_transported_into_private_project(self):
        case = CASES["iec_ld_latch"]
        xml = map_submission(case, reference(case))["xml"].replace('task="MAST"', 'task="MAST" SectionOrder="15"')
        mcp = type("Stub", (), {})()
        mcp.checked = AsyncMock(return_value={"xml": xml, "language": "LD"})
        value = asyncio.run(extract(mcp, case, {}))
        self.assertNotIn("SectionOrder", value["xml"])

    def test_checked_forwards_tool_name_argument_without_parameter_collision(self):
        from mcp.types import CallToolResult, TextContent
        mcp = type("Stub", (), {})()
        mcp.call = AsyncMock(return_value=CallToolResult(content=[TextContent(type="text", text='{"created": true}')]))
        value = asyncio.run(MCP.checked(mcp, "create_section", name="IEC_ST_Candidate", task="MAST"))
        self.assertTrue(value["created"])
        mcp.call.assert_awaited_once_with("create_section", {"name": "IEC_ST_Candidate", "task": "MAST"})

    def test_demo_order_preserves_background_sections_and_tasks(self):
        baseline = {"tasks": [{"name": "MAST", "sections": [{"name": "Demo", "language": "ST"}]}]}
        structure = deepcopy(baseline)
        structure["tasks"][0]["sections"].append({"name": "IEC_ST_Candidate", "language": "ST"})
        mcp = type("Stub", (), {})()
        mcp.checked = AsyncMock(return_value=structure)
        asyncio.run(order(mcp, ["IEC_ST_Candidate"], baseline))
        structure["tasks"][0]["sections"].reverse()
        with self.assertRaises(RuntimeError):
            asyncio.run(order(mcp, ["IEC_ST_Candidate"], baseline))

    def test_cli_routes_and_dry_run_without_provider_com_opc_or_manifest(self):
        root = Path(__file__).resolve().parents[1]
        with redirect_stdout(io.StringIO()) as out, patch("control_expert_mcp.benchmark.iec.campaign", side_effect=AssertionError("live")):
            self.assertEqual(main(["run", "--config", str(root / "benchmarks/iec.example.json"), "--dry-run"]), 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["com_connections"], 0)
        self.assertEqual(len(data["schedule"]), 10)
        from control_expert_mcp.benchmark.cli import main as cli
        with patch("control_expert_mcp.benchmark.iec.main", return_value=7) as entry:
            self.assertEqual(cli(["iec", "overview"]), 7)
        entry.assert_called_once_with(["overview"])

    def test_schedule_reference_restarts_and_mutants_are_separate(self):
        rows = schedule("all", ["A"], 1, "validate", 1729)
        self.assertEqual(len(rows), 15)
        self.assertEqual(sum(r["variant"] == "reference" for r in rows), 10)
        self.assertEqual(sum(r["variant"] == "mutant" for r in rows), 5)
        self.assertEqual(rows, schedule("all", ["A"], 1, "validate", 1729))

    def test_report_percent_unknown_and_graphics(self):
        case = CASES["iec_st_clamp"]
        rows = [{"case_id": "good", "task": case.id, "condition": "A", "variant": "synthetic-reference", "fingerprint": "fp", "validation": score(case)},
                {"case_id": "bad", "task": "iec_ld_latch", "condition": "A", "variant": "synthetic-reference", "fingerprint": "fp", "validation": result("infrastructure_error")}]
        stats = summarize(rows)
        self.assertEqual(stats["correctness_percent"], 100)
        self.assertEqual(stats["unverified_attempts"], 1)
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "run"
            write_report(directory, rows)
            write_json(directory / "plan.json", {"run_id": "SYNTHETIC", "fingerprint": "fp", "snapshot": {"suite": "iec"}, "schedule": rows})
            for row in rows:
                write_json(directory / row["case_id"] / "attempt-001/summary.json", row)
            graph = overview(Path(temp), Path(temp) / "overview.png")
            self.assertEqual(len(graph["groups"]), 1)
            for suffix in (".png", ".svg", ".json"):
                self.assertTrue((Path(temp) / ("overview" + suffix)).is_file())


if __name__ == "__main__":
    unittest.main()
