"""Full-demo grading and tool policy controls; no CE or provider needed."""
from pathlib import Path
import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock

from control_expert_mcp.benchmark.demo import io_mapping_grade, weighing_grade, DEMO_PROMPTS, table_rows
from control_expert_mcp.benchmark.report import aggregate
from control_expert_mcp.benchmark.core import digest, read_json, write_json
from control_expert_mcp.benchmark.regrade import regrade_inspection, regraded_row
from control_expert_mcp.benchmark.runner import make_schedule, task_fixture, evaluate
from control_expert_mcp.benchmark.transport import MCP, READ_TOOLS, EDIT_TOOLS

REFERENCE = Path(__file__).resolve().parents[1] / "samples/demo_ControlExpert_M580_io_mapping.md"


class DemoTests(unittest.IsolatedAsyncioTestCase):
    def test_mapping_signal_column_and_spelled_out_channel_counts(self):
        reference = REFERENCE.read_text(encoding="utf-8-sig")
        kept = []
        names = []
        for line in reference.splitlines():
            rows = table_rows(line)
            if rows and len(rows[0]) >= 7 and rows[0][5].startswith('unmapped'):
                names.append(rows[0][0])
                continue
            if rows and len(rows[0]) >= 7 and rows[0][5] == 'physical device ddt':
                cells = line.split('|')
                cells[5] = {'ddi3202k_0_5': '32 digital input channels',
                            'ddo1602_0_6': '16 digital output channels',
                            'ami0410_0_7': '4 analog input channels'}[rows[0][0]]
                line = '|'.join(cells)
            kept.append(line)
        # Remove separate hardware/leaf tables so they cannot rescue bad counts.
        start = kept.index('## Signals with physical mappings')
        end = kept.index('## Device-DDT channel fields')
        physical = '\n'.join(kept[start:end])
        memory = '\nCurrent_position (%MW10) and recipe (%MW100) are internal memory.\n'
        for header in ('Signal(s) without physical mapping', 'Signals without physical mapping',
                       'Application signal', 'Unmapped signals'):
            with self.subTest(header=header):
                answer = (physical + memory + '\n## Unmapped signals\n\n| Signal group | ' + header
                          + ' |\n|---|---|\n| Process | ' + ', '.join(names) + ' |\n')
                grade = io_mapping_grade(answer, reference)
                self.assertEqual(grade['rubric'], 'demo-io-mapping-4')
                self.assertTrue(grade['answer_pass'], grade['missing'])
                for old, new, key in (
                    ('32 digital input channels', '31 digital input channels', 'physical:ddi3202k_0_5'),
                    ('32 digital input channels', '32 digital output channels', 'physical:ddi3202k_0_5'),
                    ('16 digital output channels', '16 digital input channels', 'physical:ddo1602_0_6'),
                    ('4 analog input channels', '4 digital input channels', 'physical:ami0410_0_7'),
                    ('belt_running', 'belt_motor', 'unmapped:belt_running'),
                    ('robot_one', 'unrelated_robot', 'robot_unmapped'),
                ):
                    wrong = io_mapping_grade(answer.replace(old, new), reference)
                    self.assertFalse(wrong['answer_pass'])
                    self.assertIn(key, wrong['missing'])
                hardware = ('\n| Slot | Module | Channels configured | Application signal aliases found |\n'
                            '|---|---|---|---|\n'
                            '| 5 | BMXDDI3202K | 32 DI | Module DDT DDI3202K_0_5 |\n'
                            '| 6 | BMXDDO1602 | 16 DO | Module DDT DDO1602_0_6 |\n'
                            '| 7 | BMXAMI0410 | 4 AI | Module DDT AMI0410_0_7 |\n')
                self.assertTrue(io_mapping_grade(answer + hardware, reference)['answer_pass'])

    def test_mapping_prose_memory_and_direction_channel_labels(self):
        reference = REFERENCE.read_text(encoding="utf-8-sig")
        lines = []
        for line in reference.splitlines():
            row = table_rows(line) if line.startswith('|') else []
            if row and row[0][0] in {'current_position', 'recipe'}:
                continue
            if row and len(row[0]) >= 7 and row[0][5].startswith('physical') and row[0][4].isdigit():
                cells = line.split('|')
                cells[5] = ' Output ' + row[0][4] if row[0][2].startswith('%q') else ' Analog input ' + row[0][4]
                line = '|'.join(cells)
            lines.append(line)
        answer = '\n'.join(lines) + '\nCurrent_position (%MW10) and recipe (%MW100) are memory locations, not physical I/O.'
        grade = io_mapping_grade(answer, reference)
        self.assertTrue(grade['answer_pass'], grade['missing'])
        self.assertEqual(grade['coverage']['matched'], grade['coverage']['required'])
        self.assertFalse(io_mapping_grade(answer.replace('%MW10)', '%MW11)'), reference)['answer_pass'])

    def test_mapping_conflicts_cannot_be_rescued_by_correct_rows(self):
        reference = REFERENCE.read_text(encoding="utf-8-sig")
        for bad in ('%Q0.3.30 | BMXDDO1602 | 3', '%Q0.3.3 | BMXDDO1602 | 15',
                    '%Q0.3.3 | slot 6 BMXDDO1602 | 3', '%Q0.3.3 | BMXDDI3202K | 3',
                    '%Q0.3.3 | BMXDDO16020 | 3'):
            with self.subTest(bad=bad):
                answer = reference + '\n\n| Signal | Address | Module | Channel |\n|---|---|---|---|\n| Machine_running | ' + bad + ' |\n'
                grade = io_mapping_grade(answer, reference)
                self.assertFalse(grade['answer_pass'])
                self.assertTrue('physical:machine_running' in grade['incorrect']
                                or 'physical:machine_running' in grade['missing'])

    def test_mapping_explicit_hardware_join_and_missing_diagnostics(self):
        reference = REFERENCE.read_text(encoding="utf-8-sig")
        lines = []
        for line in reference.splitlines():
            row = table_rows(line) if line.startswith('|') else []
            if row and len(row[0]) >= 7 and row[0][5] == 'physical device ddt':
                cells = line.split('|'); cells[5] = ' module image '; line = '|'.join(cells)
            lines.append(line)
        answer = '\n'.join(lines)
        self.assertTrue(io_mapping_grade(answer, reference)['answer_pass'])
        self.assertTrue(io_mapping_grade(reference.replace('0–31', '0 to 31'), reference)['answer_pass'])
        # A different module slot cannot supply the missing device channel facts.
        answer = answer.replace('| 5 | BMXDDI3202K', '| 9 | BMXDDI3202K')
        grade = io_mapping_grade(answer, reference)
        self.assertFalse(grade['answer_pass'])
        self.assertIn('physical:ddi3202k_0_5', grade['missing'])
        self.assertEqual(grade['facts']['physical:ddi3202k_0_5']['status'], 'missing')

    def test_mapping_omissions_remain_failures(self):
        reference = REFERENCE.read_text(encoding="utf-8-sig")
        answer = reference.replace('Belt_running', 'Unrelated_signal')
        grade = io_mapping_grade(answer, reference)
        self.assertFalse(grade['answer_pass'])
        self.assertIn('unmapped:belt_running', grade['missing'])
        self.assertNotIn('unmapped:belt_running', grade['incorrect'])

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
            row = regraded_row(attempt / "summary.json", "demo-io-mapping-4")
            self.assertTrue(row["success"])
            self.assertEqual(read_json(attempt / "summary.json"), summary)
            ref.write_text(reference + "changed", encoding="utf-8")
            with self.assertRaises(ValueError):
                regrade_inspection(root, "run", "io_mapping")
            (attempt / "final-response.txt").write_text("changed", encoding="utf-8")
            with self.assertRaises(ValueError):
                regraded_row(attempt / "summary.json", "demo-io-mapping-4")

    def test_read_only_cases_are_excluded_from_build_denominators(self):
        rows = [{"task": task, "status": "completed", "success": True,
                 "validation": {"compile_pass": True if task == "alarms" else None}}
                for task in ("inspect", "weighing", "io_mapping", "alarms")]
        data = aggregate(rows)
        self.assertEqual(data["build"]["n"], 1)
        self.assertEqual(data["build"]["pass"], 1)
        self.assertEqual(data["static_behavior"]["n"], 1)
