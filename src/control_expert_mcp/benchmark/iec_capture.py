"""In-task scalar capture generation and stable OPC retrieval for the IEC suite."""
from __future__ import annotations

import asyncio
from time import monotonic

from .iec_cases import Case, physical_name, translate
from .iec_fixtures import valid_value, vectors

PROTOCOL = "iec-scalar-buffer-1"


class CaptureDataError(ValueError):
    """A read has not yet supplied trusted values for all requested tags."""


class CaptureIdentityError(ValueError):
    """OFS has not yet resolved the freshly downloaded application identity."""


class RecordingClient:
    """Record actual OPC replies, including unsuccessful readiness reads."""
    def __init__(self, client, evidence):
        self.client, self.evidence = client, evidence

    def read(self, tags):
        response = self.client.read(tags)
        self.evidence.events.emit("opc_read", tags=tags, response_ref=self.evidence.blob(response))
        return response

    def write(self, values):
        response = self.client.write(values)
        self.evidence.events.emit("opc_write", values=values, response_ref=self.evidence.blob(response))
        return response
CONTROL = {"Bench_Start": "BOOL", "Bench_Ready": "BOOL", "Bench_Done": "BOOL",
           "Bench_Active": "BOOL", "Bench_Initialized": "BOOL", "Bench_Vector": "DINT",
           "Bench_Cycle": "DINT", "Bench_Count": "DINT", "Bench_RunId": "DINT", "Bench_ArtifactId": "DINT"}


def literal(value) -> str:
    return str(value).upper() if type(value) is bool else str(value)


def layout(case: Case) -> list[dict]:
    return [{"vector": v, "cycle": c, "prefix": f"Bench_S{(v - 1) * case.cycles + c}"}
            for v in range(1, len(vectors(case)) + 1) for c in range(1, case.cycles + 1)]


def instrument(case: Case, run_id: int, artifact_id: int) -> dict:
    """Apply a complete input vector before the candidate; record after it.

    Literals preload the PLC program, never the expected outputs. The host only
    writes Bench_Start after validating ready/identity/initial public outputs.
    """
    if any(type(i) is not int or not 0 < i < 2**31 for i in (run_id, artifact_id)):
        raise ValueError("Positive DINT capture identities required")
    declarations = dict(CONTROL)
    for index, vector in enumerate(vectors(case), 1):
        declarations.update({f"Bench_V{index}_{n}": t for n, t in case.inputs})
    for row in layout(case):
        declarations.update({row["prefix"] + "_" + n: t for n, t in case.inputs + case.outputs})
        declarations[row["prefix"] + "_Vector"] = "DINT"
        declarations[row["prefix"] + "_Cycle"] = "DINT"
    before = ["IF NOT Bench_Initialized THEN", f"Bench_RunId := {run_id};",
              f"Bench_ArtifactId := {artifact_id};", "Bench_Vector := 1; Bench_Cycle := 1;",
              "Bench_Count := 0; Bench_Done := FALSE;"]
    for index, vector in enumerate(vectors(case), 1):
        before += [f"Bench_V{index}_{n} := {literal(value)};" for n, value in vector["inputs"].items()]
    before += ["Bench_Initialized := TRUE;", "END_IF;", "Bench_Active := Bench_Start AND NOT Bench_Done;",
              "Bench_Ready := NOT Bench_Start AND NOT Bench_Done;", "IF Bench_Active THEN", "CASE Bench_Vector OF"]
    for index, row in enumerate(vectors(case), 1):
        before.append(f"{index}: " + " ".join(f"{n} := Bench_V{index}_{n};" for n in row["inputs"]))
    before += ["END_CASE;", "ELSE", "IF NOT Bench_Done THEN"]
    before += [f"{n} := {literal(False if kind == 'BOOL' else 0)};" for n, kind in case.inputs]
    before += ["END_IF;", "END_IF;"]
    after = ["IF Bench_Active THEN", "CASE Bench_Count OF"]
    for index, row in enumerate(layout(case)):
        prefix = row["prefix"]
        assignments = [f"{prefix}_{n} := {n};" for n, _ in case.inputs + case.outputs]
        assignments += [f"{prefix}_Vector := Bench_Vector;", f"{prefix}_Cycle := Bench_Cycle;"]
        after.append(f"{index}: " + " ".join(assignments))
    after += ["END_CASE;", "Bench_Count := Bench_Count + 1;",
              f"IF Bench_Cycle = {case.cycles} THEN",
              "Bench_Cycle := 1; Bench_Vector := Bench_Vector + 1;",
              "ELSE Bench_Cycle := Bench_Cycle + 1; END_IF;",
              f"IF Bench_Count = {len(layout(case))} THEN Bench_Done := TRUE; END_IF;", "END_IF;"]
    return {"protocol": PROTOCOL, "declarations": declarations,
            "before": translate(case, "\n".join(before)), "after": translate(case, "\n".join(after))}


async def read_good(client, tags: list[str]) -> dict:
    response = await asyncio.to_thread(client.read, tags)
    if response.get("errors") or any(response.get("samples", {}).get(t, {}).get("good") is not True
                                      or t not in response.get("values", {}) for t in tags):
        bad = [t for t in tags if response.get("samples", {}).get(t, {}).get("good") is not True
               or t not in response.get("values", {})]
        raise CaptureDataError("Missing or bad-quality OPC data: " + ", ".join(bad[:8]) +
                               "; errors=" + str(response.get("errors", {}))[:500])
    return response["values"]


def decode(value, kind: str):
    # OPC DA providers may encode BOOL as VARIANT_BOOL or an explicit 0/1.
    if kind == "BOOL" and type(value) is int and value in (0, 1, -1):
        return value != 0
    if not valid_value(value, kind):
        raise ValueError("Malformed OPC " + kind)
    return value


async def acquire(client, case: Case, run_id: int, artifact_id: int, *, timeout=30.0,
                  clock=monotonic, sleep=asyncio.sleep) -> dict:
    started = clock()
    controls = ["Bench_RunId", "Bench_ArtifactId", "Bench_Ready", "Bench_Done", "Bench_Count"]

    async def good(tags):
        # No writes are retried. The PLC owns the timeline and freezes the
        # buffer, so bounded read-only readiness polling cannot skip a scan.
        while True:
            try:
                return await read_good(client, tags)
            except CaptureDataError as exc:
                if clock() - started >= timeout:
                    raise TimeoutError("OFS readiness deadline: " + str(exc)) from exc
                await sleep(.1)

    def identity(values):
        if (decode(values["Bench_RunId"], "DINT") != run_id
                or decode(values["Bench_ArtifactId"], "DINT") != artifact_id):
            raise CaptureIdentityError("Stale or foreign PLC capture identity")

    while True:
        status = await good(controls)
        try:
            identity(status)
        except CaptureIdentityError:
            if clock() - started >= timeout:
                raise
            await sleep(.1)
            continue
        if decode(status["Bench_Done"], "BOOL"):
            raise ValueError("Already completed before start")
        if decode(status["Bench_Ready"], "BOOL"):
            break
        if clock() - started >= timeout:
            raise TimeoutError("PLC capture did not become ready")
        await sleep(.05)
    if decode(status["Bench_Count"], "DINT") != 0:
        raise ValueError("Capture not reset")
    initial = await good([physical_name(case, n) for n, _ in case.outputs])
    for name, kind in case.outputs:
        if decode(initial[physical_name(case, name)], kind) != dict(case.initial)[name]:
            raise ValueError("Initial state not clean: " + name)
    written = await asyncio.to_thread(client.write, {"Bench_Start": True})
    if written.get("errors") or written.get("written", {}).get("Bench_Start") is not True:
        raise ValueError("Capture start not acknowledged")
    while True:
        status = await good(controls)
        identity(status)
        if decode(status["Bench_Done"], "BOOL"):
            break
        if clock() - started >= timeout:
            raise TimeoutError("PLC capture did not finish")
        await sleep(.05)
    rows = layout(case)
    if decode(status["Bench_Count"], "DINT") != len(rows):
        raise ValueError("Incomplete PLC buffer")
    tags = [r["prefix"] + "_" + n for r in rows
            for n in ["Vector", "Cycle"] + [n for n, _ in case.inputs + case.outputs]]
    values = await good(tags)
    final = await good(controls)
    if final != status:
        raise ValueError("Capture changed during readout")
    snapshots = []
    for row in rows:
        prefix = row["prefix"] + "_"
        snapshots.append({"vector": decode(values[prefix + "Vector"], "DINT"),
                          "cycle": decode(values[prefix + "Cycle"], "DINT"), "good": True,
                          "inputs": {n: decode(values[prefix + n], t) for n, t in case.inputs},
                          "outputs": {n: decode(values[prefix + n], t) for n, t in case.outputs}})
    return {"protocol": PROTOCOL, "case_id": case.id, "run_id": run_id, "artifact_id": artifact_id,
            "done": True, "count": len(rows), "mode": "all_cycles", "snapshots": snapshots}
