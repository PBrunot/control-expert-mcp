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


UNDEFINED_SYMBOL = re.compile(r"undefined symbol '([^']+)'", re.I)
CANDIDATE_NOTE = ("Declared variables ranked by name similarity only. Choose by declared type and "
                  "the surrounding expression; do not substitute a constant or declare a new "
                  "variable to hide the error.")


def _name_tokens(name: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]+", name.lower()) if len(t) > 1}


def rank_symbols(symbol: str, variables: list[dict], limit: int = 8) -> list[dict]:
    """Rank declared variables by token overlap and character similarity to an unknown symbol."""
    from difflib import SequenceMatcher

    wanted = _name_tokens(symbol)
    scored = []
    for variable in variables:
        tokens = _name_tokens(variable["name"])
        overlap = len(wanted & tokens) / len(wanted | tokens) if wanted | tokens else 0.0
        ratio = SequenceMatcher(None, symbol.lower(), variable["name"].lower()).ratio()
        score = max(overlap, ratio if ratio >= 0.6 else 0.0)
        if score > 0:
            scored.append((score, variable["name"].lower(), variable))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [{**variable, "score": round(score, 2)} for score, _, variable in scored[:limit]]


def undefined_symbols(diagnostics: list[dict]) -> list[tuple[dict, str]]:
    found = []
    for row in diagnostics:
        match = row.get("code") == "E1061" and UNDEFINED_SYMBOL.search(row.get("message", ""))
        if match:
            found.append((row, match[1]))
    return found


def attach_symbol_candidates(diagnostics: list[dict], variables: list[dict]) -> None:
    """Annotate E1061 undefined-symbol diagnostics with declared-variable suggestions."""
    for row, symbol in undefined_symbols(diagnostics):
        row["undefined_symbol"] = symbol
        row["candidates"] = rank_symbols(symbol, variables)
        row["candidate_note"] = CANDIDATE_NOTE
