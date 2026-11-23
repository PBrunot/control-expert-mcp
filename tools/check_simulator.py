"""Opt-in stdio MCP commissioning check; replaces the local simulator application.

Run from the repository root with --approve-download. --cold-start terminates
the local simulator first. --verify-run briefly runs the demo and returns it to
STOP. No physical PLC or OPC/Modbus tag access is used. Source files are not saved.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def check(args):
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "steps": []}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    parameters = StdioServerParameters(
        command=sys.executable, args=["-m", "control_expert_mcp"],
        env={**os.environ, "CE_MCP_ENABLE_ONLINE": "1"})
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()

            async def call(name, **arguments):
                response = await session.call_tool(name, arguments)
                raw = response.content[0].text
                value = {"error": raw} if response.is_error else json.loads(raw)
                report["steps"].append({"tool": name, "arguments": arguments, "result": value})
                args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(f"{name}: {value.get('plc_state', value.get('build_state', 'ok'))}", flush=True)
                if response.is_error:
                    raise RuntimeError(f"{name}: {raw}")
                return value

            await call("get_status")
            await call("get_live_access_setup")
            await call("configure_live_access", allow_live_connection=True,
                       protocol="engineering", allow_closed_loop=True)
            if args.cold_start:
                await call("stop_simulator")
                closed = await call("get_simulator_status")
                if closed["simulator_running"] or closed["plc_state"] != "unknown":
                    raise RuntimeError("Simulator did not close")
            await call("open_project", path=str(args.project.resolve()))
            await call("get_status")
            build = await call("build_project", rebuild_all=True)
            if build.get("build_state") != "built_ok" or build.get("error"):
                raise RuntimeError("Build failed; inspect report diagnostics")
            await call("start_simulator")
            await call("get_simulator_status")
            await call("plc_setup_connection", target="simulator", address="127.0.0.1", driver="TCPIP")
            await call("plc_connect", target="simulator")
            state = await call("get_simulator_status")
            if not state.get("connected"):
                raise RuntimeError("No observed simulator connection")
            if state["plc_state"] != "no_conf":
                state = await call("plc_command", command="stop")
                if state.get("plc_state") != "stop":
                    raise RuntimeError("Simulator did not reach STOP")
            await call("plc_transfer", direction="pc_to_plc")

            async def require_state(expected):
                state = await call("get_simulator_status")
                if not (state.get("simulator_running") and state.get("connected")
                        and state.get("pc_equals_plc") is True and state.get("plc_state") == expected):
                    raise RuntimeError(f"Expected matching application in {expected}: {state}")

            await require_state("stop")
            if args.verify_run:
                await call("plc_command", command="run")
                await require_state("run")
                await call("plc_command", command="stop")
                await require_state("stop")
            await call("plc_disconnect")
            disconnected = await call("get_simulator_status")
            if disconnected["plc_state"] != "unknown":
                raise RuntimeError("Disconnected state must be unknown")
            await call("close_project", save=False)
            report["success"] = True
            args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve-download", action="store_true", required=True)
    parser.add_argument("--cold-start", action="store_true")
    parser.add_argument("--verify-run", action="store_true")
    parser.add_argument("--project", type=Path, default=Path("samples/demo_ControlExpert_M580.STU"))
    parser.add_argument("--report", type=Path, default=Path("tmp/simulator-check.json"))
    asyncio.run(check(parser.parse_args()))


if __name__ == "__main__":
    main()
