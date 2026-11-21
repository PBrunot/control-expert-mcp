"""Offline benchmark regression tests: synthetic MCP/provider, never CE or API."""
from __future__ import annotations

import asyncio
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from control_expert_mcp.benchmark.core import (Events, ce_lock, digest, environment, mark_tainted,
    git_metadata, read_json, snapshot, write_json)
from control_expert_mcp.benchmark.provider import Usage, credential, request_parameters, workflow
from control_expert_mcp.benchmark.report import aggregate, compare, distribution
from control_expert_mcp.benchmark.runner import (campaign, clean_build, contexts, make_schedule,
    prepare, prepared, run_case)
from control_expert_mcp.benchmark.tasks import (BROKEN_IDENTIFIER, PROMPTS, broken_source,
    declarations, inspect_grade, normalize, source, static_grade, threshold_source)
from control_expert_mcp.benchmark.transport import Evidence, MCP, visible_payload

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tools" / "lang_refs" / "ST_2_Feeder.xml"
GOLD = {"task": "MAST", "section": "Feeder", "language": "ST",
        "initialization_event": {"edge": "falling", "variable": "Mixing_done"},
        "initialization_expression": "material_a_value+material_b_value",
        "decrement_event": {"edge": "rising", "variable": "Forming"},
        "full_condition": "feeder_state>2", "empty_condition": "feeder_state<=2",
        "temperature": {"conversion": "int_to_real", "input": "Measured_temp", "converted": "Cmeasured_temp",
                        "comparison": "=", "setpoint": "Setpoint_temp"}}


class Response:
    _request_id = "synthetic-request"

    def __init__(self, output, status="completed", usage=True):
        self.raw = {"model": "synthetic-snapshot", "status": status, "output": output}
        if usage:
            self.raw["usage"] = {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14,
                "input_tokens_details": {"cached_tokens": 2}, "output_tokens_details": {"reasoning_tokens": 1}}

    def model_dump(self, **kwargs):
        return copy.deepcopy(self.raw)


class Provider:
    """A scripted provider whose edits derive from the MCP-visible source."""
    requests = []

    def __init__(self):
        self.responses = self
        self.turn = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def create(self, **request):
        self.requests.append(copy.deepcopy(request))
        task = next(key for key, prompt in PROMPTS.items() if prompt == request["input"][0]["content"])
        turn = self.turn
        self.turn += 1
        if turn == 0:
            name, args = "read_section", {"task": "MAST", "section": "Feeder"}
        elif task == "inspect" or turn == 4:
            text = json.dumps(GOLD) if task == "inspect" else "Built and saved synthetic edit"
            return Response([{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}])
        elif turn == 1:
            output = next(item for item in request["input"] if item.get("type") == "function_call_output")
            payload = json.loads(output["output"])
            value = payload.get("structured_content") or json.loads(payload["content"][0]["text"])
            st = source(value["xml"])
            if task == "threshold":
                st = threshold_source(st)
            elif task == "temperature":
                st = st.replace("cmeasured_temp=setpoint_temp", "ABS(cmeasured_temp-setpoint_temp)<=2.0")
            else:
                st = st.replace(BROKEN_IDENTIFIER, "Measured_temp")
            name, args = "write_st_logic", {"task": "MAST", "section": "Feeder", "st_source": st}
        elif turn == 2:
            name, args = "build_project", {"rebuild_all": True}
        else:
            name, args = "save_project", {}
        return Response([{"type": "reasoning", "id": f"reason-{turn}", "encrypted_content": "synthetic"},
                         {"type": "function_call", "name": name, "arguments": json.dumps(args), "call_id": f"call-{turn}"}])


def config(directory: Path):
    condition = {"command": sys.executable, "args": [str(ROOT / "tools" / "benchmark_fake_server.py")],
                 "cwd": str(ROOT), "env": {}, "documentation": False}
    return {"fixture": str(FIXTURE), "workspace": str(directory / "workspace with spaces"),
            "results": str(directory / "results"), "cpu": {"part_number": "Synthetic CPU", "version": "1"},
            "ce_version": "16.4", "model": {"id": "synthetic-snapshot", "max_output_tokens": 1000},
            "conditions": {"A": condition, "B": {**condition, "documentation": True}},
            "tool_timeout": 10, "request_timeout": 10, "workflow_timeout": 30,
            "max_turns": 8, "max_tool_calls": 8}


class CoreTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        patcher = patch("control_expert_mcp.benchmark.core.guard_directory", return_value=Path(temporary.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_fixture_mutations_and_grading(self):
        xml = FIXTURE.read_text(encoding="utf-8-sig")
        st = source(xml)
        self.assertEqual(len(declarations(xml)), 15)
        self.assertEqual(broken_source(st).count(BROKEN_IDENTIFIER), 1)
        with self.assertRaises(ValueError):
            broken_source(st + st)
        changed = threshold_source(st)
        grade = static_grade("threshold", st, changed)
        self.assertEqual(grade["static_behavior"], "pass")
        self.assertEqual(len(grade["boundary_cases"]), 6)
        self.assertEqual(static_grade("threshold", st, changed + "Sec:=true;")["scope"], "unverified")
        tolerance = st.replace("cmeasured_temp=setpoint_temp", "ABS(cmeasured_temp-setpoint_temp)<=2.0")
        self.assertEqual(static_grade("temperature", st, tolerance)["static_behavior"], "pass")
        self.assertEqual(static_grade("temperature", st, tolerance.replace("<=2.0", "<2.0"))["static_behavior"], "unverified")
        self.assertEqual(static_grade("repair", st, st)["scope"], "pass")
        self.assertTrue(inspect_grade(json.dumps(GOLD))["answer_pass"])
        self.assertFalse(inspect_grade(json.dumps({**GOLD, "full_condition": "feeder_state>=2"}))["answer_pass"])
        self.assertFalse(inspect_grade("not JSON")["answer_pass"])

    def test_usage_subsets_unknowns_and_errors(self):
        usage = Usage()
        self.assertIsNone(usage.result()["tokens"]["total_tokens"])
        usage.add(Response([]).raw["usage"])
        usage.add(Response([]).raw["usage"])
        self.assertEqual(usage.result()["tokens"]["total_tokens"], 28)
        self.assertEqual(usage.result()["tokens"]["reasoning_tokens"], 2)
        usage.add(None)
        self.assertIsNone(usage.result()["tokens"]["total_tokens"])
        self.assertEqual(usage.result()["known_partial_tokens"]["total_tokens"], 28)
        raw = {"is_error": True, "structured_content": {"x": 1}, "content": [
            {"type": "text", "text": '{"x":1}'}, {"type": "text", "text": "error"}]}
        self.assertEqual(visible_payload(raw)["content"], [{"type": "text", "text": "error"}])
        self.assertTrue(visible_payload(raw)["is_error"])

    def test_provider_parameters_and_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = config(Path(tmp))
            settings["model"]["reasoning_effort"] = "high"
            openai = request_parameters(settings)
            self.assertIn("include", openai)
            key_file = Path(tmp) / ".secrets"
            key_file.write_text("Deepseek API KEY : sk-synthetic-offline-only\n", encoding="utf-16")
            settings["provider"] = {"name": "deepseek", "api_key_file": str(key_file), "api_key_env": "CE_BENCH_TEST_NO_KEY"}
            params = request_parameters(settings)
            self.assertNotIn("store", params)
            self.assertNotIn("include", params)
            self.assertNotIn("parallel_tool_calls", params)
            self.assertEqual(params["reasoning"], {"effort": "high"})
            self.assertEqual(credential(settings), "sk-synthetic-offline-only")
            self.assertNotIn("sk-synthetic-offline-only", json.dumps(snapshot(settings)))

    def test_schedule_environment_build_and_aggregation(self):
        schedule = make_schedule(["A", "B"], 5, 17)
        self.assertEqual(len(schedule), 40)
        self.assertEqual(schedule, make_schedule(["A", "B"], 5, 17))
        self.assertNotEqual(schedule, make_schedule(["A", "B"], 5, 18))
        with patch.dict(os.environ, {"CE_MCP_ENABLE_ONLINE": "1", "OPENAI_API_KEY": "never-log"}):
            env = environment({"env": {"CE_MCP_ENABLE_ONLINE": "1"}})
            self.assertEqual(env["CE_MCP_ENABLE_ONLINE"], "0")
            self.assertNotIn("OPENAI_API_KEY", env)
        self.assertFalse(clean_build({"diagnostics": []}))
        self.assertFalse(clean_build({"build_state": "built_ok", "error": "failed"}))
        self.assertTrue(clean_build({"build_state": "built_ok", "diagnostics_capture": {"freshness": "unchanged"}}))
        self.assertEqual(distribution([1, 5, None])["unknown_n"], 1)
        rows = [{"status": "completed", "success": True, "usage": {"tokens": {"total_tokens": 20}}},
                {"status": "timeout", "success": False}]
        report = aggregate(rows)
        self.assertEqual(report["accepted"]["rate_all"], .5)
        self.assertEqual(report["all_attempts"]["total_tokens"]["known_n"], 1)

    def test_lock_taint_and_fingerprints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(TimeoutError):
                with ce_lock(root):
                    mark_tainted(root, {"reason": "synthetic timeout"})
                    raise TimeoutError()
            with self.assertRaises(RuntimeError):
                with ce_lock(root):
                    pass
            settings = config(root)
            before = snapshot(settings)
            settings["model"]["id"] = "different-snapshot"
            self.assertNotEqual(digest(before), digest(snapshot(settings)))
            self.assertIsNone(git_metadata(root)["revision"])


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        patcher = patch("control_expert_mcp.benchmark.core.guard_directory", return_value=Path(temporary.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_complete_local_loop_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = config(root)
            await prepare(settings, "A")
            manifest = prepared(settings)
            Provider.requests = []
            directory = await campaign(settings, ["A", "B"], 1, 19, provider_factory=Provider)
            summaries = [read_json(path) for path in directory.glob("*/attempt-*/summary.json")]
            self.assertEqual(len(summaries), 8)
            self.assertTrue(all(row["success"] for row in summaries),
                            [(row["case_id"], row["status"], row["failure_reason"], row["validation"]) for row in summaries if not row["success"]])
            self.assertEqual(sum("type" in item and item["type"] == "reasoning" for item in Provider.requests[1]["input"]), 1)
            count = len(Provider.requests)
            await campaign(settings, ["A", "B"], 1, 19, run_id=directory.name, provider_factory=Provider)
            self.assertEqual(len(Provider.requests), count)
            interrupted = next(directory.glob("threshold-000-A/attempt-*/summary.json"))
            interrupted.rename(interrupted.with_name("previous-summary.json"))
            (interrupted.parent / "project.stu").write_text("uncertain interrupted artifact", encoding="utf-8")
            await campaign(settings, ["A", "B"], 1, 19, run_id=directory.name, provider_factory=Provider)
            self.assertEqual(len(Provider.requests), count + 5)
            self.assertEqual(len(list(directory.glob("threshold-000-A/attempt-*"))), 2)
            self.assertEqual((interrupted.parent / "project.stu").read_text(), "uncertain interrupted artifact")
            report = compare(Path(settings["results"]), root / "comparison")
            self.assertEqual(len(report["groups"]), 1)
            self.assertTrue(report["paired_differences"])
            self.assertEqual(len(report["interrupted_attempts"]), 1)
            settings["model"]["id"] = "changed"
            with self.assertRaises(ValueError):
                await campaign(settings, ["A", "B"], 1, 19, run_id=directory.name, provider_factory=Provider)
            self.assertEqual(digest(Path(manifest["baseline"]).read_bytes()), manifest["baseline_sha256"])

    async def test_policy_limits_and_taint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = config(root)
            await prepare(settings, "A")
            ev = Evidence(root / "events", Events(root / "events" / "events.jsonl"))
            async with MCP(settings["conditions"]["A"], settings, ev) as mcp:
                _, schemas = mcp.adapter("threshold")
                self.assertNotIn("search_manuals", {s["name"] for s in schemas})
                for name, arguments in [("search_manuals", {}), ("save_project", {"path": "unrelated.stu"}),
                                        ("write_st_logic", {"task": "MAST", "section": "Other"})]:
                    self.assertTrue((await mcp.dispatch(name, arguments, schemas))["is_error"])
                result = {}
                settings["max_tool_calls"] = 1
                await mcp.checked("open_project", path=prepared(settings)["baseline"])
                mcp.phase = "workflow"
                await workflow(mcp, "threshold", settings, Provider(), ev, result)
                self.assertEqual(result["status"], "tool_limit")
                settings["tool_timeout"] = .001
                with self.assertRaises(TimeoutError):
                    await mcp.bounded(asyncio.sleep(1), "synthetic timeout")
                self.assertTrue(mcp.tainted)
                self.assertTrue((Path(settings["workspace"]) / "TAINTED.json").exists())

    async def test_incomplete_turn_limit_provider_timeout_and_deepseek_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = config(root)
            settings["provider"] = {"name": "deepseek"}
            settings["model"]["reasoning_effort"] = "high"
            ev = Evidence(root / "evidence", Events(root / "evidence" / "events.jsonl"))
            mcp = SimpleNamespace(adapter=lambda task: ("instruction", []),
                                  dispatch=AsyncMock(return_value={"is_error": True, "error": "synthetic"}))
            async def response(**request):
                if len(request["input"]) > 1:
                    self.assertEqual(request["input"][1]["content"][0]["text"], "synthetic reasoning")
                    return Response([], status="incomplete", usage=False)
                self.assertNotIn("include", request)
                return Response([{"type": "reasoning", "content": [{"type": "reasoning_text", "text": "synthetic reasoning"}]},
                                 {"type": "function_call", "call_id": "one", "name": "unavailable", "arguments": "{}"}])
            provider = SimpleNamespace(responses=SimpleNamespace(create=response))
            result = {}
            await workflow(mcp, "inspect", settings, provider, ev, result)
            self.assertEqual(result["status"], "incomplete")
            self.assertEqual(result["tool_errors"], 1)
            self.assertIsNone(result["usage"]["tokens"]["total_tokens"])
            settings["max_turns"] = 1
            await workflow(mcp, "inspect", settings, provider, ev, result)
            self.assertEqual(result["status"], "turn_limit")
            async def slow(**kwargs):
                await asyncio.sleep(1)
            settings["request_timeout"] = .001
            provider.responses.create = slow
            with self.assertRaises(TimeoutError):
                await workflow(mcp, "inspect", settings, provider, ev, result)
            self.assertIsNone(result["usage"]["tokens"]["total_tokens"])
            self.assertFalse((Path(settings["workspace"]) / "TAINTED.json").exists())


if __name__ == "__main__":
    unittest.main()
