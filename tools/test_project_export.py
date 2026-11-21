"""Offline regressions for format fallback; run with the repository venv on Windows."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, call

import pywintypes

from control_expert_mcp import constants as C
from control_expert_mcp.bridge import CEError, ControlExpertBridge


def export_error(scode=0xA8A72CF4):
    return pywintypes.com_error(
        -2147352567, "Exception", (0, "Control Expert", "localized message", None, 0,
                                  scode - 0x100000000), None)


class ProjectExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = str(Path(self.temporary.name) / "sample.XEF")
        self.project = Mock()
        self.bridge = object.__new__(ControlExpertBridge)
        self.bridge._project = Mock(return_value=self.project)

    def test_m580_retries_zef_and_reports_actual_path(self):
        self.project.Export.side_effect = [export_error(), None]
        result = self.bridge._do_export_project(self.path)
        actual = str(Path(self.path).with_suffix('.zef'))
        self.assertEqual(result['exported'], actual)
        self.assertEqual(result['requested'], self.path)
        self.project.Export.assert_has_calls([
            call(self.path, C.EXPORT_PROJECT_FULL), call(actual, C.EXPORT_PROJECT_FULL)])
        self.bridge._project.assert_called_once_with(write=False)

    def test_supported_xef_is_unchanged(self):
        self.assertEqual(self.bridge._do_export_project(self.path), {'exported': self.path})
        self.project.Export.assert_called_once_with(self.path, C.EXPORT_PROJECT_FULL)

    def test_unrelated_error_is_not_retried(self):
        self.project.Export.side_effect = export_error(0x80070005)
        with self.assertRaises(pywintypes.com_error):
            self.bridge._do_export_project(self.path)
        self.assertEqual(self.project.Export.call_count, 1)

    def test_explicit_zef_error_is_not_retried(self):
        self.project.Export.side_effect = export_error()
        with self.assertRaises(pywintypes.com_error):
            self.bridge._do_export_project(str(Path(self.path).with_suffix('.zef')))
        self.assertEqual(self.project.Export.call_count, 1)

    def test_existing_fallback_is_preserved(self):
        target = Path(self.path).with_suffix('.zef')
        target.write_bytes(b'existing archive')
        self.project.Export.side_effect = export_error()
        with self.assertRaisesRegex(CEError, 'already exists'):
            self.bridge._do_export_project(self.path)
        self.assertEqual(target.read_bytes(), b'existing archive')
        self.assertEqual(self.project.Export.call_count, 1)

    def test_retry_failure_propagates(self):
        self.project.Export.side_effect = [export_error(), export_error(0x80070005)]
        with self.assertRaises(pywintypes.com_error):
            self.bridge._do_export_project(self.path)
        self.assertEqual(self.project.Export.call_count, 2)


if __name__ == '__main__':
    unittest.main()
