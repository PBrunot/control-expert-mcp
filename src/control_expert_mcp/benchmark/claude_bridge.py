"""Stdio MCP relay that lets the Claude Code CLI call the harness's MCP session.

Claude Code spawns this server. Tool schemas are the benchmark-filtered set and
every call is forwarded to the harness over a loopback socket, so dispatch policy,
evidence and grading stay identical to the Responses API providers.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os

import anyio
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

STREAM_LIMIT = 1 << 26


async def forward(port: int, token: str, name: str, arguments: dict) -> dict:
    reader, writer = await asyncio.open_connection("127.0.0.1", port, limit=STREAM_LIMIT)
    try:
        writer.write((json.dumps({"token": token, "name": name, "arguments": arguments}) + "\n").encode())
        await writer.drain()
        return json.loads(await reader.readline())
    finally:
        writer.close()


async def serve(port: int, schemas_path: str):
    token = os.environ["CE_BENCH_BRIDGE_TOKEN"]
    with open(schemas_path, encoding="utf-8") as handle:
        schemas = json.load(handle)
    tools = [types.Tool(name=s["name"], description=s.get("description", ""), input_schema=s["parameters"])
             for s in schemas]

    async def list_tools(context, params):
        return types.ListToolsResult(tools=tools)

    async def call_tool(context, params):
        reply = await forward(port, token, params.name, params.arguments or {})
        return types.CallToolResult(content=[types.TextContent(type="text", text=reply["output"])],
                                    is_error=reply["is_error"])

    server = Server("control-expert-bench", on_list_tools=list_tools, on_call_tool=call_tool)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--schemas", required=True)
    args = parser.parse_args()
    anyio.run(serve, args.port, args.schemas)


if __name__ == "__main__":
    main()
