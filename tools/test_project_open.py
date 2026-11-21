"""Offline regressions for archive opening and scrubbed COM environments."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from control_expert_mcp.bridge import (
    CEError, ControlExpertBridge, _format_com_error, _restore_windows_com_environment,
)


class ProjectOpenTests(unittest.TestCase):
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
