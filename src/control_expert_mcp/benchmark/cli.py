"""ce-bench entry point. Only run/resume can make paid API requests."""
from __future__ import annotations

import argparse
import asyncio
from importlib.util import find_spec
import json
import os
from pathlib import Path
import sys

from .core import Events, ce_lock, guard_directory, load_config, read_json, snapshot, write_json
from .report import compare
from .provider import adapter
from .runner import campaign, make_schedule, prepare, prepared, validate_fixtures
from .transport import Evidence, MCP


async def doctor(config: dict) -> dict:
    settings = config.get("provider", {})
    report = {"provider": adapter(config).name,
              "api_key_present": bool(os.environ.get(settings.get("api_key_env", adapter(config).key_env))),
              "credential_file_present": bool(settings.get("api_key_file") and Path(settings["api_key_file"]).is_file()),
              "model_identity": config["model"].get("identity", "pinned"),
              "openai_installed": find_spec("openai") is not None,
              "paid_requests": 0, "com_registry_present": False, "conditions": {},
              "ce_version": "unverified until prepare opens a disposable project"}
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "PSBroker.PServerBroker.1"):
                report["com_registry_present"] = True
        except OSError:
            pass
    try:
        manifest = prepared(config)
        report["prepared"] = {"baseline": manifest["baseline"], "status": manifest["status"]}
    except (OSError, ValueError, KeyError) as exc:
        report["prepared"] = {"ready": False, "reason": str(exc)}
    directory = Path(config["workspace"]) / "doctor"
    with ce_lock(Path(config["workspace"])):
        for name, condition in config["conditions"].items():
            try:
                evidence = Evidence(directory / name, Events(directory / name / "events.jsonl"))
                async with MCP(condition, config, evidence) as mcp:
                    instructions, tools = mcp.adapter("threshold")
                    report["conditions"][name] = {"server_info": mcp.initialization.get("server_info"),
                        "tools": [tool["name"] for tool in tools],
                        "documentation": await mcp.checked("get_documentation_status")
                            if any(t["name"] == "get_documentation_status" for t in mcp.tools) else None}
            except Exception as exc:
                report["conditions"][name] = {"error": type(exc).__name__}
                if (Path(config["workspace"]) / "TAINTED.json").exists():
                    break
    report["snapshot"] = snapshot(config)
    write_json(directory / "report.json", report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "prepare", "validate", "run", "resume", "recover"):
        sub = subs.add_parser(name)
        sub.add_argument("--config", required=True)
        if name in {"prepare", "validate"}:
            sub.add_argument("--condition", default="A")
        if name == "run":
            sub.add_argument("--condition", nargs="+", default=None)
            sub.add_argument("--repeats", type=int, default=5)
            sub.add_argument("--seed", type=int, default=1729)
            sub.add_argument("--dry-run", action="store_true")
        if name == "resume":
            sub.add_argument("--run-id", required=True)
        if name == "recover":
            sub.add_argument("--verified-idle", action="store_true", required=True,
                             help="Operator attests timed-out CE operations ended and session recovered")
    sub = subs.add_parser("compare")
    sub.add_argument("--results", type=Path, required=True)
    sub.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "compare":
            report = compare(args.results, args.output)
            print(f"Wrote {args.output}.json and .md ({len(report['groups'])} separate fingerprint groups)")
            return 0
        config = load_config(args.config)
        if args.command == "doctor":
            report = asyncio.run(doctor(config))
            # Full reproducibility data stays in the local report, not the console.
            print(json.dumps({k: v for k, v in report.items() if k != "snapshot"}, indent=2))
        elif args.command == "prepare":
            print(asyncio.run(prepare(config, args.condition)))
        elif args.command == "validate":
            print(asyncio.run(validate_fixtures(config, args.condition)))
        elif args.command == "recover":
            with ce_lock(Path(config["workspace"]), allow_taint=True):
                taints = {Path(config["workspace"]) / "TAINTED.json", guard_directory() / "TAINTED.json"}
                global_taint = guard_directory() / "TAINTED.json"
                if global_taint.exists():
                    origin = read_json(global_taint).get("workspace")
                    if origin:
                        taints.add(Path(origin) / "TAINTED.json")
                for taint in taints:
                    if taint.exists():
                        # Retain evidence; the explicit operator attestation is required.
                        import uuid
                        taint.rename(taint.with_name("recovered-" + uuid.uuid4().hex + ".json"))
            print("Recovery acknowledged. Next case will reopen a fresh fixture.")
        else:
            conditions = args.condition if args.command == "run" and args.condition else list(config["conditions"])
            if any(name not in config["conditions"] for name in conditions) or len(conditions) != len(set(conditions)):
                raise ValueError("Choose distinct configured conditions")
            if args.command == "run" and args.dry_run:
                report = asyncio.run(doctor(config))
                print(json.dumps({"paid_requests": 0, "schedule": make_schedule(conditions, args.repeats, args.seed),
                                  "prerequisites": {k: v for k, v in report.items() if k != "snapshot"}}, indent=2))
            else:
                if "REPLACE" in config["model"]["id"]:
                    raise ValueError("Configure an exact model ID/snapshot before a paid run")
                print(asyncio.run(campaign(config, conditions, getattr(args, "repeats", 5),
                                          getattr(args, "seed", 1729), getattr(args, "run_id", None))))
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        # Provider exception text can contain URLs or credentials. Log class only.
        print(f"ce-bench failed: {type(exc).__name__}. Check local events and prerequisites.", file=sys.stderr)
        if isinstance(exc, (ValueError, FileNotFoundError)):
            print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
