"""Stateless Responses API loop; provider usage is never estimated."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re
from time import perf_counter

from .core import encode
from .tasks import PROMPTS

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


def adapter(config: dict):
    return DeepSeekResponses if config.get("provider", {}).get("name") == "deepseek" else OpenAIResponses


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


def client_factory(config: dict):
    from openai import AsyncOpenAI
    key = credential(config)
    return lambda: AsyncOpenAI(api_key=key, base_url=adapter(config).endpoint,
                              max_retries=0, timeout=config["request_timeout"])


def request_parameters(config: dict) -> dict:
    return adapter(config).parameters(config["model"])


async def workflow(mcp, task: str, config: dict, provider, evidence, result: dict):
    """Mutate result incrementally so failures preserve partial usage and counts."""
    instructions, schemas = mcp.adapter(task)
    history = [{"role": "user", "content": PROMPTS[task]}]
    usage = Usage()
    result.update(tool_calls=0, tool_errors=0, repair_cycles=0, api_retries=0, transport_retries=0,
                  model_requests=0, returned_models=[], request_ids=[], final_response="")
    evidence.events.emit("model_context", instructions_ref=evidence.blob(instructions),
        schemas_ref=evidence.blob(schemas), prompt_ref=evidence.blob(PROMPTS[task]),
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
                        build = payload.get("structured_content", {})
                        if not build:
                            for block in payload.get("content", []):
                                if block.get("type") == "text":
                                    try:
                                        build = json.loads(block["text"])
                                    except ValueError:
                                        pass
                        failed_build = bool(payload.get("is_error") or build.get("error") or build.get("build_state") != "built_ok")
                    if call["name"] == "write_st_logic" and failed_build:
                        result["repair_cycles"] += 1
                    output = {"type": "function_call_output", "call_id": call["call_id"], "output": encode(payload)}
                    history.append(output)
                    evidence.events.emit("function_output", item_ref=evidence.blob(output))
            result.update(status="turn_limit", failure_reason="Model turn limit reached")
    finally:
        result["workflow_seconds"] = perf_counter() - started
        result["usage"] = usage.result()
