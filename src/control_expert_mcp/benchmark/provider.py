"""Stateless Responses API loop; provider usage is never estimated."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sys
import tempfile
from time import perf_counter

from .core import encode
from .tasks import PROMPTS
from .demo import DEMO_PROMPTS

CONNECTION_RETRY_DELAYS = (1.0, 2.0)


def connection_retry_policy() -> dict:
    """Describe the explicit API-only retry policy for campaign provenance."""
    return {"error": "APIConnectionError", "max_retries": len(CONNECTION_RETRY_DELAYS),
            "backoff_seconds": list(CONNECTION_RETRY_DELAYS), "sdk_retries": 0,
            "mcp_retries": 0}


def retryable_connection_error(error: BaseException) -> bool:
    """Keep the provider SDK optional for offline commands and tests."""
    try:
        from openai import APIConnectionError
    except ImportError:
        return False
    return isinstance(error, APIConnectionError)


class Usage:
    FIELDS = ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens")

    def __init__(self):
        self.totals = dict.fromkeys(self.FIELDS, 0)
        self.known = dict.fromkeys(self.FIELDS, True)
        self.requests = 0

    def add(self, usage: dict | None):
        self.requests += 1
        usage = usage or {}
        fields = {**usage,
            "cached_input_tokens": (usage.get("input_tokens_details") or {}).get("cached_tokens"),
            "reasoning_tokens": (usage.get("output_tokens_details") or {}).get("reasoning_tokens")}
        for key in self.FIELDS:
            val = fields.get(key)
            if val is None:
                self.known[key] = False
            else:
                self.totals[key] += val

    def result(self):
        return {"requests": self.requests,
                "tokens": {k: self.totals[k] if self.known[k] and self.requests else None for k in self.FIELDS},
                "known_partial_tokens": self.totals.copy()}


class OpenAIResponses:
    name = "openai"
    endpoint = "https://api.openai.com/v1"
    key_env = "OPENAI_API_KEY"

    @staticmethod
    def parameters(model: dict) -> dict:
        params = {"model": model["id"], "store": False, "parallel_tool_calls": False}
        if "reasoning_effort" in model:
            params["reasoning"] = {"effort": model["reasoning_effort"]}
            params["include"] = ["reasoning.encrypted_content"]
        for key in ("temperature", "top_p", "max_output_tokens"):
            if key in model:
                params[key] = model[key]
        return params


class DeepSeekResponses:
    """DeepSeek's stateless Responses format, with its own parameter policy.

    Full plain-text reasoning content items are retained verbatim by workflow.
    store/include/parallel_tool_calls are unsupported or ignored: never send them.
    MCP calls are dispatched serially even if a response contains several calls.
    """
    name = "deepseek"
    endpoint = "https://api.deepseek.com"
    key_env = "DEEPSEEK_API_KEY"

    @staticmethod
    def parameters(model: dict) -> dict:
        params = {"model": model["id"], "reasoning": {"effort": model["reasoning_effort"]}}
        if "max_output_tokens" in model:
            params["max_output_tokens"] = model["max_output_tokens"]
        return params


class ClaudeCodeCLI:
    """Claude Code CLI (`claude -p`) as the agent loop, using its own login.

    The CLI runs with built-in tools disabled, a replaced system prompt (the same
    server instructions other providers receive) and only a relay MCP server whose
    calls return to this harness's session. No API key is read or forwarded.
    """
    name = "claude-code"
    endpoint = None
    key_env = "ANTHROPIC_API_KEY"

    @staticmethod
    def parameters(model: dict) -> dict:
        params = {"model": model["id"]}
        if "reasoning_effort" in model:
            params["effort"] = model["reasoning_effort"]
        return params


def adapter(config: dict):
    name = config.get("provider", {}).get("name")
    return {"deepseek": DeepSeekResponses, "claude-code": ClaudeCodeCLI}.get(name, OpenAIResponses)


def credential(config: dict) -> str:
    settings = config.get("provider", {})
    key = os.environ.get(settings.get("api_key_env", adapter(config).key_env))
    if key:
        return key
    if settings.get("api_key_file"):
        raw = Path(settings["api_key_file"]).read_bytes()
        text = raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
        # Also accepts the user's labeled local .secrets format; never log content.
        keys = re.findall(r"(?im)^\s*(?:[a-z][a-z _-]*\s*[:=]\s*)?(sk-[a-z0-9_-]+)\s*$", text)
        if len(keys) != 1:
            raise ValueError("Credential file must contain exactly one API key (optionally labeled)")
        return keys[0]
    raise ValueError(f"Set {adapter(config).key_env} or configure an ignored api_key_file before a paid run")


def claude_executable() -> str:
    """Prefer the native binary over the npm .cmd shim (cmd.exe mangles arguments).

    CE_BENCH_CLAUDE_EXE selects a frozen copy: Claude Code auto-updates its shared
    install, which would change the fingerprinted CLI version mid-campaign.
    """
    pinned = os.environ.get("CE_BENCH_CLAUDE_EXE")
    if pinned:
        if not Path(pinned).is_file():
            raise FileNotFoundError("CE_BENCH_CLAUDE_EXE does not name a file")
        return pinned
    found = shutil.which("claude")
    if not found:
        raise FileNotFoundError("Claude Code CLI `claude` not found on PATH")
    native = Path(found).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    return str(native) if Path(found).suffix.lower() in {".cmd", ".ps1", ""} and native.is_file() else found


def client_factory(config: dict):
    if adapter(config) is ClaudeCodeCLI:
        executable = claude_executable()

        @asynccontextmanager
        async def session():
            yield ClaudeCodeSession(executable)
        return session
    from openai import AsyncOpenAI
    key = credential(config)
    return lambda: AsyncOpenAI(api_key=key, base_url=adapter(config).endpoint,
                              max_retries=0, timeout=config["request_timeout"])


def request_parameters(config: dict) -> dict:
    return adapter(config).parameters(config["model"])


class ClaudeCodeSession:
    def __init__(self, executable: str):
        self.executable = executable


def build_failed(payload: dict) -> bool:
    build = payload.get("structured_content", {})
    if not build:
        for block in payload.get("content", []):
            if block.get("type") == "text":
                try:
                    build = json.loads(block["text"])
                except ValueError:
                    pass
    return bool(payload.get("is_error") or build.get("error") or build.get("build_state") != "built_ok")


async def workflow(mcp, task: str, config: dict, provider, evidence, result: dict, *, prompt: str | None = None):
    """Mutate result incrementally so failures preserve partial usage and counts."""
    if isinstance(provider, ClaudeCodeSession):
        return await claude_code_workflow(mcp, task, config, provider, evidence, result, prompt=prompt)
    instructions, schemas = mcp.adapter(task)
    user_prompt = {**PROMPTS, **DEMO_PROMPTS}[task] if prompt is None else prompt
    history = [{"role": "user", "content": user_prompt}]
    usage = Usage()
    result.update(tool_calls=0, tool_errors=0, repair_cycles=0, api_retries=0, transport_retries=0,
                  model_requests=0, returned_models=[], request_ids=[], final_response="")
    evidence.events.emit("model_context", instructions_ref=evidence.blob(instructions),
        schemas_ref=evidence.blob(schemas), prompt_ref=evidence.blob(user_prompt),
        prompt_resource_policy="No automatic prompts/resources; embedded reference tools available")
    started = perf_counter()
    failed_build = False
    try:
        async with asyncio.timeout(config["workflow_timeout"]):
            for turn in range(config["max_turns"]):
                request = {**request_parameters(config), "instructions": instructions,
                           "tools": schemas, "input": history}
                for attempt in range(len(CONNECTION_RETRY_DELAYS) + 1):
                    # Resend the identical API request only. History and MCP writes
                    # are advanced once, after a successfully received response.
                    evidence.events.emit("model_request", turn=turn, connection_attempt=attempt,
                        parameters_ref=evidence.blob({k: v for k, v in request.items() if k not in {"input", "tools", "instructions"}}),
                        input_refs=[evidence.blob(item) for item in history])
                    request_started = perf_counter()
                    result["model_requests"] += 1
                    result["api_retries"] += int(attempt > 0)
                    try:
                        response = await asyncio.wait_for(provider.responses.create(**request), config["request_timeout"])
                        break
                    except BaseException as exc:
                        usage.add(None)
                        retry = retryable_connection_error(exc) and attempt < len(CONNECTION_RETRY_DELAYS)
                        evidence.events.emit("model_request_failure", turn=turn, connection_attempt=attempt,
                            elapsed=perf_counter() - request_started, will_retry=retry,
                            error=type(exc).__name__, status_code=getattr(exc, "status_code", None),
                            request_id=getattr(exc, "request_id", None))
                        if not retry:
                            raise
                        delay = CONNECTION_RETRY_DELAYS[attempt]
                        evidence.events.emit("model_request_retry", turn=turn,
                            next_connection_attempt=attempt + 1, backoff_seconds=delay)
                        await asyncio.sleep(delay)
                raw = response.model_dump(mode="json", exclude_none=True)
                result["final_response"] = "\n".join(
                    block["text"] for item in raw.get("output", []) if item["type"] == "message"
                    for block in item.get("content", []) if block["type"] == "output_text")
                usage.add(raw.get("usage"))
                result["usage"] = usage.result()
                result["returned_models"].append(raw.get("model"))
                request_id = getattr(response, "_request_id", None)
                result["request_ids"].append(request_id)
                evidence.events.emit("model_response", turn=turn, elapsed=perf_counter() - request_started,
                    request_id=request_id, response_ref=evidence.blob(raw))
                history.extend(raw.get("output", []))  # Includes reasoning items, in original order.
                if raw.get("model") != config["model"]["id"]:
                    result.update(status="model_mismatch", failure_reason="Returned model differs from configured ID; use an exact snapshot")
                    return
                if raw.get("status") != "completed":
                    result.update(status="incomplete", failure_reason=raw.get("incomplete_details"))
                    return
                calls = [item for item in raw.get("output", []) if item["type"] == "function_call"]
                if not calls:
                    result["final_response"] = "\n".join(
                        block["text"] for item in raw.get("output", []) if item["type"] == "message"
                        for block in item.get("content", []) if block["type"] == "output_text")
                    result["status"] = "completed"
                    return
                for call in calls:
                    if result["tool_calls"] >= config["max_tool_calls"]:
                        result.update(status="tool_limit", failure_reason="Tool call limit reached")
                        return
                    result["tool_calls"] += 1
                    try:
                        arguments = json.loads(call["arguments"])
                        if not isinstance(arguments, dict):
                            raise ValueError("Expected object")
                    except ValueError:
                        payload = {"is_error": True, "error": "Invalid JSON object arguments"}
                    else:
                        payload = await mcp.dispatch(call["name"], arguments, schemas)
                    result["tool_errors"] += int(bool(payload.get("is_error")))
                    if call["name"] == "build_project":
                        failed_build = build_failed(payload)
                    if call["name"] in {"write_st_logic", "submit_candidate"} and failed_build:
                        result["repair_cycles"] += 1
                    output = {"type": "function_call_output", "call_id": call["call_id"], "output": encode(payload)}
                    history.append(output)
                    evidence.events.emit("function_output", item_ref=evidence.blob(output))
            result.update(status="turn_limit", failure_reason="Model turn limit reached")
    finally:
        result["workflow_seconds"] = perf_counter() - started
        result["usage"] = usage.result()


CLAUDE_STREAM_LIMIT = 1 << 26


def claude_usage(final: dict) -> dict:
    """Map Claude Code's cumulative per-model usage onto the Responses fields."""
    models = (final or {}).get("modelUsage") or {}
    totals = {key: sum(item.get(key) or 0 for item in models.values()) for key in
              ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens", "thinkingTokens")}
    prompt = totals["inputTokens"] + totals["cacheReadInputTokens"] + totals["cacheCreationInputTokens"]
    return {"input_tokens": prompt, "output_tokens": totals["outputTokens"],
            "total_tokens": prompt + totals["outputTokens"],
            "input_tokens_details": {"cached_tokens": totals["cacheReadInputTokens"]},
            "output_tokens_details": {"reasoning_tokens": totals["thinkingTokens"]}}


async def claude_code_workflow(mcp, task: str, config: dict, provider: ClaudeCodeSession, evidence,
                               result: dict, *, prompt: str | None = None):
    """One `claude -p` session; its MCP calls return here through the relay socket."""
    instructions, schemas = mcp.adapter(task)
    user_prompt = {**PROMPTS, **DEMO_PROMPTS}[task] if prompt is None else prompt
    usage = Usage()
    result.update(tool_calls=0, tool_errors=0, repair_cycles=0, api_retries=0, transport_retries=0,
                  model_requests=0, returned_models=[], request_ids=[], final_response="")
    evidence.events.emit("model_context", instructions_ref=evidence.blob(instructions),
        schemas_ref=evidence.blob(schemas), prompt_ref=evidence.blob(user_prompt),
        prompt_resource_policy="No automatic prompts/resources; embedded reference tools available")
    token = secrets.token_hex(16)
    state = {"failed_build": False, "limit": False, "fatal": None}
    lock = asyncio.Lock()
    process = None

    async def handle(reader, writer):
        try:
            request = json.loads(await reader.readline())
            if request.get("token") != token:
                return
            name, arguments = request["name"], request.get("arguments") or {}
            async with lock:
                if state["fatal"] or result["tool_calls"] >= config["max_tool_calls"]:
                    state["limit"] = state["limit"] or not state["fatal"]
                    payload = {"is_error": True, "error": "Tool call limit reached"}
                else:
                    result["tool_calls"] += 1
                    try:
                        payload = await mcp.dispatch(name, arguments, schemas)
                    except BaseException as exc:
                        state["fatal"] = exc
                        payload = {"is_error": True, "error": "Harness MCP failure"}
                    else:
                        result["tool_errors"] += int(bool(payload.get("is_error")))
                        if name == "build_project":
                            state["failed_build"] = build_failed(payload)
                        if name in {"write_st_logic", "submit_candidate"} and state["failed_build"]:
                            result["repair_cycles"] += 1
            output = encode(payload)
            evidence.events.emit("function_output", item_ref=evidence.blob(
                {"type": "function_call_output", "name": name, "output": output}))
            writer.write((json.dumps({"output": output, "is_error": bool(payload.get("is_error"))}) + "\n").encode())
            await writer.drain()
            state["mark"] = perf_counter()
        finally:
            writer.close()
            if (state["limit"] or state["fatal"]) and process and process.returncode is None:
                process.kill()

    started = state["mark"] = perf_counter()
    work = Path(tempfile.mkdtemp(prefix="ce-bench-claude-"))  # Outside any repository/CLAUDE.md tree.
    server = await asyncio.start_server(handle, "127.0.0.1", 0, limit=CLAUDE_STREAM_LIMIT)
    final = None
    try:
        port = server.sockets[0].getsockname()[1]
        (work / "schemas.json").write_text(json.dumps(schemas), encoding="utf-8")
        (work / "system-prompt.txt").write_text(instructions, encoding="utf-8")
        (work / "mcp.json").write_text(json.dumps({"mcpServers": {"ce": {
            "command": sys.executable,
            "args": ["-m", "control_expert_mcp.benchmark.claude_bridge", "--port", str(port),
                     "--schemas", str(work / "schemas.json")],
            "env": {"CE_BENCH_BRIDGE_TOKEN": token}}}}), encoding="utf-8")
        parameters = request_parameters(config)
        argv = [provider.executable, "-p", "--model", parameters["model"],
                "--output-format", "stream-json", "--verbose", "--tools", "",
                "--system-prompt-file", str(work / "system-prompt.txt"),
                "--mcp-config", str(work / "mcp.json"), "--strict-mcp-config",
                "--allowedTools", "mcp__ce", "--permission-mode", "dontAsk",
                "--setting-sources", "", "--no-session-persistence", "--disable-slash-commands",
                "--max-turns", str(config["max_turns"])]
        if "effort" in parameters:
            argv += ["--effort", parameters["effort"]]
        environment = {**os.environ, "MCP_TOOL_TIMEOUT": str((config["tool_timeout"] + 30) * 1000),
                       "MCP_TIMEOUT": "60000", "DISABLE_AUTOUPDATER": "1"}
        evidence.events.emit("model_request", turn=0, connection_attempt=0,
            parameters_ref=evidence.blob({"argv": [Path(argv[0]).name, *argv[1:]], "parameters": parameters}),
            input_refs=[evidence.blob({"role": "user", "content": user_prompt})])
        async with asyncio.timeout(config["workflow_timeout"]):
            process = await asyncio.create_subprocess_exec(*argv, cwd=work, env=environment,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, limit=CLAUDE_STREAM_LIMIT)
            stderr = asyncio.create_task(process.stderr.read())
            process.stdin.write(user_prompt.encode("utf-8"))
            await process.stdin.drain()
            process.stdin.close()
            seen = set()
            async for line in process.stdout:
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                kind = message.get("type")
                if kind == "system" and message.get("subtype") == "init":
                    result["claude_code"] = {"version": message.get("claude_code_version"),
                        "api_key_source": message.get("apiKeySource"), "tools": message.get("tools"),
                        "mcp_servers": message.get("mcp_servers"), "model": message.get("model")}
                    evidence.events.emit("claude_code_init", init_ref=evidence.blob(message))
                elif kind == "assistant":
                    body = message.get("message", {})
                    if body.get("id") in seen:
                        # Later content blocks of one API response arrive as separate lines.
                        evidence.events.emit("model_response_part", turn=len(seen) - 1,
                            request_id=message.get("request_id"), response_ref=evidence.blob(message))
                        continue
                    seen.add(body.get("id"))
                    result["model_requests"] += 1
                    result["returned_models"].append(body.get("model"))
                    result["request_ids"].append(message.get("request_id"))
                    # Approximate latency: since the previous response or returned tool output.
                    evidence.events.emit("model_response", turn=len(seen) - 1, elapsed=perf_counter() - state["mark"],
                        request_id=message.get("request_id"), response_ref=evidence.blob(message))
                    state["mark"] = perf_counter()
                elif kind == "result":
                    final = message
                    evidence.events.emit("claude_code_result", result_ref=evidence.blob(message))
            await process.wait()
            error_text = (await stderr).decode("utf-8", "replace")
        if state["fatal"]:
            raise state["fatal"]
        usage.add(claude_usage(final) if final else None)
        usage.requests = max(result["model_requests"], 1)
        if final:
            result["final_response"] = final.get("result") or ""
            result["cost_usd"] = final.get("total_cost_usd")
            result.setdefault("claude_code", {}).update(num_turns=final.get("num_turns"),
                duration_api_ms=final.get("duration_api_ms"), terminal_reason=final.get("terminal_reason"),
                subtype=final.get("subtype"), model_usage=final.get("modelUsage"))
        if state["limit"]:
            result.update(status="tool_limit", failure_reason="Tool call limit reached")
        elif final is None:
            evidence.events.emit("claude_code_exit", returncode=process.returncode,
                                 stderr_ref=evidence.blob(error_text[-4000:]))
            result.update(status="workflow_failure", failure_reason=f"Claude Code exited without a result ({process.returncode})")
        elif any(model != config["model"]["id"] for model in result["returned_models"]):
            result.update(status="model_mismatch", failure_reason="Returned model differs from configured ID; use an exact snapshot")
        elif final.get("subtype") == "error_max_turns":
            result.update(status="turn_limit", failure_reason="Model turn limit reached")
        elif final.get("subtype") == "success" and not final.get("is_error"):
            result["status"] = "completed"
        else:
            result.update(status="incomplete", failure_reason=final.get("terminal_reason") or final.get("subtype"))
    finally:
        if process and process.returncode is None:
            process.kill()
            await process.wait()
        server.close()
        result["workflow_seconds"] = perf_counter() - started
        result["usage"] = usage.result()
        shutil.rmtree(work, ignore_errors=True)
