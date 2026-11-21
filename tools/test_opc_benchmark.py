"""No model requests or PLC access: live OPC benchmark policy/scoring tests."""

import unittest
from control_expert_mcp.benchmark.opc import cases, expected, grade, LiveMCP
from control_expert_mcp.benchmark.core import environment
from control_expert_mcp.benchmark.report import aggregate


class GradingTests(unittest.TestCase):
    def setUp(self):
        self.case = cases(1, 1729, 'positive')[0]
        self.observed = {'values': expected(self.case['inputs'])}
        self.calls = [
            {'tool': 'opc_write_tags', 'value': {'written': self.case['inputs']}},
            {'tool': 'opc_read_tags', 'value': self.observed},
        ]

    def test_independent_values_and_actual_model_read_write_are_all_required(self):
        self.assertTrue(grade(self.case, self.calls, self.observed, True, 'completed')['success'])
        self.assertFalse(grade(self.case, [], self.observed, True, 'completed')['success'])
        self.assertFalse(grade(self.case, list(reversed(self.calls)), self.observed, True, 'completed')['success'])
        self.assertFalse(grade(self.case, self.calls, {'values': {}}, True, 'completed')['success'])
        self.assertFalse(grade(self.case, self.calls, self.observed, False, 'completed')['success'])
        self.assertFalse(grade(self.case, self.calls, self.observed, True, 'incomplete')['success'])
        self.assertFalse(grade(self.case, self.calls + [{'tool': 'x', 'policy_violation': True}],
                               self.observed, True, 'completed')['success'])

    def test_cases_repeat_deterministically_and_include_disabled_negative_paths(self):
        self.assertEqual(cases(2, 1729), cases(2, 1729))
        self.assertEqual(len(cases(2, 1729)), 6)
        for case in cases(1, 1729):
            values = expected(case['inputs'])
            if case['task'] == 'opc_disabled':
                self.assertEqual(values['OPCBench_Output'], 0.0)
                self.assertIs(values['OPCBench_Positive'], False)
            elif case['task'] == 'opc_negative':
                self.assertLess(values['OPCBench_Output'], 0)

    def test_live_environment_is_explicit_and_does_not_change_offline_policy(self):
        condition = {'env': {'CE_MCP_ENABLE_ONLINE': '1'}}
        self.assertEqual(environment(condition)['CE_MCP_ENABLE_ONLINE'], '0')
        mcp = LiveMCP(condition, {}, None, 'Demo')
        self.assertEqual(mcp.server_environment()['CE_MCP_ENABLE_ONLINE'], '1')

    def test_live_cases_are_not_reported_as_failed_compilation(self):
        report = aggregate([{'task': 'opc_positive', 'status': 'completed', 'success': True,
                             'validation': {'runtime_behavior': 'pass'}}])
        self.assertEqual(report['build']['n'], 0)
        self.assertEqual(report['static_behavior']['n'], 0)
        self.assertEqual(report['runtime_behavior']['pass'], 1)


class DispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_output_and_other_device_writes_are_blocked_before_transport(self):
        mcp = LiveMCP({}, {}, None, 'Demo')
        schema = [{'name': 'opc_write_tags'}]
        for tag in ('OPCBench_Output', 'Other!OPCBench_Input', 'Start'):
            result = await mcp.dispatch('opc_write_tags', {'values': {tag: 1}}, schema)
            self.assertTrue(result['is_error'])
        self.assertEqual(len(mcp.model_calls), 3)
        self.assertTrue(all(call['policy_violation'] for call in mcp.model_calls))


if __name__ == '__main__':
    unittest.main()
