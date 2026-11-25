"""Evaluator-only ordered fixtures from the IEC specification v0.1."""
from __future__ import annotations

from .iec_cases import CASES, Case

VERSION = "iec-fixtures-1"

# Inputs followed by evaluated outputs. BOOL table cells are decoded explicitly.
_ROWS = {
    "iec_st_clamp": [(110,10,100), (500,500,0), (99,100,0), (100,99,1),
                     (1099,100,999), (1100,100,1000), (1101,100,1000),
                     (-50,-100,50), (32767,-32768,1000), (-32768,32767,0)],
    "iec_ld_latch": [(0,0,1,0), (1,0,1,1), (0,0,1,1), (1,1,1,0),
                     (0,0,1,0), (1,0,1,1), (0,0,0,0), (0,0,1,0),
                     (1,0,0,0), (1,0,1,1), (0,1,1,0)],
    "iec_fbd_hysteresis": [(50,1,0), (31,1,0), (30,1,1), (50,1,1),
                           (69,1,1), (70,1,0), (69,1,0), (29,1,1),
                           (29,0,0), (50,1,0), (30,1,1), (71,1,0)],
    "iec_sfc_sequence": [(0,0,0,0,0), (0,1,0,0,0), (1,1,0,0,0),
                         (1,0,0,1,0), (0,0,0,1,0), (0,0,1,1,0),
                         (0,1,1,1,0), (0,1,0,0,1), (0,0,0,0,1),
                         (1,0,0,0,1), (1,1,1,0,1), (0,0,1,0,0), (1,0,0,1,0)],
    "iec_il_select": [(0,0,0,0,0), (0,0,0,1,0), (0,0,1,1,1), (0,0,1,0,0),
                      (0,1,0,1,1), (0,1,0,0,0), (0,1,1,0,0), (0,1,1,1,1),
                      (1,0,0,1,1), (1,0,0,0,0), (1,0,1,0,0), (1,0,1,1,1),
                      (1,1,0,1,0), (1,1,0,0,0), (1,1,1,1,1), (1,1,1,0,0)],
}


def valid_value(value, kind: str) -> bool:
    if kind == "BOOL":
        return type(value) is bool
    if kind in {"INT", "DINT"}:
        limit = 2 ** (15 if kind == "INT" else 31)
        return type(value) is int and -limit <= value < limit
    return False


def vectors(case: Case) -> list[dict]:
    fields = case.inputs + case.outputs
    result = []
    for row in _ROWS[case.id]:
        if len(row) != len(fields):
            raise ValueError("Invalid fixture width")
        values = {}
        for (name, kind), value in zip(fields, row):
            if kind == "BOOL":
                if type(value) is not int or value not in (0, 1):
                    raise ValueError("Invalid fixture BOOL")
                value = bool(value)
            if not valid_value(value, kind):
                raise ValueError("Invalid fixture value")
            values[name] = value
        result.append({"inputs": {n: values[n] for n, _ in case.inputs},
                       "outputs": {n: values[n] for n, _ in case.outputs}})
    return result


def private_contract() -> dict:
    return {"version": VERSION, "cases": {key: vectors(case) for key, case in CASES.items()}}
