"""Diagnostic parsing and build capture checks, without a Control Expert session."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from control_expert_mcp.bridge import ControlExpertBridge
from control_expert_mcp.diagnostics import diagnostic_capture, parse_diagnostics


def snapshot(text, tab="Build"):
    return {"available": text is not None, "output": text, "tab": tab, "read_errors": []}


class DiagnosticTests(unittest.TestCase):
    def test_known_formats_and_unrecognized_lines(self):
        line = '{FBD_Demo : [MAST]} : (l: 12, c: 7) E1189 converter error: bad pin'
        rows = parse_diagnostics(line + '\nWarning: check value\n0 error(s), 0 warning(s)\n'
                                 'localized message with no known code\nE1203 invalid assignment')
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0], {"severity": "error", "code": "E1189", "task": "MAST",
                                  "section": "FBD_Demo", "location": {"line": 12, "column": 7},
                                  "message": line})
        self.assertIsNone(rows[1]["code"])
        self.assertIsNone(rows[1]["location"])
        self.assertIsNone(rows[2]["section"])
        scoped = parse_diagnostics('{Section1 <DFB> : [Heating]} E1203 invalid\n'
                                   '{Action : [MAST - Robot]} E1203 invalid')
        self.assertTrue(all(row["task"] is None and row["section"] is None for row in scoped))

    def test_freshness_missing_empty_unchanged_replaced_and_appended(self):
        old = snapshot("E1203 old\n")
        result = diagnostic_capture(old, snapshot(old["output"] + "Warning: new\n"), "build")
        self.assertEqual(len(result["diagnostics"]), 1)
        self.assertEqual(result["output"], "E1203 old\nWarning: new\n")
        self.assertEqual(result["diagnostics_output"], "Warning: new\n")
        self.assertEqual(result["diagnostics_capture"]["scope"], "appended")
        self.assertEqual(result["diagnostics_capture"]["attribution"], "unverified")
        self.assertEqual(diagnostic_capture(old, old, "build")["diagnostics_capture"]["freshness"], "unchanged")
        missing = diagnostic_capture(old, snapshot(None), "build")
        self.assertFalse(missing["diagnostics_available"])
        self.assertIsNone(missing["output"])
        empty = diagnostic_capture(old, snapshot(""), "analyze")
        self.assertTrue(empty["diagnostics_available"])
        self.assertEqual(empty["diagnostics"], [])
        self.assertEqual(empty["diagnostics_capture"]["freshness"], "changed")
        self.assertEqual(diagnostic_capture(snapshot(None), old, "build")["diagnostics_capture"]["freshness"], "unknown")
        summary = diagnostic_capture(old, snapshot('Process succeeded  : 0 Error(s) , 1 Warning(s)'), "build")
        self.assertEqual(summary["diagnostics"], [])
        self.assertEqual(summary["diagnostics_summary"]["warnings"], 1)

    def test_capture_never_falls_back_to_unrelated_tabs(self):
        bridge = object.__new__(ControlExpertBridge)
        bridge._ensure_app = Mock(return_value=object())
        bridge._wrap = lambda value: value
        calls = []
        def get_prop(obj, name, *args):
            if name == "OutputWindow":
                return object()
            calls.append(args[0])
            raise RuntimeError("unavailable")
        bridge._get_prop = get_prop
        result = bridge._do_capture_build_output()
        self.assertFalse(result["available"])
        self.assertEqual(calls, ["Build", "build"])

    def test_build_analyze_and_incremental_fallback(self):
        for operation in ("build", "analyze"):
            with self.subTest(operation=operation):
                bridge = object.__new__(ControlExpertBridge)
                project = SimpleNamespace(InfoBuildState=0, Build=Mock(), BuildAll=Mock(), Analyze=Mock())
                bridge._project = Mock(return_value=project)
                bridge._do_capture_build_output = Mock(side_effect=[snapshot(""), snapshot("E1203 bad")])
                result = bridge._do_build(False) if operation == "build" else bridge._do_analyze()
                self.assertEqual(result["diagnostics"][0]["code"], "E1203")
                self.assertEqual(result["diagnostics_capture"]["operation"], operation)
        bridge._do_capture_build_output = Mock(side_effect=[snapshot(None), snapshot(None), snapshot(None)])
        project.Build.side_effect = RuntimeError("generic failure")
        result = bridge._do_build(False)
        self.assertIn("error", result)
        self.assertFalse(result["diagnostics_available"])
        project.BuildAll.assert_not_called()
        bridge._do_capture_build_output = Mock(side_effect=[snapshot("Build changes function not available")] * 3)
        bridge._do_build(False)
        project.BuildAll.assert_not_called()
        bridge._do_capture_build_output = Mock(side_effect=[snapshot(""), snapshot("Build changes function not available"),
                                                           snapshot("Process succeeded")])
        result = bridge._do_build(False)
        self.assertIn("note", result)
        self.assertNotIn("error", result)
        project.BuildAll.assert_called_once()


if __name__ == "__main__":
    unittest.main()
