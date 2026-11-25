"""Offline regressions for archive opening and scrubbed COM environments."""

import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import Mock, patch

from control_expert_mcp.bridge import (
    CEError, ControlExpertBridge, _format_com_error, _restore_windows_com_environment,
)


class ProjectOpenTests(unittest.TestCase):
    def test_plc_execution_commands_are_idempotent_without_resetting_memory(self):
        for command, observed in (("stop", "stop"), ("stop", "no_conf"), ("run", "run")):
            bridge = object.__new__(ControlExpertBridge)
            app = Mock()
            bridge._ensure_app = Mock(return_value=app)
            bridge._project = Mock(return_value="write-token")
            bridge._do_plc_state = Mock(return_value={"connected": True, "plc_state": observed})
            result = bridge._do_plc_command(command)
            self.assertFalse(result["command_sent"])
            self.assertEqual(result["plc_state"], observed)
            app.TargetSendCommand.assert_not_called()
            bridge._project.assert_called_once_with(write=True)

    def test_no_configuration_explains_required_download_for_run_and_init(self):
        for command in ("run", "init"):
            bridge = object.__new__(ControlExpertBridge)
            app = Mock()
            bridge._ensure_app = Mock(return_value=app)
            bridge._project = Mock(return_value="write-token")
            bridge._do_plc_state = Mock(return_value={"connected": True, "plc_state": "no_conf"})
            with self.assertRaisesRegex(CEError, "Download a successfully built project"):
                bridge._do_plc_command(command)
            app.TargetSendCommand.assert_not_called()

    def test_init_on_stopped_application_still_reinitializes(self):
        bridge = object.__new__(ControlExpertBridge)
        app = Mock()
        bridge._ensure_app = Mock(return_value=app)
        bridge._project = Mock(return_value="write-token")
        bridge._do_plc_state = Mock(return_value={"connected": True, "plc_state": "stop"})
        result = bridge._do_plc_command("init")
        self.assertTrue(result["command_sent"])
        app.TargetSendCommand.assert_called_once_with(1, "write-token")

    def test_simulator_status_distinguishes_process_from_plc_execution(self):
        bridge = object.__new__(ControlExpertBridge)
        bridge._app = Mock(SelectTarget=1)
        bridge._sim_running = Mock(return_value=False)
        bridge._do_plc_state = Mock()
        status = bridge._do_get_simulator_status()
        self.assertFalse(status['simulator_running'])
        self.assertEqual(status['plc_state'], 'unknown')
        bridge._do_plc_state.assert_not_called()
        bridge._sim_running.return_value = True
        for state in ('no_conf', 'stop', 'run', 'halt', 'default', 'unknown'):
            bridge._do_plc_state.return_value = {
                'connected': True, 'plc_state': state, 'pc_equals_plc': state != 'no_conf'}
            with self.subTest(state=state):
                status = bridge._do_get_simulator_status()
                self.assertTrue(status['simulator_running'])
                self.assertEqual(status['plc_state'], state)
                self.assertEqual(status['state_source'], 'engineering_connection')

    def test_simulator_status_never_attributes_a_real_plc_or_stale_state(self):
        bridge = object.__new__(ControlExpertBridge)
        bridge._sim_running = Mock(return_value=True)
        bridge._do_plc_state = Mock(return_value={'connected': False, 'plc_state': 'run'})
        for app, reason in ((None, 'no_application_open'),
                            (Mock(SelectTarget=0), 'engineering_target_is_not_simulator'),
                            (Mock(SelectTarget=1), 'simulator_not_connected')):
            bridge._app = app
            with self.subTest(reason=reason):
                status = bridge._do_get_simulator_status()
                self.assertEqual(status['plc_state'], 'unknown')
                self.assertIsNone(status['pc_equals_plc'])
                self.assertEqual(status['reason'], reason)

    def test_simulator_uses_active_installation_instead_of_legacy_path(self):
        bridge = object.__new__(ControlExpertBridge)
        bridge._app = Mock(InstallationPath="active-ce-16.4")
        bridge._sim_running = Mock(side_effect=[False, True])
        expected = os.path.join("active-ce-16.4", "PLC_Simulator", "sim.exe")
        with patch.dict(os.environ, {"CE_MCP_SIMULATOR_EXE": ""}), \
             patch.dict(sys.modules, {"winreg": Mock()}), \
             patch("os.path.isfile", side_effect=lambda p: p == expected), \
             patch("subprocess.Popen") as launch, patch("time.sleep"):
            self.assertEqual(bridge._do_start_simulator(True)["simulator"], "started")
        launch.assert_called_once_with([expected])

    def test_missing_active_simulator_does_not_launch_another_version(self):
        bridge = object.__new__(ControlExpertBridge)
        bridge._app = Mock(InstallationPath="missing-active-ce")
        bridge._sim_running = Mock(return_value=False)
        with patch.dict(os.environ, {"CE_MCP_SIMULATOR_EXE": ""}), \
             patch.dict(sys.modules, {"winreg": Mock()}), \
             patch("os.path.isfile", return_value=False), \
             patch("subprocess.Popen") as launch:
            with self.assertRaisesRegex(CEError, "missing-active-ce"):
                bridge._do_start_simulator(True)
        launch.assert_not_called()

    def test_simulator_override_and_missing_application_need_no_version_guess(self):
        bridge = object.__new__(ControlExpertBridge)
        bridge._app = None
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "custom-simulator.exe"
            executable.write_bytes(b"test, never executed")
            with patch.dict(os.environ, {"CE_MCP_SIMULATOR_EXE": str(executable)}):
                actual = Path(bridge._simulator_executable())
                self.assertTrue(actual.is_absolute())
                # Windows short and long paths can identify the same file.
                self.assertTrue(actual.samefile(executable))
        with patch.dict(os.environ, {"CE_MCP_SIMULATOR_EXE": ""}):
            with self.assertRaisesRegex(CEError, "Open.*project first"):
                bridge._simulator_executable()

    def test_archive_requires_native_saveas_and_preserves_source(self):
        bridge = object.__new__(ControlExpertBridge)
        bridge._do_close = Mock()
        broker = Mock()
        bridge._broker = Mock(return_value=broker)
        project = Mock(HasProjectFileName=0)
        bridge._project = Mock(return_value=project)
        bridge._project_info = Mock(return_value={"name": "Project"})
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "sample.STA"
            archive.write_bytes(b"archive fixture")
            bridge._do_open_project(str(archive))
            broker.OpenApplication.assert_not_called()
            broker.NewApplication.return_value.OpenArchive.assert_called_once_with(str(archive), "")
            self.assertIsNone(bridge._project_path)
            with self.assertRaisesRegex(CEError, "explicit.*stu path"):
                bridge._do_save_project(None)
            project.SaveAs.assert_not_called()
            self.assertEqual(archive.read_bytes(), b"archive fixture")

    @unittest.skipUnless(os.name == "nt", "Windows registry paths")
    def test_scrubbed_environment_is_restored_without_overwriting_configuration(self):
        names = ("CommonProgramFiles", "CommonProgramFiles(x86)", "CommonProgramW6432")
        with patch.dict(os.environ, {}, clear=True):
            _restore_windows_com_environment()
            for name in names:
                self.assertTrue(Path(os.environ[name]).is_dir(), name)
            os.environ["CommonProgramFiles"] = "explicit-test-path"
            del os.environ["CommonProgramW6432"]
            _restore_windows_com_environment()
            self.assertEqual(os.environ["CommonProgramFiles"], "explicit-test-path")
            self.assertTrue(Path(os.environ["CommonProgramW6432"]).is_dir())

    @unittest.skipUnless(os.name == "nt", "pywin32 COM exception")
    def test_server_code_survives_generic_dispatch_exception(self):
        import pywintypes
        error = pywintypes.com_error(-2147352567, "Exception",
                                    (0, "PSBroker.PServerBroker.1", None, None, 0, -2147219191), None)
        message = _format_com_error(error)
        self.assertIn("0x80040909", message)
        self.assertIn("0x80020009", message)


if __name__ == "__main__":
    unittest.main()
