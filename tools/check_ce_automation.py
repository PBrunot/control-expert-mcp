"""Check the local CE COM broker and MCP registration; optionally build a scratch project."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import time

from control_expert_mcp.bridge import ControlExpertBridge


def inspect_application() -> dict:
    """Called exclusively on the bridge's STA worker; never closes an existing project."""
    broker = ControlExpertBridge._broker()
    app = broker.NewApplication()
    return {name: str(getattr(app, name)) for name in ("Version", "InstallationPath", "IsProjectOpen")}


async def inspect_mcp() -> dict:
    from control_expert_mcp.server import mcp

    tools = await mcp.list_tools()
    prompts = await mcp.list_prompts()
    return {"tools": len(tools), "prompts": len(prompts),
            "online_tools_registered": any(tool.name == "plc_connect" for tool in tools)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exercise-project", action="store_true",
                        help="Create, edit, build, save, export and reopen a disposable offline project")
    parser.add_argument("--cpu", default="BMX P34 2020")
    parser.add_argument("--cpu-version", default="02.70")
    parser.add_argument("--report", type=Path, help="Write JSON evidence to this path")
    args = parser.parse_args()
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "python": sys.version,
              "online_connection_attempted": False, "checks": {}}
    started = time.monotonic()
    bridge = ControlExpertBridge()
    try:
        report["checks"]["com"] = bridge._run(inspect_application)
        print(json.dumps(report["checks"]["com"], indent=2), flush=True)
        report["checks"]["mcp"] = asyncio.run(inspect_mcp())
        if args.exercise_project:
            with tempfile.TemporaryDirectory(prefix="ce-automation-check-") as temporary:
                folder = Path(temporary)
                try:
                    checks = report["checks"]
                    checks["create"] = bridge.new_project(args.cpu, args.cpu_version)
                    print("Scratch project created", flush=True)
                    checks["write_st"] = bridge.write_st_logic(
                        "MAST", "AutomationCheck", "CheckCounter := CheckCounter + 1;",
                        {"CheckCounter": "INT"},
                    )
                    checks["build"] = bridge.build_project(True)
                    print("Build:", json.dumps(checks["build"]), flush=True)
                    if checks["build"].get("build_state") != "built_ok":
                        raise RuntimeError("Scratch project did not reach built_ok")
                    checks["save"] = bridge.save_project(str(folder / "automation_check.stu"))
                    checks["export"] = bridge.export_project(str(folder / "automation_check.xef"))
                    checks["export_bytes"] = (folder / "automation_check.xef").stat().st_size
                    bridge.close_project(False)
                    checks["reopen"] = bridge.open_project(str(folder / "automation_check.stu"))
                    checks["status"] = bridge.get_status()
                    checks["variables"] = bridge.list_variables("CheckCounter", 10)
                finally:
                    bridge.close_project(False)
        report["success"] = True
    except Exception as exc:
        report["success"] = False
        report["error"] = str(exc)
    finally:
        bridge.shutdown()
    report["elapsed_seconds"] = round(time.monotonic() - started, 2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
