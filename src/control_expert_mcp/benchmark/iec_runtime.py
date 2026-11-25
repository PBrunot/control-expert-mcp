"""IEC-only project lifecycle and model tool boundary. No fixture data is exposed."""
from __future__ import annotations

from pathlib import Path

from lxml import etree as ET

from .core import environment
from .iec_artifact import parse, validate_submission
from .iec_cases import ORIENTATION, Case, map_submission, physical_name, translate
from .runner import clean_build, verify_version
from .transport import DOC_GUIDANCE, DOC_TOOLS, MCP, plain, visible_payload

SUBMIT = {"type": "function", "name": "submit_candidate", "strict": False,
          "description": "Replace native MAST/IEC_<language>_Candidate. Supply st_source for ST, otherwise inline section exchange XML "
                         "without dataBlock or SectionOrder metadata. FBD grids: 6..36 columns, 24..144 rows; never use 40 columns. "
                         "Optional scalar IEC_<language>_LLM_* helpers; FBD also permits declared RS/SR bistables. "
                         "SFC can publish outputs from scoped inline native actions or a combinational post helper. "
                         "Only local scalar logic is supported. Build afterwards and inspect diagnostics.",
          "parameters": {"type": "object", "properties": {
              "st_source": {"type": "string"}, "xml": {"type": "string"},
              "helpers": {"type": "object", "additionalProperties": {"type": "string", "enum": ["BOOL", "INT", "DINT", "RS", "SR"]}},
              "pre": {"type": "string"}, "post": {"type": "string"}}, "additionalProperties": False}}


async def idle(mcp):
    if (await mcp.checked("get_status")).get("session") != "no application open":
        raise RuntimeError("Use a dedicated idle CE session; another project is open")


async def inventory(mcp) -> dict:
    value = await mcp.checked("list_variables", max_results=1000000)
    if value.get("returned") != value.get("total_variables"):
        raise RuntimeError("Incomplete declaration inventory")
    return {v["name"]: v for v in value["variables"]}


async def interface(mcp, case: Case, helpers: dict, baseline: dict) -> None:
    variables = await inventory(mcp)
    expected = {physical_name(case, n): t for n, t in (dict(case.inputs + case.outputs) | helpers).items()}
    if case.language == "SFC":
        expected[physical_name(case, "Candidate")] = "SFCCHART_STATE"
        expected.update({physical_name(case, n): "SFCSTEP_STATE" for n in ("Idle", "Active", "Completed")})
    for name, original in baseline.items():
        if variables.get(name) != original:
            raise ValueError("Demo declaration changed: " + name)
    variables = {n: v for n, v in variables.items() if n not in baseline}
    if set(variables) != set(expected):
        raise ValueError("Unexpected or missing project declarations")
    for name, kind in expected.items():
        if variables[name].get("type") != kind or variables[name].get("address"):
            raise ValueError("Wrong type or located variable: " + name)


async def create_public(mcp, case: Case, config: dict, path: Path) -> dict:
    await idle(mcp)
    await mcp.checked("open_project", path=str(path))
    status = await verify_version(mcp, config)
    cpu = status.get("project", {}).get("cpu", {})
    if any(cpu.get(k) != v for k, v in config["cpu"].items()):
        raise RuntimeError("Unexpected CPU in IEC project")
    structure = await mcp.checked("get_project_structure")
    baseline = await inventory(mcp)
    if any(n.casefold().startswith(("iec_", "bench_")) for n in baseline):
        raise ValueError("Demo variable namespace collision")
    if any(s["name"].casefold().startswith(("iec_", "bench_")) for t in structure["tasks"] for s in t["sections"]):
        raise ValueError("Demo section namespace collision")
    for name, kind in case.inputs + case.outputs:
        await mcp.checked("create_variable", name=physical_name(case, name), type_name=kind, initial_value="FALSE" if kind == "BOOL" else "0")
    if case.language == "SFC":
        await mcp.checked("write_st_logic", task="MAST", section=physical_name(case, "LLM_Pre"), st_source="(* combinational helper *)")
    await mcp.checked("create_section", task="MAST", name=physical_name(case, "Candidate"), language=case.language)
    if case.language == "SFC":
        await mcp.checked("write_st_logic", task="MAST", section=physical_name(case, "LLM_Post"), st_source="(* step publication *)")
    await order(mcp, [physical_name(case, n) for n in (["LLM_Pre", "Candidate", "LLM_Post"] if case.language == "SFC" else ["Candidate"])], structure)
    await mcp.checked("save_project", path=str(path))
    return {"variables": baseline, "structure": structure}


async def order(mcp, names: list[str], baseline: dict) -> None:
    structure = await mcp.checked("get_project_structure")
    import copy
    mast = next((t for t in baseline["tasks"] if t["name"] == "MAST"), None)
    if mast is None:
        raise ValueError("Demo has no MAST task")
    actual_mast = next((t for t in structure["tasks"] if t["name"] == "MAST"), {})
    original_names = [s["name"] for s in mast["sections"]]
    if [s["name"] for s in actual_mast.get("sections", [])] != original_names + names:
        raise RuntimeError("MAST section order or task inventory differs from capture contract")
    # Preserve every other task and the original section languages/scan settings.
    actual = copy.deepcopy(structure)
    next(t for t in actual["tasks"] if t["name"] == "MAST")["sections"] = actual_mast["sections"][:len(original_names)]
    if actual != baseline:
        raise RuntimeError("Demo task structure changed")


async def install(mcp, case: Case, submission: dict) -> dict:
    submission = validate_submission(case, submission)
    existing = await inventory(mcp)
    for name, kind in submission["helpers"].items():
        physical = physical_name(case, name)
        if physical not in existing:
            await mcp.checked("create_variable", name=physical, type_name=kind,
                              initial_value="FALSE" if kind == "BOOL" else "0" if kind in {"INT", "DINT"} else "")
        elif existing[physical].get("type") != kind:
            raise ValueError("Helper type cannot change")
    if case.language == "ST":
        await mcp.checked("write_st_logic", task="MAST", section=physical_name(case, "Candidate"), st_source=translate(case, submission["st_source"]))
    else:
        xml = translate(case, submission["xml"])
        check = await mcp.checked("validate_xml", xml_content=xml)
        if check.get("valid") is not True:
            raise ValueError("Invalid native exchange XML: " + str(check.get("errors", [])))
        await mcp.checked("import_xml", kind="section", task="MAST", xml_content=xml)
    if case.language == "SFC":
        for section, key in (("LLM_Pre", "pre"), ("LLM_Post", "post")):
            await mcp.checked("write_st_logic", task="MAST", section=physical_name(case, section), st_source=translate(case, submission[key]) or "(* empty *)")
    return submission


async def inspect(mcp, case: Case, helpers: dict, baseline: dict) -> dict:
    await interface(mcp, case, helpers, baseline["variables"])
    expected = ["LLM_Pre", "Candidate", "LLM_Post"] if case.language == "SFC" else ["Candidate"]
    await order(mcp, [physical_name(case, n) for n in expected], baseline["structure"])
    return await extract(mcp, case, helpers)


async def extract(mcp, case: Case, helpers: dict) -> dict:
    """Read native executable source from the actual engineering project."""
    exported = await mcp.checked("read_section", task="MAST", section=physical_name(case, "Candidate"))
    if exported.get("language") != case.language:
        raise ValueError("Engineering section has wrong native language")
    root = parse(translate(case, exported["xml"], reverse=True))
    # SectionOrder is an absolute position in this particular demo copy. CE
    # adds it on export; it must not move a section when transporting logic
    # into the private project with its own verified capture order.
    for identifier in root.iter("identProgram"):
        identifier.attrib.pop("SectionOrder", None)
    # CE includes referenced declarations in section exports. Inspect the real
    # project inventory above, then transport executable content only.
    for block in list(root.findall("dataBlock")):
        root.remove(block)
    submission = {"helpers": helpers}
    if case.language == "ST":
        sources = root.findall(".//STSource")
        if len(sources) != 1:
            raise ValueError("Missing ST source")
        submission["st_source"] = sources[0].text or ""
    else:
        submission["xml"] = ET.tostring(root, encoding="unicode")
    if case.language == "SFC":
        for section, key in (("LLM_Pre", "pre"), ("LLM_Post", "post")):
            helper = parse(translate(case, (await mcp.checked("read_section", task="MAST", section=physical_name(case, section)))["xml"], reverse=True))
            sources = helper.findall(".//STSource")
            if len(sources) != 1:
                raise ValueError("Missing SFC helper")
            submission[key] = sources[0].text or ""
    return validate_submission(case, submission)


class IECMCP(MCP):
    """Only a public pre-opened project is reachable during model generation."""
    def __init__(self, condition, config, evidence, case: Case):
        super().__init__(condition, config, evidence)
        self.case = case
        self.helpers = {}
        self.frozen = False
        self.submitted = False

    def adapter(self, task):
        allowed = {"read_section", "get_project_structure", "list_variables", "get_language_reference",
                   "analyze_project", "build_project", "save_project"}
        if self.condition["documentation"]:
            allowed |= DOC_TOOLS
        if allowed - {t["name"] for t in self.tools}:
            raise ValueError("Required IEC authoring tools missing")
        tools = [{"type": "function", "name": t["name"], "description": t.get("description", ""),
                  "parameters": t["input_schema"], "strict": False} for t in self.tools if t["name"] in allowed]
        instructions = self.instructions.replace(DOC_GUIDANCE, "")
        if any(name in instructions for name in DOC_TOOLS):
            raise ValueError("Unrecognized documentation guidance")
        return instructions + "\n" + ORIENTATION, [*tools, SUBMIT]

    async def dispatch(self, name, arguments, schemas):
        if self.frozen or name not in {t["name"] for t in schemas}:
            return {"is_error": True, "error": "Tool unavailable under IEC policy"}
        try:
            if name == "submit_candidate":
                submission = validate_submission(self.case, map_submission(self.case, arguments, reverse=True))
                for helper, kind in self.helpers.items():
                    if submission["helpers"].get(helper) != kind:
                        raise ValueError("Retain previously declared helper names/types")
                # Track partially installed helpers too: a failed import is not
                # evidence that preceding declarations rolled back.
                self.helpers.update(submission["helpers"])
                await install(self, self.case, submission)
                self.submitted = True
                return {"structured_content": {"submitted": True}, "is_error": False}
            if name == "read_section" and (arguments.get("task") != "MAST" or arguments.get("section") not in
                    {physical_name(self.case, n) for n in ({"Candidate", "LLM_Pre", "LLM_Post"} if self.case.language == "SFC" else {"Candidate"})}):
                raise ValueError("Only candidate and permitted helpers are readable")
            if name == "save_project" and arguments:
                raise ValueError("Save without a path")
            if name == "get_language_reference" and arguments.get("language") not in {self.case.language, "ST"}:
                raise ValueError("Only this case's language reference is available")
            if name == "get_project_structure":
                value = await self.checked(name, **arguments)
                for task in value.get("tasks", []):
                    task["sections"] = [s for s in task["sections"] if s["name"].startswith("IEC_" + self.case.language + "_")]
                return {"structured_content": value, "is_error": False}
            if name == "list_variables":
                value = await inventory(self)
                variables = [v for n, v in value.items() if n.startswith("IEC_" + self.case.language + "_")]
                return {"structured_content": {"variables": variables, "returned": len(variables), "total_variables": len(variables)}, "is_error": False}
            return visible_payload(plain(await self.call(name, arguments)))
        except (ValueError, RuntimeError) as exc:
            if self.tainted:
                raise
            return {"is_error": True, "error": str(exc)}


class EvaluationMCP(MCP):
    def server_environment(self):
        return {**environment(self.condition), "CE_MCP_ENABLE_ONLINE": "1"}
