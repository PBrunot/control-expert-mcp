"""Claude Code plugin and marketplace stay in sync with the released package."""

import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PluginTests(unittest.TestCase):
    def test_versions_and_layout(self):
        version = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M)[1]
        manifest = json.loads((ROOT / "plugin/.claude-plugin/plugin.json").read_text())
        servers = json.loads((ROOT / "plugin/.mcp.json").read_text())["mcpServers"]
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual(manifest["version"], version)
        self.assertEqual(servers["control-expert"]["args"], [f"control-expert-mcp@{version}"])
        self.assertEqual(servers["control-expert"]["env"]["CE_MCP_ENABLE_ONLINE"], "${user_config.enable_online}")
        self.assertFalse(manifest["userConfig"]["enable_online"]["default"])
        self.assertEqual([(p["name"], p["source"]) for p in marketplace["plugins"]], [(manifest["name"], "./plugin")])
        skill = (ROOT / "plugin/skills/control-expert/SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---\nname: control-expert\n"))
        self.assertIn("allow_online_change", skill)
        # A repo-root .mcp.json would also act as a project MCP config for contributors.
        self.assertFalse((ROOT / ".mcp.json").exists())


if __name__ == "__main__":
    unittest.main()
