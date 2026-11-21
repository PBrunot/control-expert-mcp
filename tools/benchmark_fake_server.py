"""Synthetic stdio fixture server for offline tests; never imports the COM bridge."""
from pathlib import Path
import xml.etree.ElementTree as ET

from mcp.server.mcpserver import MCPServer

server = MCPServer("Synthetic benchmark", version="test", instructions="Offline synthetic fixture server.")
xml = ""
project_path = ""


@server.tool()
def get_status() -> dict:
    return {"server_version": "16.4 synthetic", "session": "application open" if xml else "no application open"}


@server.tool()
def new_project(cpu_part_number: str, cpu_version: str) -> dict:
    global xml, project_path
    xml, project_path = "", ""
    return {"created": True}


@server.tool()
def import_xml(kind: str, task: str, xml_content: str) -> dict:
    global xml
    ET.fromstring(xml_content)
    xml = xml_content
    return {"imported": True}


@server.tool()
def open_project(path: str) -> dict:
    global xml, project_path
    xml, project_path = Path(path).read_text(encoding="utf-8"), path
    return {"opened": path}


@server.tool()
def close_project(save: bool = False) -> dict:
    global xml
    if save:
        save_project()
    xml = ""
    return {"closed": True}


@server.tool()
def save_project(path: str = "") -> dict:
    global project_path
    project_path = path or project_path
    Path(project_path).write_text(xml, encoding="utf-8")
    return {"saved_as": project_path}


@server.tool()
def read_section(task: str, section: str) -> dict:
    return {"task": task, "section": section, "language": "ST", "xml": xml}


@server.tool()
def write_st_logic(task: str, section: str, st_source: str, declare: str = "") -> dict:
    global xml
    root = ET.fromstring(xml)
    root.find(".//STSource").text = st_source
    xml = ET.tostring(root, encoding="unicode")
    return {"written": True}


@server.tool()
def export_xml(kind: str) -> dict:
    return {"xml": xml, "kind": kind}


@server.tool()
def build_project(rebuild_all: bool = False) -> dict:
    if "CE_BENCH_UNDEFINED_TEMP_7F93" in xml:
        return {"build_state": "not_built", "error": "synthetic undefined identifier",
                "diagnostics_output": "Undefined CE_BENCH_UNDEFINED_TEMP_7F93",
                "diagnostics_available": True, "diagnostics_capture": {"freshness": "changed"}}
    return {"build_state": "built_ok", "diagnostics_available": True,
            "diagnostics_capture": {"freshness": "unchanged", "attribution": "unverified"}}


@server.tool()
def analyze_project() -> dict:
    return build_project()


@server.tool()
def get_project_structure() -> dict:
    return {"tasks": [{"name": "MAST", "sections": ["Feeder"]}]}


@server.tool()
def list_variables() -> dict:
    return {"variables": [node.attrib for node in ET.fromstring(xml).iter("variables")]}


@server.tool()
def get_language_reference(language: str) -> dict:
    return {"language": language, "text": "Synthetic reference"}


@server.tool()
def get_documentation_status() -> dict:
    return {"ready": True, "freshness": "current", "synthetic": True}


@server.tool()
def search_manuals(query: str) -> dict:
    return {"results": []}


@server.tool()
def get_manual_topic(topic_id: str) -> dict:
    return {"text": "Synthetic manual"}


if __name__ == "__main__":
    server.run(transport="stdio")
