"""Public MCP stdio transport and controlled OpenAI function adapter."""
from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
import json
from pathlib import Path
from time import perf_counter

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import PaginatedRequestParams

from .core import digest, encode, environment, mark_tainted, write_json
from .tasks import ORIENTATION
from .demo import DEMO_PROMPTS, DEMO_ORIENTATION

DOC_TOOLS = {"get_documentation_status", "search_manuals", "get_manual_topic"}
READ_TOOLS = {"get_status", "get_project_structure", "list_variables", "read_section",
              "get_language_reference"}
EDIT_TOOLS = {"write_st_logic", "build_project", "analyze_project", "save_project"}
DOC_GUIDANCE = ("For installed manuals, call get_documentation_status, search_manuals, "
                "then get_manual_topic; citations distinguish installation and manual versions. ")
_EDGE = {"type": "object", "properties": {"edge": {"type": "string", "enum": ["rising", "falling"]},
                                          "variable": {"type": "string"}},
         "required": ["edge", "variable"], "additionalProperties": False}
# Harness-local answer tools: structured submission removes formatting failures
# (fences, prose) from scoring; the content is graded exactly as before.
ANSWER_SCHEMAS = {
    "inspect": {"type": "object", "additionalProperties": False, "properties": {
        "task": {"type": "string"}, "section": {"type": "string"}, "language": {"type": "string"},
        "initialization_event": _EDGE, "initialization_expression": {"type": "string"},
        "decrement_event": _EDGE, "full_condition": {"type": "string"}, "empty_condition": {"type": "string"},
        "temperature": {"type": "object", "additionalProperties": False, "properties": {
            key: {"type": "string"} for key in ("conversion", "input", "converted", "comparison", "setpoint")},
            "required": ["conversion", "input", "converted", "comparison", "setpoint"]}},
        "required": ["task", "section", "language", "initialization_event", "initialization_expression",
                     "decrement_event", "full_condition", "empty_condition", "temperature"]},
    "io_mapping": {"type": "object", "additionalProperties": False, "properties": {
        "report": {"type": "string", "description": "Complete Markdown answer in the requested format"}},
        "required": ["report"]},
}
SUBMIT_DESCRIPTION = ("Submit the final answer for grading. Call with the complete answer; a later call "
                      "replaces the earlier one. Structure is validated; content is graded later.")


def schema_errors(schema: dict, value, path: str = "answer") -> list[str]:
    """Validate the small JSON-schema subset used by ANSWER_SCHEMAS."""
    if schema["type"] == "string":
        if not isinstance(value, str):
            return [f"{path} must be a string"]
        if "enum" in schema and value not in schema["enum"]:
            return [f"{path} must be one of {schema['enum']}"]
        return []
    if not isinstance(value, dict):
        return [f"{path} must be an object"]
    errors = [f"{path}.{key} is required" for key in schema["required"] if key not in value]
    errors += [f"{path}.{key} is not allowed" for key in value if key not in schema["properties"]]
    for key, child in schema["properties"].items():
        if key in value:
            errors += schema_errors(child, value[key], f"{path}.{key}")
    return errors


def answer_text(task: str, submitted: dict) -> str:
    return submitted["report"] if task == "io_mapping" else json.dumps(submitted)


def plain(value):
    return value.model_dump(mode="json", by_alias=False, exclude_none=True)


def tool_value(result) -> dict:
    if result.is_error:
        raise RuntimeError("MCP tool error: " + encode(plain(result)))
    if result.structured_content is not None:
        return result.structured_content
    for content in result.content:
        if content.type == "text":
            return json.loads(content.text)
    raise ValueError("Tool returned no structured object")


def visible_payload(raw: dict) -> dict:
    """Preserve errors and non-text blocks; remove only exact JSON text duplicates."""
    result = dict(raw)
    structured = result.get("structured_content")
    if structured is not None:
        blocks = []
        for block in result.get("content", []):
            try:
                if block.get("type") == "text" and json.loads(block["text"]) == structured:
                    continue
            except (ValueError, KeyError):
                pass
            blocks.append(block)
        result["content"] = blocks
    return result


class Evidence:
    def __init__(self, directory: Path, events):
        self.directory, self.events = directory, events

    def blob(self, value) -> str:
        ref = digest(value)
        target = self.directory / "blobs" / (ref + ".json")
        if not target.exists():
            write_json(target, value)
        return ref


class MCP:
    def __init__(self, condition: dict, config: dict, evidence: Evidence):
        self.condition, self.config, self.evidence = condition, config, evidence
        self.stack = AsyncExitStack()
        self.phase = "setup"
        self.tools = []
        self.tainted = False
        self.submitted = None

    def server_environment(self) -> dict:
        return environment(self.condition)

    async def bounded(self, operation, name: str):
        try:
            return await asyncio.wait_for(operation, self.config["tool_timeout"])
        except BaseException:
            # A disconnected client is not evidence the COM worker has stopped.
            self.tainted = True
            mark_tainted(Path(self.config["workspace"]), {"operation": name})
            raise

    async def __aenter__(self):
        try:
            parameters = StdioServerParameters(command=self.condition["command"],
                args=self.condition.get("args", []), cwd=self.condition["cwd"],
                env=self.server_environment())
            started = perf_counter()
            streams = await self.stack.enter_async_context(stdio_client(parameters))
            self.session = await self.stack.enter_async_context(ClientSession(*streams))
            init = await self.bounded(self.session.initialize(), "initialize")
            self.startup_seconds = perf_counter() - started
            self.initialization = plain(init)
            self.instructions = init.instructions or ""
            self.evidence.events.emit("initialize", elapsed=perf_counter() - started,
                                      result=self.initialization)
            started = perf_counter()
            cursor = None
            seen = set()
            while True:
                result = await self.bounded(self.session.list_tools(
                    params=PaginatedRequestParams(cursor=cursor) if cursor else None), "list_tools")
                self.tools.extend(plain(tool) for tool in result.tools)
                cursor = result.next_cursor
                if not cursor:
                    break
                if cursor in seen:
                    raise ValueError("Repeated tool discovery cursor")
                seen.add(cursor)
            self.evidence.events.emit("discovery", elapsed=perf_counter() - started,
                                      schemas_ref=self.evidence.blob(self.tools))
            self.discovery_seconds = perf_counter() - started
            return self
        except BaseException:
            await self.stack.aclose()
            raise

    async def __aexit__(self, *args):
        await self.stack.__aexit__(*args)

    async def call(self, name: str, arguments: dict):
        started = perf_counter()
        try:
            result = await self.bounded(self.session.call_tool(name, arguments), name)
        except BaseException as exc:
            self.evidence.events.emit("mcp_exception", phase=self.phase, tool=name,
                elapsed=perf_counter() - started, error=type(exc).__name__)
            raise
        raw = plain(result)
        visible = visible_payload(raw)
        outcome = {}
        if name == "build_project" and not result.is_error:
            build = tool_value(result)
            outcome["build_ok"] = build.get("build_state") == "built_ok" and not build.get("error")
        self.evidence.events.emit("mcp_call", phase=self.phase, tool=name, arguments=arguments,
            elapsed=perf_counter() - started, is_error=result.is_error,
            raw_ref=self.evidence.blob(raw), visible_ref=self.evidence.blob(visible),
            visible_bytes=len(encode(visible).encode()), **outcome)
        return result

    async def checked(self, name: str, /, **arguments):
        return tool_value(await self.call(name, arguments))

    def adapter(self, task: str) -> tuple[str, list]:
        demo = task in DEMO_PROMPTS
        self.demo_task = demo
        allowed = READ_TOOLS | (set() if task == "inspect" or demo else EDIT_TOOLS)
        if demo:
            allowed |= {"get_hardware", "export_xml", "list_data_types"}
        if self.condition["documentation"]:
            allowed |= DOC_TOOLS
        available = {tool["name"] for tool in self.tools}
        required = allowed.copy()
        if required - available:
            raise ValueError(f"Missing required tools: {sorted(required - available)}")
        # Only the known documentation recommendation is normalized in BOTH arms.
        # Unknown guidance changes are retained and fingerprinted, never guessed away.
        instructions = self.instructions.replace(DOC_GUIDANCE, "") + "\n" + (DEMO_ORIENTATION if demo else ORIENTATION)
        if any(name in instructions for name in DOC_TOOLS):
            raise ValueError("Unrecognized manual-tool guidance: update explicit normalization before comparing")
        schemas = [{"type": "function", "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool["input_schema"], "strict": False}
                   for tool in self.tools if tool["name"] in allowed]
        if task in ANSWER_SCHEMAS:
            schemas.append({"type": "function", "name": "submit_answer", "description": SUBMIT_DESCRIPTION,
                            "parameters": ANSWER_SCHEMAS[task], "strict": False})
        return instructions, schemas

    def submit(self, arguments: dict, schemas: list) -> dict:
        schema = next(tool["parameters"] for tool in schemas if tool["name"] == "submit_answer")
        errors = schema_errors(schema, arguments)
        self.evidence.events.emit("answer_submitted", phase=self.phase, accepted=not errors,
                                  answer_ref=self.evidence.blob(arguments), errors=errors)
        if errors:
            return {"is_error": True, "error": "Answer structure invalid: " + "; ".join(errors[:10])}
        self.submitted = arguments
        return {"is_error": False, "structured_content": {
            "accepted": True, "note": "Answer recorded for grading; finish with a brief confirmation."}}

    async def dispatch(self, name: str, arguments: dict, schemas: list) -> dict:
        if name not in {tool["name"] for tool in schemas}:
            return {"is_error": True, "error": "Tool unavailable under benchmark policy"}
        if name == "submit_answer":
            return self.submit(arguments, schemas)
        if name in {"read_section", "write_st_logic"} and not getattr(self, "demo_task", False):
            if arguments.get("task", "").upper() != "MAST" or arguments.get("section", "").lower() != "feeder":
                return {"is_error": True, "error": "Only MAST/Feeder is in scope"}
        if name == "write_st_logic" and arguments.get("declare"):
            return {"is_error": True, "error": "Declarations are fixed"}
        if name == "save_project" and arguments.get("path"):
            return {"is_error": True, "error": "Use save_project without a path"}
        return visible_payload(plain(await self.call(name, arguments)))
