"""Git-safe archive privacy, provenance and explicit regrade regression tests."""
import json
from importlib.util import find_spec
from pathlib import Path
import tempfile
import unittest

from control_expert_mcp.benchmark.core import digest, read_json, write_json
from control_expert_mcp.benchmark.archive import archive_run
from control_expert_mcp.benchmark.regrade import regrade_inspection, regraded_row
from test_benchmark import GOLD
from control_expert_mcp.benchmark.tasks import RUBRIC_VERSION
from control_expert_mcp.benchmark.plot import chart_rows, visualize_archive, mapping_correctness
from control_expert_mcp.benchmark.report import aggregate


class ArchiveTests(unittest.TestCase):
    def test_explicit_suite_row_requires_complete_unique_cases(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            identities = [("A", "inspect", 0), ("B", "inspect", 0),
                          ("SIMULATOR", "simulator_counter", 0)]
            for index, (condition, task, repeat) in enumerate(identities):
                case = {"case_id": str(index), "task": task, "condition": condition,
                        "repeat": repeat, "success": True, "status": "completed"}
                record = {"run_id": str(index), "model": {"id": "model"}, "provider": "deepseek",
                          "cases": [case], "servers": {condition: {"source": {"revision": "same"}}},
                          "conditions": {condition: {"overall": aggregate([case])}}, "rubric_version": "test"}
                path = root / str(index) / "record.json"
                write_json(path, record)
                write_json(path.parent / "checksums.json", {"record.json": digest(path.read_bytes())})
            group = {"id": "latest", "label": "Latest DeepSeek A+B+simulator",
                     "run_ids": ["0", "1", "2"], "expected_cases": identities}
            write_json(root / "overview.groups.json", {"groups": [group]})
            rows, inputs = chart_rows(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["overall"]["accepted"]["pass"], 3)
            self.assertEqual(rows[0]["tasks"]["inspect"]["cases"], 2)
            self.assertEqual(rows[0]["tasks"]["simulator_counter"]["cases"], 1)
            self.assertEqual(len(rows[0]["members"]), 3)
            self.assertIn("overview.groups.json", inputs)
            group["expected_cases"] = identities[:-1]
            write_json(root / "overview.groups.json", {"groups": [group]})
            with self.assertRaisesRegex(ValueError, "missing or duplicate"):
                chart_rows(root)

    def test_mapping_correctness_reports_partial_and_unknown_answers(self):
        def case(matched, required=29):
            return {'task': 'io_mapping', 'validation': {'checks': {
                str(i): i < matched for i in range(required)}}}
        for matched in (22, 23, 29):
            score = mapping_correctness([case(matched)])
            self.assertAlmostEqual(score['fraction'], matched / 29)
            self.assertEqual((score['matched'], score['required']), (matched, 29))
        score = mapping_correctness([case(23), case(22), {'task': 'io_mapping'},
                                     {'task': 'inspect', 'validation': {'checks': {'x': True}}}])
        self.assertEqual((score['matched'], score['required']), (45, 58))
        self.assertEqual((score['known_n'], score['unknown_n']), (2, 1))
        self.assertIsNone(mapping_correctness([{'task': 'io_mapping'}])['fraction'])

    def test_plot_data_keeps_models_and_versions_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index in (1, 2):
                case = {"case_id": "inspect-0-A", "attempt_id": "attempt-1", "task": "inspect", "condition": "A",
                        "status": "completed", "success": True, "workflow_seconds": None if index == 1 else index,
                        "validation": {"rubric": "synthetic", "answer_pass": True},
                        "usage": {"tokens": {"total_tokens": None if index == 1 else index * 10}}}
                record = {"run_id": f"run-{index}", "model": {"id": f"model-{index}"}, "provider": "synthetic",
                          "cases": [case], "servers": {"A": {"source": {"revision": str(index) * 40}}},
                          "conditions": {"A": {"overall": aggregate([case])}}, "rubric_version": "synthetic"}
                path = root / f"run-{index}" / "record.json"
                write_json(path, record)
                write_json(path.parent / "checksums.json", {"record.json": digest(path.read_bytes())})
            rows, inputs = chart_rows(root)
            self.assertEqual(len(rows), 2)
            self.assertEqual(len({row["model"] for row in rows}), 2)
            self.assertEqual(len({row["source"] for row in rows}), 2)
            self.assertEqual(len(inputs), 2)
            if find_spec("matplotlib"):
                output = visualize_archive(root, root / "overview.png")
                self.assertTrue(output.read_bytes().startswith(b"\x89PNG"))
                manifest = read_json(output.with_suffix(".metadata.json"))
                self.assertEqual(manifest["inputs"], inputs)
                self.assertEqual(manifest["image_sha256"], digest(output.read_bytes()))
                self.assertEqual(len(manifest["rows"]), 2)

    def test_committed_image_matches_archive(self):
        root = Path(__file__).resolve().parents[1] / "benchmarks" / "archive"
        manifest = root / "overview.metadata.json"
        if not manifest.exists():
            self.skipTest("No committed archive image in this source distribution")
        value = read_json(manifest)
        self.assertEqual(digest((root / "overview.png").read_bytes()), value["image_sha256"])
        for relative, checksum in value["inputs"].items():
            self.assertEqual(digest((root / relative).read_bytes()), checksum)

    def test_allowlist_and_immutable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = {"run_id": "run", "fingerprint": "same", "seed": 1,
                    "schedule": [{"case_id": "inspect-0-A", "task": "inspect", "repeat": 0, "condition": "A"}],
                    "snapshot": {"config": {"model": {"id": "synthetic", "identity": "alias"},
                        "provider": {"name": "deepseek", "api_key_file": "PRIVATE_PATH"}, "cpu": {},
                        "conditions": {"A": {"documentation": False}}}, "servers": {"A": {"environment": {"PRIVATE_ENV": "SECRET_VALUE"}}},
                        "machine": {"hostname": "PRIVATE_HOST"}, "harness": {"revision": "abc", "root": "PRIVATE_ROOT", "dirty": True},
                        "dependencies": {}, "fixture_sha256": "fixture", "rubric_version": "test", "prompts": {"inspect": "PRIVATE_PROMPT"}, "orientation": "PRIVATE_ORIENTATION"}}
            write_json(root / "results/run/plan.json", plan)
            summary = {"case_id": "inspect-0-A", "task": "inspect", "repeat": 0, "condition": "A", "fingerprint": "same",
                       "status": "completed", "success": True, "durable_completed": True, "final_response": "PRIVATE_RESPONSE",
                       "ce_status": {"installation_path": "PRIVATE_INSTALL"}, "validation": {"success": True, "answer_pass": True}}
            summary_path = root / "results/run/inspect-0-A/attempt-1/summary.json"
            write_json(summary_path, summary)
            archive = archive_run(root / "results", "run", root / "archive")
            serialized = (archive / "record.json").read_text()
            for word in ("PRIVATE_", "SECRET_VALUE", "api_key_file", "final_response", "installation_path"):
                self.assertNotIn(word, serialized)
            self.assertEqual(archive_run(root / "results", "run", root / "archive"), archive)
            response = summary_path.parent / "final-response.txt"
            response.write_text("saved answer", encoding="utf-8")
            original_record = (archive / 'record.json').read_bytes()
            for rubric in ("feeder-2", "feeder-3"):
                write_json(root / "results/run/regrades" / rubric / "inspect-0-A/attempt-1.json",
                           {"rubric": rubric, "case_id": "inspect-0-A", "attempt_id": "attempt-1",
                            "summary_sha256": digest(summary_path.read_bytes()),
                            "response_sha256": digest(response.read_bytes()),
                            "success": rubric != 'feeder-3',
                            "validation": {"answer_pass": rubric != 'feeder-3'}})
            selected = archive_run(root / "results", "run", root / "selected", rubric="feeder-3")
            self.assertEqual([g['rubric'] for g in read_json(selected / 'record.json')['inspection_regrades']],
                             ['feeder-3'])
            snapshot = archive_run(root / 'results', 'run', root / 'archive', rubric='feeder-3')
            self.assertNotEqual(snapshot, archive)
            self.assertEqual((archive / 'record.json').read_bytes(), original_record)
            latest, _ = chart_rows(root / 'archive')
            self.assertEqual(len(latest), 1)
            self.assertEqual(latest[0]['overall']['accepted']['pass'], 0)
            originals, _ = chart_rows(root / 'archive', scoring='original')
            self.assertEqual(originals[0]['overall']['accepted']['pass'], 1)
            with self.assertRaisesRegex(ValueError, "No saved regrades"):
                archive_run(root / "results", "run", root / "missing", rubric="absent")
            summary["success"] = False
            write_json(summary_path, summary)
            with self.assertRaises(ValueError):
                archive_run(root / "results", "run", root / "archive")
            write_json(summary_path, {**summary, "success": True})
            (archive / "report.md").write_text("tampered", encoding="utf-8")
            with self.assertRaises(ValueError):
                archive_run(root / "results", "run", root / "archive")

    def test_regrade_preserves_original_and_checks_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "results" / "run"
            case = {"case_id": "inspect-000-A", "task": "inspect", "repeat": 0, "condition": "A"}
            write_json(run / "plan.json", {"fingerprint": "original", "schedule": [case]})
            path = run / case["case_id"] / "attempt-one" / "summary.json"
            original = {**case, "fingerprint": "original", "status": "completed", "success": False,
                        "validation": {"rubric": "feeder-1", "scope": "pass", "obtained_source_through_mcp": True}}
            write_json(path, original)
            answer = {**GOLD, "initialization_expression": "Feeder_state := material_a_value + material_b_value;",
                      "temperature": {**GOLD["temperature"], "conversion": "CMeasured_temp := INT_TO_REAL(Measured_temp)"}}
            (path.parent / "final-response.txt").write_text(json.dumps(answer), encoding="utf-8")
            before = path.read_bytes()
            regrade_inspection(root / "results", "run")
            self.assertEqual(before, path.read_bytes())
            self.assertTrue(regraded_row(path, RUBRIC_VERSION)["success"])
            self.assertFalse(read_json(path)["success"])
            (path.parent / "final-response.txt").write_text("changed", encoding="utf-8")
            with self.assertRaises(ValueError):
                regraded_row(path, RUBRIC_VERSION)


if __name__ == "__main__":
    unittest.main()
