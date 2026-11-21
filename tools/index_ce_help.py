"""Explicitly index converted local manuals; never opens Control Expert or a PLC."""

from control_expert_mcp.documentation import main


if __name__ == "__main__":
    raise SystemExit(main())
