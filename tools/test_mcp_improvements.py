"""Online-change guard, undefined-symbol candidates, ST tick pattern and answer submission."""

import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from mcp.types import CallToolResult

from control_expert_mcp.bridge import CEError, ControlExpertBridge
from control_expert_mcp.diagnostics import attach_symbol_candidates, parse_diagnostics, rank_symbols
from control_expert_mcp.lang_reference import REFERENCES
from control_expert_mcp.live_access import LiveAccessPolicy
from control_expert_mcp.benchmark.core import Events
from control_expert_mcp.benchmark.simulator import SimulatorMCP
from control_expert_mcp.benchmark.tasks import inspect_grade
from control_expert_mcp.benchmark.transport import ANSWER_SCHEMAS, MCP, Evidence, answer_text, schema_errors
from test_benchmark import GOLD

VARIABLES = [{"name": n, "type": t} for n, t in (
    ("Measured_temp", "INT"), ("CMeasured_temp", "REAL"), ("Setpoint_temp", "REAL"),
    ("Temp_ok", "BOOL"), ("Feeder_state", "INT"), ("Mixing_done", "EBOOL"))]
E1061 = "{Feeder : [MAST]}\t: \t(l: 73, c: 30) E1061 undefined symbol 'CE_BENCH_UNDEFINED_TEMP_7F93' or namespace missing"


def snapshot(text):
    return {"available": True, "output": text, "tab": "Build", "read_errors": []}


def bridge(connected, outputs, project=None):
    value = object.__new__(ControlExpertBridge)
    value._ensure_app = Mock(return_value=SimpleNamespace(IsTargetConnected=int(connected)))
    value._project = Mock(return_value=project or SimpleNamespace(InfoBuildState=0, Build=Mock(), BuildAll=Mock()))
    value._do_capture_build_output = Mock(side_effect=[snapshot(t) for t in outputs])
    value._do_plc_state = Mock(return_value={"connected": True, "pc_equals_plc": True, "plc_state": "run"})
    return value


class OnlineChangeTests(unittest.TestCase):
    def test_connected_build_is_refused_without_explicit_permission(self):
        value = bridge(True, [""])
        with self.assertRaises(CEError):
            value._do_build(False)
        value._project.return_value.Build.assert_not_called()

    def test_connected_build_reports_online_change_and_target_state(self):
        value = bridge(True, ["", "Linking...\nDownloading and Executing On Line Changes...\nProcess succeeded  : 0 Error(s) , 0 Warning(s)"])
        result = value._do_build(False, allow_online_change=True)
        self.assertTrue(result["online_change_applied"])
        self.assertTrue(result["target_after_build"]["pc_equals_plc"])
        self.assertIn("online_change_note", result)

    def test_offline_build_is_unchanged(self):
        result = bridge(False, ["", "Process succeeded  : 0 Error(s) , 0 Warning(s)"])._do_build(False)
        self.assertNotIn("online_change_applied", result)
        self.assertNotIn("target_after_build", result)

    def test_online_change_permission_requires_closed_loop_approval(self):
        policy = LiveAccessPolicy(True)
        with self.assertRaises(ValueError):
            policy.require_closed_loop("Online change")
        policy.config = policy.validate(True, "engineering", allow_closed_loop=False)
        policy.configured = True
        with self.assertRaises(ValueError):
            policy.require_closed_loop("Online change")
        policy.config = policy.validate(True, "engineering", allow_closed_loop=True)
        policy.require_closed_loop("Online change")


class CandidateTests(unittest.TestCase):
    def test_ranked_candidates_carry_types_and_guidance(self):
        rows = parse_diagnostics(E1061 + "\n{Feeder : [MAST]} E1203 invalid assignment")
        attach_symbol_candidates(rows, VARIABLES)
        self.assertEqual(rows[0]["undefined_symbol"], "CE_BENCH_UNDEFINED_TEMP_7F93")
        names = {c["name"]: c["type"] for c in rows[0]["candidates"]}
        self.assertEqual(names["Measured_temp"], "INT")
        self.assertNotIn("Feeder_state", names)
        self.assertIn("constant", rows[0]["candidate_note"])
        self.assertNotIn("candidates", rows[1])
        self.assertEqual(rank_symbols("Measurd_temp", VARIABLES)[0]["name"], "Measured_temp")
        self.assertEqual(rank_symbols("zzz", VARIABLES), [])

    def test_build_attaches_candidates_from_project_variables(self):
        variables = [SimpleNamespace(Name=v["name"], TypeName=v["type"]) for v in VARIABLES]
        project = SimpleNamespace(InfoBuildState=0, Build=Mock(), BuildAll=Mock(), Variables=variables)
        result = bridge(False, ["", E1061], project)._do_build(False)
        self.assertIn("Measured_temp", [c["name"] for c in result["diagnostics"][0]["candidates"]])


class ReferenceTests(unittest.TestCase):
    def test_st_guide_has_self_restarting_tick(self):
        guide = REFERENCES["ST"]["guide"]
        self.assertIn("Tick(IN := NOT Tick.Q, PT := t#1s);", guide)
        self.assertIn("IN := TRUE fires once", guide)


class AnswerTests(unittest.TestCase):
    def test_schema_and_text(self):
        self.assertEqual(schema_errors(ANSWER_SCHEMAS["inspect"], GOLD), [])
        broken = {**GOLD, "decrement_event": {"edge": "up", "variable": "forming"}, "extra": 1}
        errors = schema_errors(ANSWER_SCHEMAS["inspect"], broken)
        self.assertTrue(any("edge" in e for e in errors) and any("extra" in e for e in errors))
        self.assertTrue(inspect_grade(answer_text("inspect", GOLD))["answer_pass"])
        self.assertEqual(answer_text("io_mapping", {"report": "## Table"}), "## Table")

    def test_dispatch_records_submission_without_mcp_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mcp = MCP({"documentation": False}, {}, Evidence(root, Events(root / "events.jsonl")))
            mcp.instructions, mcp.tools = "", [{"name": n, "input_schema": {"type": "object"}} for n in (
                "get_status", "get_project_structure", "list_variables", "read_section", "get_language_reference")]
            instructions, schemas = mcp.adapter("inspect")
            self.assertEqual(schemas[-1]["name"], "submit_answer")
            mcp.call = Mock(side_effect=AssertionError("submit_answer must not reach MCP"))
            bad = asyncio.run(mcp.dispatch("submit_answer", {"task": "MAST"}, schemas))
            self.assertTrue(bad["is_error"])
            self.assertIsNone(mcp.submitted)
            good = asyncio.run(mcp.dispatch("submit_answer", GOLD, schemas))
            self.assertFalse(good["is_error"])
            self.assertEqual(mcp.submitted, GOLD)
            kinds = [json.loads(line)["kind"] for line in (root / "events.jsonl").read_text().splitlines()]
            self.assertEqual(kinds, ["answer_submitted", "answer_submitted"])


class SimulatorDeploymentTests(unittest.IsolatedAsyncioTestCase):
    async def run_calls(self, calls):
        mcp = SimulatorMCP({}, {}, None, Path("case.stu"), "Demo")
        mcp.opened = mcp.simulator_connected = mcp.connection_configured = True
        mcp.policy_error = lambda *args: None
        values = iter([value for _, value in calls])
        async def call(*args):
            return CallToolResult(structured_content=next(values), content=[])
        mcp.call = call
        for name, _ in calls:
            await mcp.dispatch(name, {}, [])
        return mcp

    async def test_online_change_after_own_download_counts_as_deployment(self):
        built = {"build_state": "built_ok", "online_change_applied": True,
                 "target_after_build": {"pc_equals_plc": True, "plc_state": "run"}}
        mcp = await self.run_calls([("build_project", {"build_state": "built_ok"}),
                                    ("plc_transfer", {"transferred": "pc_to_plc"}),
                                    ("write_st_logic", {"section": "LLM"}), ("build_project", built)])
        self.assertTrue(mcp.deployed)
        mcp = await self.run_calls([("build_project", built)])
        self.assertFalse(mcp.deployed)
        stale = {**built, "target_after_build": {"pc_equals_plc": False}}
        mcp = await self.run_calls([("plc_transfer", {"transferred": "pc_to_plc"}),
                                    ("write_st_logic", {"section": "LLM"}), ("build_project", stale)])
        self.assertFalse(mcp.deployed)


if __name__ == "__main__":
    unittest.main()
