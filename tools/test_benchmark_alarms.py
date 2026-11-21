"""Demo-derived alarm transitions: independent examples and negative controls."""
from pathlib import Path
import unittest

from control_expert_mcp.benchmark.alarms import Parser, execute, tokens
from control_expert_mcp.benchmark.tasks import alarm_fixture, alarm_source, declarations, source, static_grade

FIXTURE = Path(__file__).resolve().parents[1] / "tools/lang_refs/ST_2_Feeder.xml"
BOOLEAN_FORM = """
Temp_fault_1 := Start_process AND
    ((Cmeasured_temp <= 200.0) OR (Temp_fault_1 AND (Cmeasured_temp < 205.0)));
Temp_fault_2 := Start_process AND
    ((Cmeasured_temp >= 400.0) OR (Temp_fault_2 AND (Cmeasured_temp > 395.0)));
"""


class AlarmTests(unittest.TestCase):
    def setUp(self):
        self.xml = FIXTURE.read_text(encoding="utf-8-sig")
        self.baseline = source(self.xml)

    def grade(self, suffix):
        return static_grade("alarms", self.baseline, self.baseline + "\n" + suffix)

    def test_fixture_is_separate_and_preserves_original_source(self):
        extended = alarm_fixture(self.xml)
        self.assertEqual(source(extended), self.baseline)
        self.assertEqual(len(declarations(self.xml)), 15)
        self.assertEqual(len(declarations(extended)), 18)
        with self.assertRaises(ValueError):
            alarm_fixture(extended)

    def test_equivalent_if_and_boolean_transitions(self):
        for candidate in (alarm_source(self.baseline), self.baseline + BOOLEAN_FORM):
            with self.subTest(candidate=candidate):
                result = static_grade("alarms", self.baseline, candidate)
                self.assertEqual(result["scope"], "pass")
                self.assertEqual(result["static_behavior"], "pass")
                self.assertEqual(result["runtime_behavior"], "unverified")
                self.assertGreaterEqual(result["partition_cases"], 112)

    def test_wrong_boundaries_missing_gating_and_state_fail(self):
        for candidate in (
            BOOLEAN_FORM.replace("<= 200.0", "< 200.0"),
            BOOLEAN_FORM.replace(">= 400.0", "> 400.0"),
            BOOLEAN_FORM.replace("< 205.0", "<= 205.0"),
            BOOLEAN_FORM.replace("> 395.0", ">= 395.0"),
            BOOLEAN_FORM.replace("Start_process AND", "TRUE AND"),
            BOOLEAN_FORM.replace("Temp_fault_1 AND", "FALSE AND"),
            BOOLEAN_FORM.replace("Temp_fault_2 AND", "FALSE AND"),
            BOOLEAN_FORM.replace("<= 200.0", "<= 201.0"),
            BOOLEAN_FORM + "IF Cmeasured_temp = 12345 THEN Temp_fault_1 := TRUE; END_IF;",
        ):
            with self.subTest(candidate=candidate):
                result = self.grade(candidate)
                self.assertEqual(result["static_behavior"], "unverified")
                self.assertIn("counterexample", result)

    def test_scope_and_unsupported_syntax_stay_unverified(self):
        for candidate in (
            BOOLEAN_FORM + "Sec := TRUE;", BOOLEAN_FORM + "Temp_fault_1 := ABS(Cmeasured_temp) > 1;",
            BOOLEAN_FORM + "Temp_fault_1 := Cmeasured_temp + 1 > 200;",
            BOOLEAN_FORM + "Temp_fault_1 := TRUE XOR FALSE;",
            BOOLEAN_FORM + "Temp_fault_1 := TRUE @ FALSE;", BOOLEAN_FORM + "ELSE",
            BOOLEAN_FORM + "Temp_fault_1 := 200;", BOOLEAN_FORM + "IF TRUE THEN",
        ):
            with self.subTest(candidate=candidate):
                self.assertEqual(self.grade(candidate)["static_behavior"], "unverified")
        modified = alarm_source(self.baseline).replace("feeder_state=2", "feeder_state=3")
        self.assertEqual(static_grade("alarms", self.baseline, modified)["scope"], "unverified")

    def test_hysteresis_scan_sequence_and_disable_reset(self):
        parser = Parser(tokens(BOOLEAN_FORM))
        program = parser.block()
        state = {"start_process": True, "temp_fault_1": False, "temp_fault_2": False}
        # Warmup, low hysteresis, high hysteresis, then disable/re-enable inside band.
        for measured, enabled, expected in (
            (199, True, (True, False)), (200, True, (True, False)),
            (204, True, (True, False)), (205, True, (False, False)),
            (204, True, (False, False)), (399, True, (False, False)),
            (400, True, (False, True)), (396, True, (False, True)),
            (395, True, (False, False)), (396, True, (False, False)),
            (400, True, (False, True)), (398, False, (False, False)),
            (398, True, (False, False)), (-32768, True, (True, False)),
            (32767, True, (False, True)),
        ):
            state.update(cmeasured_temp=float(measured), start_process=enabled)
            execute(program, state)
            self.assertEqual((state["temp_fault_1"], state["temp_fault_2"]), expected)


if __name__ == "__main__":
    unittest.main()
