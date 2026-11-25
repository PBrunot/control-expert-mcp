"""Public IEC task contracts. Evaluation vectors deliberately live elsewhere."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re


@dataclass(frozen=True)
class Case:
    id: str
    language: str
    inputs: tuple[tuple[str, str], ...]
    outputs: tuple[tuple[str, str], ...]
    requirement: str
    initial: tuple[tuple[str, bool | int], ...]
    cycles: int = 1

    def public(self) -> dict:
        return asdict(self)


CASES = {
    c.id: c for c in (
        Case("iec_st_clamp", "ST", (("Raw", "INT"), ("Offset", "INT")),
             (("Result", "INT"),),
             "Each scan compute the mathematical difference Raw - Offset and clamp it to "
             "[0, 1000]. Support the entire INT input domain, including differences "
             "outside INT range. Previous Result is irrelevant.", (("Result", 0),)),
        Case("iec_ld_latch", "LD", (("StartCmd", "BOOL"), ("StopCmd", "BOOL"), ("Permit", "BOOL")),
             (("Running", "BOOL"),),
             "StopCmd OR NOT Permit clears Running in the same scan, even with StartCmd. "
             "Otherwise StartCmd sets Running; otherwise retain Running. Start is level "
             "sensitive, including when Permit returns while Start remains high.", (("Running", False),)),
        Case("iec_fbd_hysteresis", "FBD", (("LevelValue", "INT"), ("EnableCmd", "BOOL")),
             (("Demand", "BOOL"),),
             "When disabled clear Demand in the same scan. When enabled, LevelValue <= 30 "
             "sets Demand; LevelValue >= 70 clears it; intermediate levels retain it.", (("Demand", False),)),
        Case("iec_sfc_sequence", "SFC", (("StartCmd", "BOOL"), ("DoneCmd", "BOOL"), ("AckCmd", "BOOL")),
             (("Busy", "BOOL"), ("Complete", "BOOL")),
             "Use a native three-step chart, initially Idle, then Active, then Completed. "
             "Idle -> Active only with StartCmd alone; Active -> Completed only with "
             "DoneCmd alone; Completed -> Idle only with AckCmd alone. All other command "
             "combinations retain the current step. Commands are level sensitive. "
             "Idle outputs Busy=FALSE, Complete=FALSE; Active TRUE,FALSE; Completed "
             "FALSE,TRUE. A local combinational helper may calculate transition "
             "conditions or publish step state; the native chart must govern the sequence.",
             (("Busy", False), ("Complete", False)), 4),
        Case("iec_il_select", "IL", (("SignalA", "BOOL"), ("SignalB", "BOOL"),
                                     ("OverrideCmd", "BOOL"), ("EnableCmd", "BOOL")),
             (("Selected", "BOOL"),),
             "Each scan set Selected to EnableCmd AND (OverrideCmd OR (SignalA XOR SignalB)). "
             "Disabled always means FALSE.", (("Selected", False),)),
    )
}

ORIENTATION = (
    "Implement only the case's IEC_<language>_Candidate section in MAST in the requested native language. The harness has "
    "opened a disposable project with the typed public interface precreated. "
    "Use the exposed tools; no automatic MCP resources/prompts are loaded. "
    "Bench_ is reserved and inaccessible. Helpers may be new unlocated scalar "
    "IEC_<language>_LLM_* BOOL/INT/DINT declarations; FBD also permits native RS/SR instances. "
    "Inputs are read-only. Do not access system "
    "variables, addresses, external devices, files or other sections. For SFC "
    "inline actions/transitions and combinational IEC_SFC_LLM_Pre and "
    "IEC_SFC_LLM_Post helpers are allowed; helpers cannot replace chart state. "
    "Build and repair using public diagnostics, then save. Independent grading "
    "takes place only after your artifact has been frozen."
)


def task_prompt(case: Case) -> str:
    """Project only public data; never import the private fixture module here."""
    public = case.public()
    public["inputs"] = [(physical_name(case, n), t) for n, t in case.inputs]
    public["outputs"] = [(physical_name(case, n), t) for n, t in case.outputs]
    public["initial"] = [(physical_name(case, n), v) for n, v in case.initial]
    public["requirement"] = translate(case, case.requirement)
    public["section"] = physical_name(case, "Candidate")
    public["helpers_prefix"] = physical_name(case, "LLM_")
    return json.dumps(public, ensure_ascii=False) + (
        f"\nA vector remains stable for {case.cycles} consecutive useful MAST scans. "
        f"Outputs are evaluated at the end of scan {case.cycles}, after the chart "
        "and any output publication. State persists between vectors; each new "
        "execution starts clean. Deliver the saved engineering project."
    )


def physical_name(case: Case, name: str) -> str:
    return "IEC_" + case.language + "_" + name


def translate(case: Case, text: str, *, reverse=False) -> str:
    """Map only benchmark identifiers; fixture/grader names stay stable."""
    known = {n.casefold(): n for n, _ in case.inputs + case.outputs}
    known.update({n.casefold(): n for n in ("Candidate", "Idle", "Active", "Completed", "LLM_Pre", "LLM_Post")})
    prefix = "IEC_" + case.language + "_"

    def replace(match):
        token = match.group()
        if reverse:
            if token.casefold().startswith(prefix.casefold()):
                suffix = token[len(prefix):]
                return known.get(suffix.casefold(), suffix)
            return token
        if token.casefold() in known:
            return prefix + known[token.casefold()]
        if token.upper().startswith("LLM_"):
            return prefix + token
        return token
    return re.sub(r"[A-Za-z_][A-Za-z0-9_]*", replace, text)


def map_submission(case: Case, value: dict, *, reverse=False) -> dict:
    if not isinstance(value, dict) or any(not isinstance(item, dict if key == "helpers" else str)
                                          for key, item in value.items()):
        raise ValueError("Candidate fields must be text; helpers must be an object")
    return {key: ({translate(case, n, reverse=reverse): kind for n, kind in item.items()}
                  if key == "helpers" else translate(case, item, reverse=reverse))
            for key, item in value.items()}


def select(selected: str) -> list[Case]:
    if selected == "all":
        return list(CASES.values())
    if selected not in CASES:
        raise ValueError("Unknown IEC case: " + selected)
    return [CASES[selected]]
