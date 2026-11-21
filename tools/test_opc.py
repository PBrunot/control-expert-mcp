"""OPC quality, browsing, worker failure and session policy checks; no PLC access."""

import queue
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from control_expert_mcp.live_access import LiveAccessPolicy
from control_expert_mcp.opc import OpcClient, OpcError
from control_expert_mcp.opc_worker import AutomationSession


class LivePolicyTests(unittest.TestCase):
    def test_opt_in_is_not_consent_and_opc_confirmation_is_required(self):
        policy = LiveAccessPolicy(True)
        with self.assertRaisesRegex(ValueError, 'configure_live_access'):
            with policy.guard('opc_connect'):
                self.fail('must not connect')
        with self.assertRaisesRegex(ValueError, 'alias'):
            policy.validate(True)
        with self.assertRaisesRegex(ValueError, 'confirm OFS'):
            policy.validate(True, 'opc', 'Demo', False, True)
        with self.assertRaisesRegex(ValueError, 'CE_MCP_ENABLE_ONLINE'):
            LiveAccessPolicy(False).validate(True, 'opc', 'Demo')

    def test_read_only_protocol_and_revocation(self):
        policy = LiveAccessPolicy(True)
        policy.config = policy.validate(True, 'opc', 'Demo')
        policy.configured = True
        with policy.guard('opc_read_tags'):
            pass
        for name in ('write_tags', 'modbus_connect', 'opc_write_tags', 'plc_transfer', 'plc_command'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                with policy.guard(name):
                    self.fail('must remain blocked')
        policy.config = policy.validate(True, 'opc', 'Demo', True, True)
        with policy.guard('opc_write_tags'):
            pass
        policy.config = policy.validate(False)
        for name in ('opc_disconnect', 'modbus_disconnect', 'plc_disconnect', 'opc_status'):
            with policy.guard(name):
                pass
        with self.assertRaises(ValueError):
            with policy.guard('opc_read_tags'):
                self.fail('revoked')


class AutomationTests(unittest.TestCase):
    def test_mixed_quality_missing_and_other_alias(self):
        session = AutomationSession()
        session.alias = 'Demo'
        items = {
            'Demo!good': SimpleNamespace(Read=lambda source: (42, 192, None), CanonicalDataType=2, AccessRights=3),
            'Demo!bad': SimpleNamespace(Read=lambda source: (99, 0, None), CanonicalDataType=2, AccessRights=3),
            'Demo!uncertain': SimpleNamespace(Read=lambda source: (98, 64, None), CanonicalDataType=2, AccessRights=3),
        }
        session.group = SimpleNamespace(OPCItems=SimpleNamespace(AddItem=lambda name, handle: items.get(name)))
        result = session.read(['good', 'bad', 'uncertain', 'missing', 'Other!good'])
        self.assertEqual(result['values'], {'good': 42})
        self.assertEqual(set(result['errors']), {'bad', 'uncertain', 'missing', 'Other!good'})
        self.assertEqual(result['samples']['bad']['value'], 99)
        self.assertFalse(result['samples']['uncertain']['good'])
        self.assertNotIn('Demo!missing', session.items)

    def test_browser_refresh_and_page_boundaries(self):
        class Browser:
            rows = []
            def MoveToRoot(self): pass
            def MoveDown(self, branch): pass
            def ShowBranches(self): self.rows = ['nested']
            def ShowLeafs(self, flat): self.rows = ['a', 'b', 'c']
            @property
            def Count(self): return len(self.rows)
            def Item(self, index): return self.rows[index - 1]
            def GetItemID(self, name): return 'Demo!' + name
            def __iter__(self): raise AssertionError('stale enumerator must not be used')
        session = AutomationSession()
        session.server = SimpleNamespace(CreateBrowser=Browser)
        first = session.browse(['Demo'], False, 0, 2)
        second = session.browse(['Demo'], False, first['next_offset'], 2)
        self.assertEqual(first['entries'], [{'kind': 'branch', 'name': 'nested'},
                                         {'kind': 'item', 'name': 'a', 'item_id': 'Demo!a'}])
        self.assertEqual([entry['name'] for entry in second['entries']], ['b', 'c'])
        self.assertIsNone(second['next_offset'])
        self.assertEqual(session.browse([], False, 20, 2)['entries'], [])

    def test_write_types_and_ranges_are_checked_before_com_write(self):
        session = AutomationSession()
        session.alias = 'Demo'
        boolean = SimpleNamespace(CanonicalDataType=11, AccessRights=3, Write=Mock())
        integer = SimpleNamespace(CanonicalDataType=2, AccessRights=3, Write=Mock())
        real = SimpleNamespace(CanonicalDataType=4, AccessRights=3, Write=Mock())
        session.group = object()
        session.items = {'Demo!bool': boolean, 'Demo!int': integer, 'Demo!real': real}
        for values in ({'bool': 'false'}, {'int': 32768}, {'int': True}, {'real': float('nan')}):
            result = session.write(values)
            self.assertFalse(result['written'])
            self.assertTrue(result['errors'])
        boolean.Write.assert_not_called()
        integer.Write.assert_not_called()
        real.Write.assert_not_called()
        result = session.write({'bool': False, 'int': -123, 'real': 1.25})
        self.assertFalse(result['errors'])
        self.assertIs(boolean.Write.call_args.args[0].value, False)
        self.assertEqual(integer.Write.call_args.args[0].value, -123)
        self.assertEqual(real.Write.call_args.args[0].value, 1.25)


class WorkerTests(unittest.TestCase):
    def test_timeout_discards_session_without_replaying_write(self):
        client = OpcClient(timeout=.01)
        process = Mock()
        client._process = process
        client._responses = queue.Queue()
        with self.assertRaisesRegex(OpcError, 'timed out'):
            client.write({'Demo!tag': 1})
        self.assertEqual(process.stdin.write.call_count, 1)
        self.assertIsNone(client._process)

    def test_worker_exit_is_actionable_and_clears_process(self):
        client = OpcClient()
        client._process = Mock()
        client._responses = queue.Queue()
        client._responses.put(None)
        with self.assertRaisesRegex(OpcError, 'pywin32'):
            client.status()
        self.assertIsNone(client._process)


if __name__ == '__main__':
    unittest.main()
