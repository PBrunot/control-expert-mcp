"""Conservative parsing of Control Expert's textual build diagnostics."""

from __future__ import annotations

import re


def parse_diagnostics(output: str | None) -> list[dict]:
    """Extract recognized diagnostic lines; never infer a clean build from silence."""
    diagnostics = []
    for line in (output or "").splitlines():
        code = re.search(r"\b([EW]\d{3,4})\b", line)
        explicit = re.search(r"\b(error|warning)\s*:", line, re.I)
        if not code and not explicit:
            continue
        # DFB/action/SFC scopes use similar braces but do not name a plain task/section.
        owner = re.match(r"\s*\{([^{}:<]+?)\s*:\s*\[([\w]+)\]\}", line)
        location = re.search(r"\(l:\s*(\d+),\s*c:\s*(\d+)\)", line)
        diagnostics.append({
            "severity": explicit[1].lower() if explicit else
                        ("error" if code[1].startswith("E") else "warning"),
            "code": code[1] if code else None,
            "task": owner[2].strip() if owner else None,
            "section": owner[1].strip() if owner else None,
            "location": {"line": int(location[1]), "column": int(location[2])} if location else None,
            "message": line,
        })
    return diagnostics


def diagnostic_capture(before: dict, after: dict, operation: str) -> dict:
    """Describe observed output changes without asserting compiler attribution."""
    available = after["available"]
    comparable = available and before["available"] and before["tab"] == after["tab"]
    freshness = ("changed" if before["output"] != after["output"] else "unchanged") if comparable else "unknown"
    text = after["output"]
    scope = "snapshot"
    if comparable and before["output"] and text.startswith(before["output"]) and freshness == "changed":
        text = text[len(before["output"]):]
        scope = "appended"
    summary = None
    for line in (text or "").splitlines():
        match = re.fullmatch(r"\s*Process (succeeded|failed)\s*:\s*(\d+) Error\(s\)\s*,\s*"
                             r"(\d+) Warning\(s\)\s*", line, re.I)
        if match:
            summary = {"process_status": match[1].lower(), "errors": int(match[2]),
                       "warnings": int(match[3]), "message": line}
    return {"output": after["output"], "diagnostics_output": text,
            "diagnostics": parse_diagnostics(text),
            "diagnostics_summary": summary,
            "diagnostics_available": available,
            "diagnostics_capture": {
                "operation": operation, "source_tab": after["tab"],
                "freshness": freshness, "scope": scope,
                "attribution": "unverified",
                "read_errors": after.get("read_errors", []),
                "note": "Observed output changes do not prove operation attribution. "
                        "An empty diagnostics list does not establish a clean build; "
                        "check build_state, error, availability and freshness.",
            }}
