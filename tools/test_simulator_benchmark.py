"""Offline simulator policy, timing rubric and scripted lifecycle regressions."""
from __future__ import annotations

import io
from pathlib import Path
import tempfile
from contextlib import redirect_stdout
import unittest
from unittest.mock import Mock, patch

from mcp.types import CallToolResult

from control_expert_mcp.benchmark.core import read_json, write_json
from control_expert_mcp.benchmark.archive import archive_run
from control_expert_mcp.benchmark.simulator import (
    OBSERVATION, SimulatorMCP, TAG, grade_samples, main, observe, prepare, run_case,
)


def samples(period=1.0, step=1, start=0):
    return [{"elapsed": i / 10, "good": True,
             "value": start + int((i / 10 + 1e-8) / period) * step} for i in range(81)]


class TimingTests(unittest.TestCase):
    def test_success_depends_only_on_existence_and_one_second_unit_increments(self):
        result = grade_samples(samples(start=100))
        self.assertTrue(result["success"])
        self.assertEqual(result["increments"], 8)
        self.assertAlmostEqual(result["mean_period_seconds"], 1)

    def test_constant_fast_slow_reset_skipped_and_irregular_counters_fail(self):
        candidates = [samples(step=0), samples(period=.5), samples(period=2),
                      samples(step=2), samples(step=-1)]
        reset = samples()
        reset[40]["value"] = 0
        candidates.append(reset)
        irregular = samples()
        for s in irregular:
            s["value"] = sum(s["elapsed"] >= t for t in (1, 1.4, 3, 3.4, 5, 5.4, 7, 7.4))
        candidates.append(irregular)
        for data in candidates:
            with self.subTest(data=data[-1]):
                result = grade_samples(data)
                self.assertFalse(result["success"])
                self.assertEqual(result["runtime_behavior"], "fail")

    def test_missing_bad_quality_nonnumeric_and_sparse_observation_are_unverified(self):
        for value in (None, True, "1", float("nan"), float("inf")):
            data = samples()
            data[3]["value"] = value
            self.assertEqual(grade_samples(data)["runtime_behavior"], "unverified")
        data = samples()
        data[3]["good"] = False
        self.assertEqual(grade_samples(data)["runtime_behavior"], "unverified")
        self.assertEqual(grade_samples(samples()[::10])["runtime_behavior"], "unverified")
        self.assertEqual(grade_samples(samples()[:20])["runtime_behavior"], "unverified")
        self.assertEqual(grade_samples([])["runtime_behavior"], "unverified")

    def test_phase_offset_and_small_jitter_are_accepted_but_persistent_drift_is_not(self):
        data = samples()
        for s in data:
            s["elapsed"] += .01 if int(s["elapsed"] * 10) % 2 else 0
        self.assertTrue(grade_samples(data)["success"])
        self.assertFalse(grade_samples(samples(period=1.3))["success"])
        data = samples()
        for s in data:
            s["value"] = float(s["value"]) + .5
        self.assertTrue(grade_samples(data)["success"])


class PolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_forbidden_operations_are_rejected_before_transport(self):
        mcp = SimulatorMCP({}, {}, None, Path("case.stu"), "Demo", ["LLM_Existing"])
        mcp.opened = True
        names = {"write_st_logic", "create_variable", "open_project", "save_project", "plc_connect",
                 "plc_setup_connection", "plc_transfer", "plc_command", "opc_connect", "opc_read_tags"}
        schemas = [{"name": name} for name in names]
        forbidden = [
            ("opc_write_tags", {"values": {TAG: 1}}),
            ("write_st_logic", {"task": "MAST", "section": "Feeder"}),
            ("write_st_logic", {"task": "MAST", "section": "LLM", "declare": "Start:BOOL"}),
            ("create_variable", {"name": "LLM_Existing", "type_name": "BOOL"}),
            ("create_variable", {"name": TAG, "type_name": "DINT", "address": "%MW1"}),
            ("open_project", {"path": "original.stu"}),
            ("save_project", {"path": "original.stu"}),
            ("plc_setup_connection", {"target": "plc", "address": "192.168.0.1"}),
            ("plc_connect", {"target": "simulator"}),  # setup not recorded
            ("plc_connect", {"target": "plc"}),
            ("plc_transfer", {"direction": "pc_to_plc"}),  # no clean build
            ("plc_command", {"command": "init"}),
            ("opc_connect", {"alias": "Other"}),
            ("opc_read_tags", {"tags": ["Other!TEST_LLM"]}),
        ]
        for name, args in forbidden:
            self.assertTrue((await mcp.dispatch(name, args, schemas))["is_error"])
        self.assertTrue(all(c["policy_violation"] for c in mcp.model_calls))

    async def test_edits_invalidate_build_and_deployment_and_offline_policy_stays_separate(self):
        mcp = SimulatorMCP({}, {}, None, Path("case.stu"), "Demo")
        mcp.opened = mcp.built = mcp.deployed = True
        async def call(*args):
            return CallToolResult(structured_content={"section": "LLM"}, content=[])
        mcp.call = call
        await mcp.dispatch("write_st_logic", {"task": "MAST", "section": "LLM", "st_source": ""},
                           [{"name": "write_st_logic"}])
        self.assertFalse(mcp.built)
        self.assertFalse(mcp.deployed)
        self.assertEqual(mcp.server_environment()["CE_MCP_ENABLE_ONLINE"], "1")

    async def test_observer_uses_read_only_device_values_and_preserves_bad_quality(self):
        now = [0.0]
        async def sleep(seconds):
            now[0] += seconds
        client = Mock()
        client.read.side_effect = lambda tags: {
            "values": {TAG: int(now[0])}, "samples": {TAG: {"good": True, "quality": 192}}, "errors": {}}
        result = await observe(client, clock=lambda: now[0], sleep=sleep)
        self.assertTrue(grade_samples(result)["success"])
        client.write.assert_not_called()
        self.assertGreaterEqual(result[-1]["elapsed"], OBSERVATION["duration_seconds"])
        now[0] = 0
        client.read.side_effect = lambda tags: {
            "values": {}, "samples": {TAG: {"good": False, "quality": 0}}, "errors": {TAG: "bad quality"}}
        self.assertEqual(grade_samples(await observe(client, clock=lambda: now[0], sleep=sleep))[
            "runtime_behavior"], "unverified")


class FakeSimulator(SimulatorMCP):
    last = None
    taint_on_build = False
    fail_artifact = False

    async def __aenter__(self):
        FakeSimulator.last = self
        self.instructions = "Synthetic server"
        self.initialization = {"instructions": self.instructions}
        names = ("get_live_access_setup get_status open_project get_project_structure list_variables "
                 "read_section get_language_reference create_variable write_st_logic analyze_project "
                 "build_project save_project start_simulator plc_setup_connection plc_connect plc_state "
                 "plc_command plc_transfer opc_connect opc_status opc_browse opc_read_tags opc_disconnect").split()
        self.tools = [{"name": n, "input_schema": {"type": "object"}} for n in names]
        self.startup_seconds = self.discovery_seconds = 0
        self.state = "stop"
        self.seen = []
        return self

    async def __aexit__(self, *args):
        pass

    async def call(self, name, args):
        self.seen.append(name)
        if name == "build_project" and self.taint_on_build:
            self.tainted = True
            raise TimeoutError("synthetic outstanding CE operation")
        if name == "read_section" and self.fail_artifact:
            raise RuntimeError("synthetic export failure")
        value = {}
        if name == "build_project":
            value = {"build_state": "built_ok"}
        elif name in {"plc_connect", "plc_state"}:
            value = {"connected": True, "pc_equals_plc": True, "plc_state": self.state}
        elif name == "plc_transfer":
            value = {"transferred": "pc_to_plc"}
        elif name == "plc_command":
            self.state = args["command"]
            value = {"plc_state": self.state}
        elif name == "get_status":
            value = {"server_version": "16.4", "project": {"cpu": {}}}
        elif name == "read_section":
            value = {"xml": "<STExchangeFile/>"}
        return CallToolResult(structured_content=value, content=[])


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_preparation_accepts_com_boolean_dictionary_settings(self):
        calls = []
        class OfflineMCP:
            def __init__(self, *args):
                self.opened = False
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def checked(self, tool, **args):
                calls.append((tool, args))
                if tool == "open_project":
                    self.opened = True
                if tool == "get_status":
                    return {"session": "application open" if self.opened else "no application open",
                            "server_version": "16.4", "project": {"cpu": {"part_number": "M580", "version": "1"}}}
                if tool == "get_project_structure":
                    return {"tasks": [{"name": "MAST", "sections": []}]}
                if tool == "list_variables":
                    return {"returned": 0, "total_variables": 0, "variables": []}
                if tool == "get_project_setting":
                    return {"value": args["ident"] == "unity.dataDictionary"}
                if tool == "build_project":
                    return {"build_state": "built_ok"}
                return {}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "demo.stu"
            source.write_bytes(b"source demo")
            config = {"fixture": str(source), "workspace": str(root / "workspace"),
                      "conditions": {"SIMULATOR": {}}, "ce_version": "16.4",
                      "cpu": {"part_number": "M580", "version": "1"}}
            with patch("control_expert_mcp.benchmark.simulator.MCP", OfflineMCP):
                manifest = read_json(await prepare(config))
            self.assertEqual(source.read_bytes(), b"source demo")
            self.assertNotEqual(manifest["baseline"], str(source))
        self.assertFalse(any(name.startswith(("plc_", "opc_")) for name, _ in calls))

    async def exercise(self, root):
        baseline = root / "baseline.stu"
        baseline.write_bytes(b"untouched demo")
        config = {"model": {"id": "synthetic"}, "provider": {"name": "openai"},
                  "conditions": {"SIMULATOR": {}}, "ce_version": "16.4"}
        async def observed(client):
            return samples()
        with patch("control_expert_mcp.benchmark.simulator.SimulatorMCP", FakeSimulator), \
             patch("control_expert_mcp.benchmark.simulator.OpcClient"), \
             patch("control_expert_mcp.benchmark.simulator.observe", observed):
            result = await run_case(config, {"task": "simulator_counter"},
                {"baseline": str(baseline), "existing_variables": []}, root / "attempt",
                "fingerprint", "Demo", "validate")
        self.assertEqual(baseline.read_bytes(), b"untouched demo")
        self.assertEqual(read_json(root / "attempt" / "summary.json"), result)
        return result, FakeSimulator.last

    async def test_scripted_end_to_end_with_independent_grading_and_stop_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, mcp = await self.exercise(Path(temporary))
        self.assertTrue(result["success"])
        self.assertTrue(result["cleanup"]["verified"])
        self.assertEqual(mcp.state, "stop")
        for tool in ("open_project", "write_st_logic", "build_project", "plc_transfer", "opc_read_tags"):
            self.assertIn(tool, mcp.seen)

    async def test_tainted_session_stops_without_evaluation_or_cleanup_operations(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(FakeSimulator, "taint_on_build", True):
            result, mcp = await self.exercise(Path(temporary))
        self.assertFalse(result["success"])
        self.assertFalse(result["cleanup"]["verified"])
        self.assertEqual(mcp.seen[-1], "build_project")

    async def test_artifact_failure_does_not_override_counter_success(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(FakeSimulator, "fail_artifact", True):
            result, _ = await self.exercise(Path(temporary))
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "evaluation_failure")
        self.assertTrue(result["cleanup"]["verified"])


class CLITests(unittest.TestCase):
    def test_dry_run_has_no_connections_or_paid_requests(self):
        config = {"fixture": "demo.stu", "conditions": {"SIMULATOR": {"documentation": False}}}
        with patch("control_expert_mcp.benchmark.simulator.load_config", return_value=config), \
             patch("control_expert_mcp.benchmark.simulator.campaign") as campaign, \
             redirect_stdout(io.StringIO()) as output:
            status = main(["run", "--config", "unused.json", "--alias", "Demo", "--allow-live",
                           "--allow-closed-loop", "--confirm-ofs-running", "--allow-simulator-replacement", "--dry-run"])
        self.assertEqual(status, 0)
        self.assertIn('"live_connections":0', output.getvalue())
        campaign.assert_not_called()

    def test_scripted_or_unclean_simulator_runs_cannot_be_archived_as_llm_performance(self):
        for mode, clean in (("validate", True), ("run", False)):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                write_json(root / "campaign" / "plan.json", {
                    "snapshot": {"suite": "simulator-counter", "config": {}}, "mode": mode})
                write_json(root / "campaign" / "outcome.json", {"cleanup_verified": clean})
                with self.assertRaises(ValueError):
                    archive_run(root, "campaign", root / "archive")


if __name__ == "__main__":
    unittest.main()
