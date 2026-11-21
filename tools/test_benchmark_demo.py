"""Full-demo grading and tool policy controls; no CE or provider needed."""
from pathlib import Path
import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock

from control_expert_mcp.benchmark.demo import io_mapping_grade, weighing_grade, DEMO_PROMPTS, io_mapping_grade_v1, table_rows
from control_expert_mcp.benchmark.report import aggregate
from control_expert_mcp.benchmark.core import digest, read_json, write_json
from control_expert_mcp.benchmark.regrade import regrade_inspection, regraded_row
from control_expert_mcp.benchmark.runner import make_schedule, task_fixture, evaluate
from control_expert_mcp.benchmark.transport import MCP, READ_TOOLS, EDIT_TOOLS

REFERENCE = Path(__file__).resolve().parents[1] / "samples/demo_ControlExpert_M580_io_mapping.md"


class DemoTests(unittest.IsolatedAsyncioTestCase):
    def test_weighing_identifiers(self):
        self.assertTrue(weighing_grade("Weighing_Material_A and Weighing_Material_B")["answer_pass"])
        self.assertFalse(weighing_grade("Weighing_Material_A only")["answer_pass"])

    def test_reference_and_incorrect_mapping(self):
        reference = REFERENCE.read_text(encoding="utf-8-sig")
        grade = io_mapping_grade(reference, reference)
        self.assertTrue(grade["answer_pass"], grade)
        self.assertEqual(len([k for k in grade["checks"] if k.startswith("physical:")]), 11)
        for old, new in (("%Q0.3.3", "%Q0.3.4"), ("BMXDDO1602", "BMXDDI3202K"),
                         ("%CH0.4.0", "%CH0.8.0")):
            self.assertFalse(io_mapping_grade(reference.replace(old, new), reference)["answer_pass"])
        self.assertFalse(io_mapping_grade("L0 L1 L2 Machine_running", reference)["answer_pass"])
        self.assertFalse(io_mapping_grade(reference.replace("UNMAPPED", "PHYSICAL"), reference)["answer_pass"])
        # A valid address elsewhere cannot rescue a wrong signal row.
        changed = reference.replace("%Q0.3.3", "%Q0.3.4") + "\n%Q0.3.3\n"
        self.assertFalse(io_mapping_grade(changed, reference)["answer_pass"])

    async def test_read_only_policy_and_full_application_scope(self):
        mcp = MCP({"documentation": False}, {}, None)
        mcp.instructions = ""
        mcp.tools = [{"name": name, "input_schema": {}} for name in
                    READ_TOOLS | EDIT_TOOLS | {"get_hardware", "export_xml", "list_data_types"}]
        mcp.call = AsyncMock(return_value=SimpleNamespace(model_dump=lambda **kwargs: {"is_error": False}))
        instructions, schemas = mcp.adapter("weighing")
        self.assertIn("M580", instructions)
        self.assertFalse(EDIT_TOOLS & {tool["name"] for tool in schemas})
        await mcp.dispatch("read_section", {"task": "MAST", "section": "Weighing_Material_A"}, schemas)
        mcp.call.assert_awaited_once()
        self.assertTrue((await mcp.dispatch("write_st_logic", {}, schemas))["is_error"])
        schedule = make_schedule(["A", "B"], 1, 1729, DEMO_PROMPTS)
        self.assertEqual(len(schedule), 4)
        self.assertEqual(task_fixture({"demo_project": "demo.stu"}, "weighing")[0], "demo.stu")

    async def test_evaluator_requires_source_and_unchanged_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            original = Path(temporary) / "original.stu"
            output = Path(temporary) / "copy.stu"
            original.write_bytes(b"demo")
            output.write_bytes(b"demo")
            manifest = {"demo_project": str(original)}
            mcp = SimpleNamespace(checked=AsyncMock())
            events = [{"kind": "mcp_call", "phase": "workflow", "tool": "read_section", "is_error": False}]
            answer = "Weighing_Material_A and Weighing_Material_B"
            grade = await evaluate(mcp, "weighing", manifest, output, answer, events)
            self.assertTrue(grade["success"])
            grade = await evaluate(mcp, "weighing", manifest, output, answer, [])
            self.assertFalse(grade["success"])
            output.write_bytes(b"changed")
            grade = await evaluate(mcp, "weighing", manifest, output, answer, events)
            self.assertFalse(grade["success"])
            self.assertEqual(grade["scope"], "fail")

    def test_equivalent_table_formats_and_grouped_flags(self):
        reference = REFERENCE.read_text(encoding="utf-8-sig")
        equivalent = reference.replace("BMXDDO1602", "BMX DDO 1602").replace("BMXAMI0410", "BMX AMI 0410").replace("BMXDDI3202K", "BMX DDI 3202K")
        lines = []
        for line in equivalent.splitlines():
            if line.startswith("| `"):
                row = line.split("|")
                if len(row) > 6 and row[5].strip().isdigit():
                    row[5] = " ch " + row[5].strip() + " "
                if row[1].strip() == "`L0`":
                    row[1] = " `L0` (RED LED) "
                line = "|".join(row)
            lines.append(line)
        equivalent = "\n".join(lines)
        self.assertTrue(io_mapping_grade(equivalent, reference)["answer_pass"])
        self.assertFalse(io_mapping_grade_v1(equivalent, reference)["answer_pass"])
        # Group every software signal in one explicitly flagged table row.
        kept = [line for line in equivalent.splitlines()
                if "UNMAPPED" not in line or not line.startswith("|")]
        names = [row[0] for row in table_rows(reference)
                 if len(row) >= 7 and row[5].startswith("unmapped")]
        grouped = "\n".join(kept) + "\n\n## Signals without a physical mapping\n\n| Group | Signals (all unlocated) |\n| --- | --- |\n| Software | " + ", ".join(names) + " |\n"
        self.assertTrue(io_mapping_grade(grouped, reference)["answer_pass"])
        self.assertFalse(io_mapping_grade(grouped.replace("%Q0.3.3", "%Q0.3.4"), reference)["answer_pass"])
        for name in ("L0", "Machine_running"):
            lines = []
            for line in reference.splitlines():
                if line.startswith("| `" + name + "`"):
                    row = line.split("|")
                    row[5] = " 15 "
                    line = "|".join(row)
                lines.append(line)
            self.assertFalse(io_mapping_grade("\n".join(lines), reference)["answer_pass"])
        invented = reference + "\n\n| Signal | Address | Status |\n| --- | --- | --- |\n| Start | %I0.2.0 | PHYSICAL |\n"
        self.assertFalse(io_mapping_grade(invented, reference)["answer_pass"])

    def test_io_regrade_preserves_original_and_checks_reference_and_response(self):
        reference = REFERENCE.read_text(encoding="utf-8-sig")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ref = root / "reference.md"
            ref.write_text(reference, encoding="utf-8")
            run = root / "run"
            case = {"case_id": "io_mapping-000-A", "task": "io_mapping"}
            attempt = run / case["case_id"] / "attempt-1"
            attempt.mkdir(parents=True)
            summary = {**case, "fingerprint": "same", "status": "completed", "success": False,
                       "validation": {"scope": "pass", "obtained_source_through_mcp": True,
                                      "rubric": "demo-io-mapping-1"}}
            write_json(attempt / "summary.json", summary)
            (attempt / "final-response.txt").write_text(reference, encoding="utf-8")
            write_json(run / "plan.json", {"fingerprint": "same", "schedule": [case],
                       "snapshot": {"config": {"io_mapping_reference": str(ref)},
                                    "demo_inputs": {"io_mapping_reference": digest(ref.read_bytes())}}})
            regrade_inspection(root, "run", "io_mapping")
            row = regraded_row(attempt / "summary.json", "demo-io-mapping-2")
            self.assertTrue(row["success"])
            self.assertEqual(read_json(attempt / "summary.json"), summary)
            ref.write_text(reference + "changed", encoding="utf-8")
            with self.assertRaises(ValueError):
                regrade_inspection(root, "run", "io_mapping")
            (attempt / "final-response.txt").write_text("changed", encoding="utf-8")
            with self.assertRaises(ValueError):
                regraded_row(attempt / "summary.json", "demo-io-mapping-2")

    def test_read_only_cases_are_excluded_from_build_denominators(self):
        rows = [{"task": task, "status": "completed", "success": True,
                 "validation": {"compile_pass": True if task == "alarms" else None}}
                for task in ("inspect", "weighing", "io_mapping", "alarms")]
        data = aggregate(rows)
        self.assertEqual(data["build"]["n"], 1)
        self.assertEqual(data["build"]["pass"], 1)
        self.assertEqual(data["static_behavior"]["n"], 1)
