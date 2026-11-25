"""Evaluator-only native references and single-fault mutants; require CE validation."""
from __future__ import annotations

from lxml import etree as ET

from .iec_artifact import envelope
from .iec_cases import Case

MUTANT_VECTOR = {"iec_st_clamp": 6, "iec_ld_latch": 4, "iec_fbd_hysteresis": 6,
                 "iec_sfc_sequence": 3, "iec_il_select": 13}


def program(source: str) -> str:
    return '<program><identProgram name="Candidate" type="section" task="MAST"/>' + source + '</program>'


def reference(case: Case, *, mutant=False) -> dict:
    """These are authored fixtures, not claims of installed CE compatibility."""
    if case.language == "ST":
        limit = 999 if mutant else 1000
        return {"helpers": {"LLM_Difference": "DINT"}, "st_source":
                "LLM_Difference := INT_TO_DINT(Raw) - INT_TO_DINT(Offset);\n"
                "IF LLM_Difference < 0 THEN Result := 0;\n"
                f"ELSIF LLM_Difference > {limit} THEN Result := {limit};\n"
                "ELSE Result := DINT_TO_INT(LLM_Difference); END_IF;"}
    if case.language == "IL":
        operator = "OR" if mutant else "XOR"
        body = f"LD SignalA\n{operator} SignalB\nOR OverrideCmd\nAND EnableCmd\nST Selected\n"
        return {"xml": envelope("IL", program("<ILSource>" + body + "</ILSource>"))}
    if case.language == "LD":
        def rung(contacts, coil):
            cells = ''.join(f'<contact typeContact="{kind}" contactVariableName="{name}"/>'
                            for name, kind in contacts)
            return (f'<typeLine>{cells}<HLink nbCells="{10 - len(contacts)}"/>'
                    f'<coil typeCoil="{coil}" coilVariableName="Running"/></typeLine>')
        start = rung([("StartCmd", "openContact"), ("Permit", "openContact")], "setCoil")
        stop = rung([("StopCmd", "openContact")], "resetCoil")
        permit = rung([("Permit", "closedContact")], "resetCoil")
        rungs = stop + permit + start if mutant else start + stop + permit
        return {"xml": envelope("LD", program('<LDSource nbColumns="11"><networkLD>' + rungs + '</networkLD></LDSource>'))}
    if case.language == "FBD":
        # Demand := EnableCmd AND (Low OR (Demand AND NOT High)). Each EF
        # publishes a scalar temporary, with explicit execution dependencies.
        helpers = {"LLM_Low": "BOOL", "LLM_High": "BOOL", "LLM_Hold": "BOOL", "LLM_On": "BOOL"}
        blocks = [
            ("LE_INT", [("IN1", "LevelValue", False), ("IN2", "30", False)], "LLM_Low"),
            ("GT_INT" if mutant else "GE_INT", [("IN1", "LevelValue", False), ("IN2", "70", False)], "LLM_High"),
            ("AND_BOOL", [("IN1", "Demand", False), ("IN2", "LLM_High", True)], "LLM_Hold"),
            ("OR_BOOL", [("IN1", "LLM_Low", False), ("IN2", "LLM_Hold", False)], "LLM_On"),
            ("AND_BOOL", [("IN1", "EnableCmd", False), ("IN2", "LLM_On", False)], "Demand"),
        ]
        source = ET.Element("FBDSource", nbRows="48", nbColumns="36")
        network = ET.SubElement(source, "networkFBD")
        for index, (kind, inputs, output) in enumerate(blocks, 1):
            block = ET.SubElement(network, "FFBBlock", instanceName=f".{index}", typeName=kind,
                                  additionnalPinNumber="0", enEnO="false", width="8", height="6")
            ET.SubElement(block, "objPosition", posX="10", posY=str((index - 1) * 8 + 1))
            description = ET.SubElement(block, "descriptionFFB", execAfter=f".{index - 1}" if index > 1 else "")
            ET.SubElement(description, "inputVariable", invertedPin="false", formalParameter="EN")
            for pin, value, inverted in inputs:
                ET.SubElement(description, "inputVariable", invertedPin=str(inverted).lower(),
                              formalParameter=pin, effectiveParameter=value)
            ET.SubElement(description, "outputVariable", invertedPin="false", formalParameter="ENO")
            ET.SubElement(description, "outputVariable", invertedPin="false", formalParameter="OUT", effectiveParameter=output)
        return {"helpers": helpers, "xml": envelope("FBD", program(ET.tostring(source, encoding="unicode")))}
    source = ET.Element("SFCProgram", areaNum="0", operatorCtrl="0")
    ET.SubElement(source, "identProgram", name="Candidate", type="section", task="MAST")
    chart = ET.SubElement(source, "chartSource", name="Chart")
    network = ET.SubElement(chart, "networkSFC")
    for index, name in enumerate(("Idle", "Active", "Completed")):
        step = ET.SubElement(network, "step", stepType="initialStep" if index == 0 else "step", stepName=name)
        ET.SubElement(step, "objPosition", posX="0", posY=str(index * 2))
        ET.SubElement(step, "literals", max="", min="", delay="")
        transition = ET.SubElement(network, "transition")
        ET.SubElement(transition, "objPosition", posX="0", posY=str(index * 2 + 1))
        condition = ET.SubElement(transition, "transitionCondition", invertLogic="false")
        ET.SubElement(condition, "variableName").text = ("LLM_StartOnly", "LLM_DoneOnly", "LLM_AckOnly")[index]
    jump = ET.SubElement(network, "jumpSFC", stepName="Idle")
    ET.SubElement(jump, "objPosition", posX="0", posY="6")
    start = "StartCmd AND NOT AckCmd" if mutant else "StartCmd AND NOT DoneCmd AND NOT AckCmd"
    return {"xml": envelope("SFC", ET.tostring(source, encoding="unicode")),
            "helpers": {"LLM_StartOnly": "BOOL", "LLM_DoneOnly": "BOOL", "LLM_AckOnly": "BOOL"},
            "pre": f"LLM_StartOnly := {start};\n"
                   "LLM_DoneOnly := DoneCmd AND NOT StartCmd AND NOT AckCmd;\n"
                   "LLM_AckOnly := AckCmd AND NOT StartCmd AND NOT DoneCmd;",
            "post": "Busy := Active.x;\nComplete := Completed.x;"}


def alternative_reference(case: Case) -> dict:
    """Common native authoring styles for policy/engineering regression checks."""
    data = reference(case)
    if case.language == "ST":
        data["st_source"] = (data["st_source"].replace(" < 0", " < DINT#0")
                             .replace(" > 1000", " > DINT#1000")
                             .replace("Result := 0", "Result := INT#0")
                             .replace("Result := 1000", "Result := INT#1000"))
        return data
    if case.language == "FBD":
        root = ET.fromstring(data["xml"].encode())
        blocks = list(root.iter("FFBBlock"))
        data["helpers"] = {"LLM_Low": "BOOL", "LLM_High": "BOOL", "LLM_Set": "BOOL",
                           "LLM_Reset": "BOOL", "LLM_Bistable": "RS"}
        # S := Enable AND Low; R1 := High OR NOT Enable. RS stores native state.
        for block, inputs, output in ((blocks[2], ("EnableCmd", "LLM_Low"), "LLM_Set"),
                                      (blocks[3], ("LLM_High", "EnableCmd"), "LLM_Reset")):
            pins = list(block.iter("inputVariable"))[1:]
            for pin, value in zip(pins, inputs):
                pin.set("effectiveParameter", value)
                pin.set("invertedPin", "true" if value == "EnableCmd" and output == "LLM_Reset" else "false")
            list(block.iter("outputVariable"))[-1].set("effectiveParameter", output)
        block = blocks[4]
        block.set("typeName", "RS")
        block.set("instanceName", "LLM_Bistable")
        block.set("width", "7")
        for pin, formal, value in zip(list(block.iter("inputVariable"))[1:], ("S", "R1"), ("LLM_Set", "LLM_Reset")):
            pin.set("formalParameter", formal)
            pin.set("effectiveParameter", value)
        list(block.iter("outputVariable"))[-1].set("formalParameter", "Q1")
        data["xml"] = ET.tostring(root, encoding="unicode")
        return data
    if case.language == "SFC":
        root = ET.fromstring(data["xml"].encode())
        program = root.find("SFCProgram")
        for step in root.iter("step"):
            name = step.get("stepName")
            action_name = "LLM_" + name + "Outputs"
            action = ET.Element("action", qualifier="NONE")
            ET.SubElement(ET.SubElement(action, "actionName"), "sectionName").text = action_name
            ET.SubElement(ET.SubElement(action, "tValue"), "tLiteral")
            step.insert(1, action)
            source = ET.SubElement(program, "actionSource", name=action_name)
            ET.SubElement(source, "STSource").text = (
                f"Busy := {str(name == 'Active').upper()};\nComplete := {str(name == 'Completed').upper()};")
        data["post"] = ""
        data["xml"] = ET.tostring(root, encoding="unicode")
        return data
    raise ValueError("No alternate style required for this case")
