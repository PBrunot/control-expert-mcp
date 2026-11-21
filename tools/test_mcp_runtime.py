"""MCP 2.x protocol and shared Modbus regression checks; never connect to a PLC."""

from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import create_autospec, patch

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pymodbus.client import ModbusTcpClient

from control_expert_mcp.modbus import ModbusClient
from control_expert_mcp.documentation import build_index


class MCPRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_manual_tools_over_stdio_without_application(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "topic.md").write_text('# TON\n\nSynthetic timer reference.\n', encoding="utf-8")
            (root / "manifest.json").write_text(json.dumps({"manuals": [
                {"status": "converted", "source": "test.chm", "folder": ".",
                 "title": "Test", "outputs": ["topic.md"], "warnings": []},
            ]}), encoding="utf-8")
            build_index(root)
            parameters = StdioServerParameters(command=sys.executable,
                args=["-m", "control_expert_mcp"],
                env={**os.environ, "CE_MCP_ENABLE_ONLINE": "0", "CE_MCP_MANUALS_DIR": str(root)})
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    status = await session.call_tool("get_documentation_status", {})
                    self.assertTrue(json.loads(status.content[0].text)["ready"])
                    result = await session.call_tool("search_manuals", {"query": "TON"})
                    self.assertFalse(result.is_error)
                    topic = json.loads(result.content[0].text)["results"][0]
                    response = await session.call_tool("get_manual_topic", {"topic_id": topic["topic_id"]})
                    self.assertFalse(response.is_error)
                    self.assertIn("Synthetic timer reference", json.loads(response.content[0].text)["markdown"])
                    status = await session.call_tool("get_status", {})
                    self.assertEqual(json.loads(status.content[0].text)["session"], "no application open")
                    error = await session.call_tool("get_manual_topic", {"topic_id": "../secret"})
                    self.assertTrue(error.is_error)
                    self.assertIn("Invalid topic ID", error.content[0].text)

    async def test_stdio_tools_resources_and_prompts(self):
        environment = {**os.environ, "CE_MCP_ENABLE_ONLINE": "0"}
        parameters = StdioServerParameters(command=sys.executable,
                                           args=["-m", "control_expert_mcp"], env=environment)
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                self.assertEqual(initialized.server_info.version, version("control-expert-mcp"))
                tools = {tool.name for tool in (await session.list_tools()).tools}
                self.assertIn("get_language_reference", tools)
                self.assertNotIn("plc_connect", tools)
                result = await session.call_tool("get_status", {})
                self.assertFalse(result.is_error)
                self.assertEqual(json.loads(result.content[0].text)["session"], "no application open")
                language = await session.read_resource("reference://language/ST")
                self.assertIn("ST", language.contents[0].text)
                prompts = {prompt.name for prompt in (await session.list_prompts()).prompts}
                self.assertIn("consult_installed_manuals", prompts)
                prompt = await session.get_prompt("consult_installed_manuals", {})
                self.assertTrue(prompt.messages)
                error = await session.call_tool("get_language_reference", {"language": "invalid"})
                self.assertTrue(error.is_error)
                self.assertIn("Unknown language", error.content[0].text)
                error = await session.call_tool("get_project_structure", {})
                self.assertTrue(error.is_error)
                self.assertIn("No project is open", error.content[0].text)

    async def test_online_flag_controls_registration_without_connecting(self):
        parameters = StdioServerParameters(command=sys.executable,
                                           args=["-m", "control_expert_mcp"],
                                           env={**os.environ, "CE_MCP_ENABLE_ONLINE": "1"})
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                self.assertIn("get_live_access_setup", initialized.instructions)
                tools = {tool.name for tool in (await session.list_tools()).tools}
                self.assertIn("plc_connect", tools)
                self.assertIn("read_tags", tools)
                self.assertIn("opc_connect", tools)
                self.assertIn("configure_live_access", tools)
                self.assertIn("get_live_access_setup", tools)
                status = await session.call_tool("get_live_access_setup", {})
                self.assertFalse(json.loads(status.content[0].text)["allow_live_connection"])
                blocked = await session.call_tool("opc_connect", {})
                self.assertTrue(blocked.is_error)
                self.assertIn("configure_live_access", blocked.content[0].text)
                rejected = await session.call_tool("configure_live_access", {
                    "allow_live_connection": True, "ofs_alias": "Demo", "allow_closed_loop": True})
                self.assertTrue(rejected.is_error)
                self.assertIn("confirm OFS", rejected.content[0].text)
                accepted = await session.call_tool("configure_live_access", {
                    "allow_live_connection": True, "ofs_alias": "Demo"})
                self.assertFalse(accepted.is_error)
                for name, args in (("modbus_connect", {"host": "127.0.0.1"}),
                                   ("opc_connect", {"alias": "Other"}),
                                   ("opc_write_tags", {"values": {"x": 1}})):
                    blocked = await session.call_tool(name, args)
                    self.assertTrue(blocked.is_error)
                revoked = await session.call_tool("configure_live_access", {"allow_live_connection": False})
                self.assertFalse(revoked.is_error)
                blocked = await session.call_tool("opc_read_tags", {"tags": ["x"]})
                self.assertTrue(blocked.is_error)


class ModbusCompatibilityTests(unittest.TestCase):
    def test_latest_client_signature_and_schneider_word_order(self):
        transport = create_autospec(ModbusTcpClient, instance=True)
        transport.read_holding_registers.return_value = SimpleNamespace(
            isError=lambda: False, registers=[0x0000, 0x3F80])
        transport.write_registers.return_value = SimpleNamespace(isError=lambda: False)
        client = ModbusClient()
        client._client = transport
        self.assertEqual(client.read_one("%MW2", "REAL"), 1.0)
        client.write_one("%MW2", "REAL", 1.0)
        transport.read_holding_registers.assert_called_once_with(2, count=2, device_id=1)
        transport.write_registers.assert_called_once_with(2, [0, 0x3F80], device_id=1)

    def test_concurrent_bit_writes_do_not_lose_updates(self):
        register = [0]
        def read(address, *, count, device_id):
            old = register[0]
            time.sleep(0.01)
            return SimpleNamespace(isError=lambda: False, registers=[old])
        def write(address, value, *, device_id):
            register[0] = value
            return SimpleNamespace(isError=lambda: False)
        client = ModbusClient()
        client._client = SimpleNamespace(read_holding_registers=read, write_register=write)
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(lambda bit: client.write_one(f"%MW0.{bit}", "BOOL", True), [0, 1]))
        self.assertEqual(register[0], 3)

    def test_connect_can_read_status_under_reentrant_lock(self):
        with patch("pymodbus.client.ModbusTcpClient", autospec=True) as constructor:
            constructor.return_value.connect.return_value = True
            constructor.return_value.connected = True
            client = ModbusClient()
            self.assertTrue(client.connect("127.0.0.1", 502, 1, "low_first")["connected"])
            self.assertFalse(client.disconnect()["connected"])


if __name__ == "__main__":
    unittest.main()
