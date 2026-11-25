"""Constrained native IEC authoring and artifact validation.

The benchmark intentionally permits only local scalar logic. This is a narrow
authoring contract, not a general parser for arbitrary Control Expert programs.
"""
from __future__ import annotations

import re
from lxml import etree as ET

from .iec_cases import Case

ROOTS = {lang: lang + "ExchangeFile" for lang in ("ST", "LD", "FBD", "SFC", "IL")}
SOURCE = {lang: lang + "Source" for lang in ("ST", "LD", "FBD", "IL")}
FUNCTIONS = {"INT_TO_DINT", "DINT_TO_INT", "MIN", "MAX", "LIMIT", "ABS"}
KEYWORDS = {"IF", "THEN", "ELSE", "ELSIF", "END_IF", "TRUE", "FALSE", "AND", "OR", "XOR", "NOT", "MOD"}
OPS = {"LD", "LDN", "ST", "STN", "S", "R", "AND", "ANDN", "OR", "ORN", "XOR", "XORN", "NOT"}
BLOCKS = {"AND_BOOL", "OR_BOOL", "XOR_BOOL", "NOT_BOOL", "LE_INT", "GE_INT", "LT_INT", "GT_INT", "EQ_INT", "NE_INT", "RS", "SR"}
TAGS = {
    "fileHeader", "contentHeader", "comment", "program", "identProgram", "STSource", "ILSource",
    "LDSource", "networkLD", "typeLine", "emptyLine", "emptyCell", "contact", "coil", "shortCircuit", "VLink", "HLink",
    "FBDSource", "networkFBD", "FFBBlock", "objPosition", "descriptionFFB", "inputVariable", "outputVariable",
    "linkFB", "linkSource", "linkDestination", "gridObjPosition", "textBox",
    "SFCProgram", "chartSource", "networkSFC", "step", "literals", "transition", "transitionCondition",
    "variableName", "jumpSFC", "action", "actionName", "sectionName", "tValue", "tLiteral",
    "actionSource", "transitionSource",
}
ATTRIBUTES = {
    "company", "product", "dateTime", "content", "DTDVersion", "name", "version", "type", "task",
    "nbColumns", "nbRows", "nbCells", "typeContact", "contactVariableName", "typeCoil", "coilVariableName",
    "instanceName", "typeName", "additionnalPinNumber", "enEnO", "width", "height", "posX", "posY",
    "execAfter", "invertedPin", "formalParameter", "effectiveParameter", "parentObjectName", "pinName",
    "areaNum", "operatorCtrl", "stepType", "stepName", "max", "min", "delay", "invertLogic", "qualifier",
}


def parse(xml: str):
    if not isinstance(xml, str) or len(xml) > 200000 or re.search(r"<!DOCTYPE|<!ENTITY", xml, re.I):
        raise ValueError("XML must be inline, bounded and have no DTD/entities")
    try:
        root = ET.fromstring(xml.encode(), ET.XMLParser(resolve_entities=False, no_network=True))
    except ET.XMLSyntaxError as exc:
        raise ValueError("Invalid exchange XML") from exc
    if any(not isinstance(n.tag, str) or "{" in n.tag for n in root.iter()):
        raise ValueError("XML namespaces and processing instructions are unsupported")
    return root


def strip_comments(source: str) -> str:
    return re.sub(r"\(\*.*?\*\)|//[^\n]*", " ", source, flags=re.S)


def expression(source: str, names: set[str], *, il: bool = False, steps: bool = False) -> str:
    clean = strip_comments(source)
    clean = re.sub(r"\b(?:BOOL|INT|DINT)#(TRUE|FALSE|[+-]?\d+)\b", r"\1", clean, flags=re.I)
    if re.search(r"[^A-Za-z0-9_\s.:;()+*/<>=,\-]", clean):
        raise ValueError("Only local scalar expressions are permitted")
    allowed = {n.upper() for n in names} | KEYWORDS | FUNCTIONS | (OPS if il else set())
    if steps:
        for name in ("Idle", "Active", "Completed"):
            clean = re.sub(r"\b" + name + r"\.x\b", "TRUE", clean, flags=re.I)
    if "." in clean:
        raise ValueError("Only approved SFC step .x access is permitted")
    if any(token.upper() not in allowed for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", clean)):
        raise ValueError("Unknown identifier, system access or function")
    return clean


def source_policy(source: str, case: Case, helpers: dict[str, str], *, il=False) -> None:
    names = {n for n, _ in case.inputs + case.outputs} | set(helpers)
    clean = expression(source, names, il=il)
    writable = {n.casefold() for n, _ in case.outputs} | {n.casefold() for n in helpers}
    targets = (re.findall(r"(?im)^\s*(?:STN?|S|R)\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", clean)
               if il else re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*:=", clean))
    if any(name.casefold() not in writable for name in targets):
        raise ValueError("Inputs are read-only")
    if il:
        for line in clean.splitlines():
            if line.strip() and not re.fullmatch(r"\s*(?:" + "|".join(sorted(OPS)) +
                                               r")\b[^;:]*", line, re.I):
                raise ValueError("Unsupported IL instruction")
    elif re.search(r"\b[A-Za-z_][A-Za-z0-9_]*\s*\(", clean):
        calls = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", clean)
        if any(c.upper() not in FUNCTIONS | {"IF", "ELSIF", "NOT", "AND", "OR", "XOR"} for c in calls):
            raise ValueError("Only scalar conversion/arithmetic functions are allowed")


def helper_policy(source: str, case: Case, helpers: dict[str, str], *, post=False) -> None:
    """SFC helpers are combinational: no feedback, branches or sequence state."""
    if not source.strip():
        return
    names = {n for n, _ in case.inputs} if not post else set()
    for statement in strip_comments(source).split(";"):
        if not statement.strip():
            continue
        match = re.fullmatch(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*:=\s*(.+)\s*", statement, re.S)
        if not match:
            raise ValueError("SFC helpers must contain simple combinational assignments")
        target, rhs = match.groups()
        writable = {n for n, _ in case.outputs} if post else set(helpers)
        if target not in writable:
            raise ValueError("Invalid SFC helper target")
        expression(rhs, names, steps=post)
        if re.search(r"\b(?:IF|THEN|ELSE|END_IF)\b|:=", rhs, re.I):
            raise ValueError("SFC helper cannot implement a state machine")


def validate_submission(case: Case, submission: dict) -> dict:
    if not isinstance(submission, dict) or set(submission) - {"xml", "st_source", "helpers", "pre", "post"}:
        raise ValueError("Unknown candidate fields")
    helpers = submission.get("helpers", {})
    if not isinstance(helpers, dict) or len(helpers) > 32:
        raise ValueError("At most 32 scoped helpers")
    names = set()
    helper_types = {"BOOL", "INT", "DINT"} | ({"RS", "SR"} if case.language == "FBD" else set())
    for name, kind in helpers.items():
        if (not re.fullmatch(r"LLM_[A-Za-z0-9_]{1,48}", name) or kind not in helper_types
                or name.casefold() in names):
            raise ValueError("Helpers must be unique unlocated LLM_* BOOL/INT/DINT; FBD also permits RS/SR")
        names.add(name.casefold())
    pre, post = submission.get("pre", ""), submission.get("post", "")
    if case.language != "SFC" and (pre or post):
        raise ValueError("Separate helpers are only supported for SFC")
    if case.language == "SFC":
        helper_policy(pre, case, helpers)
        helper_policy(post, case, helpers, post=True)
    if case.language == "ST":
        if submission.get("xml") or not isinstance(submission.get("st_source"), str):
            raise ValueError("ST requires st_source")
        source_policy(submission["st_source"], case, helpers)
        return {"st_source": submission["st_source"], "helpers": dict(helpers), "pre": pre, "post": post}
    if submission.get("st_source"):
        raise ValueError("Native non-ST exchange XML required")
    root = parse(submission.get("xml", ""))
    if root.tag != ROOTS[case.language]:
        raise ValueError("Wrong native language")
    identifiers = list(root.iter("identProgram"))
    if len(identifiers) != 1 or dict(identifiers[0].attrib) != {"name": "Candidate", "type": "section", "task": "MAST"}:
        raise ValueError("Only MAST/Candidate may be imported")
    all_names = {n for n, _ in case.inputs + case.outputs} | set(helpers)
    writable = {n for n, _ in case.outputs} | set(helpers)
    actions = {n.get("name"): n for n in root.iter("actionSource")}
    if len(actions) != len(list(root.iter("actionSource"))) or any(
            not re.fullmatch(r"LLM_[A-Za-z0-9_]+", name or "") for name in actions):
        raise ValueError("Inline action names must be unique scoped LLM_* names")
    for node in root.iter():
        if node is root:
            continue
        if node.tag not in TAGS or set(node.attrib) - ATTRIBUTES:
            raise ValueError("Unsupported exchange node/attribute: " + node.tag)
        if node.tag in set(SOURCE.values()) and node.tag != SOURCE.get(case.language) and not (
                case.language == "SFC" and node.tag == "STSource"):
            raise ValueError("Cross-language executable body")
        if any(re.search(r"Bench_|%|[\\/]", v, re.I) for v in node.attrib.values()):
            raise ValueError("External/reserved reference in XML")
        if node.tag in {"STSource", "ILSource"}:
            if case.language == "SFC":
                # Inline actions are evaluated only by native chart activation.
                if node.getparent().tag != "actionSource":
                    raise ValueError("Inline executable ST must be a native chart action")
                for statement in strip_comments(node.text or "").split(";"):
                    if not statement.strip():
                        continue
                    target = statement.partition(":=")[0].strip()
                    helper_policy(statement + ";", case, helpers,
                                  post=target in {name for name, _ in case.outputs})
            elif node.tag != SOURCE.get(case.language):
                raise ValueError("Cross-language executable source")
            else:
                source_policy(node.text or "", case, helpers, il=case.language == "IL")
        for key in ("contactVariableName", "effectiveParameter"):
            if node.get(key):
                if ":" in node.get(key) or ";" in node.get(key):
                    raise ValueError("Pin expressions cannot contain statements")
                expression(node.get(key), all_names)
        for key in ("coilVariableName",):
            if node.get(key) and node.get(key) not in writable:
                raise ValueError("Illegal coil target")
        if node.tag == "outputVariable" and node.get("effectiveParameter") and node.get("effectiveParameter") not in writable:
            raise ValueError("Illegal block output target")
        if node.tag == "FFBBlock" and node.get("typeName") not in BLOCKS:
            raise ValueError("Unsupported FBD block")
        if node.tag == "FFBBlock" and node.get("typeName") in {"RS", "SR"}:
            if helpers.get(node.get("instanceName")) != node.get("typeName"):
                raise ValueError("Declare each native bistable instance in helpers with its matching RS/SR type")
        if node.tag == "sectionName" and (node.text or "").strip() not in actions:
            raise ValueError("Chart action reference must resolve inside the candidate")
        if node.tag == "variableName":
            if ":" in (node.text or "") or ";" in (node.text or ""):
                raise ValueError("Transition expressions cannot contain statements")
            expression(node.text or "", all_names)
        if node.tag == "literals" and any(node.get(k) for k in ("min", "max", "delay")):
            raise ValueError("Timer-dependent SFC steps are unsupported")
    if case.language == "SFC":
        steps = list(root.iter("step"))
        if ({s.get("stepName") for s in steps} != {"Idle", "Active", "Completed"} or len(steps) != 3
                or [s.get("stepName") for s in steps if s.get("stepType") == "initialStep"] != ["Idle"]
                or len(list(root.iter("transition"))) != 3 or len(list(root.iter("chartSource"))) != 1):
            raise ValueError("Native three-step chart with initial Idle required")
    elif len(list(root.iter(SOURCE[case.language]))) != 1:
        raise ValueError("Missing native executable body")
    # Drop vendor headers/comments. No hidden declarations are imported.
    return {"xml": ET.tostring(root, encoding="unicode"), "helpers": dict(helpers), "pre": pre, "post": post}


def envelope(language: str, source: str) -> str:
    root = ET.Element(ROOTS[language])
    ET.SubElement(root, "fileHeader", company="Schneider Automation", product="Control Expert V16.4",
                  dateTime="date_and_time#2026-11-25-0:0:0", content=language + " source file", DTDVersion="41")
    ET.SubElement(root, "contentHeader", name="IEC_Benchmark", version="0.0.000",
                  dateTime="date_and_time#2026-11-25-0:0:0")
    root.append(ET.fromstring(source.encode()))
    return ET.tostring(root, encoding="unicode")


def executable_identity(submission: dict) -> dict:
    """Ignore headers, comments and source whitespace, retain executable content."""
    def node_identity(node):
        if node.tag in {"fileHeader", "contentHeader", "comment"}:
            return None
        text = " ".join((node.text or "").split())
        if node.tag in {"STSource", "ILSource"}:
            text = " ".join(strip_comments(node.text or "").upper().split())
        return [node.tag, sorted(node.attrib.items()), text,
                [value for child in node if (value := node_identity(child)) is not None]]
    return {key: node_identity(parse(value)) if key == "xml" else
            " ".join(strip_comments(value).upper().split()) if isinstance(value, str) else value
            for key, value in submission.items()}
