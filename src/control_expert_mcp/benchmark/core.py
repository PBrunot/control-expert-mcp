"""Configuration, durable evidence, fingerprints and exclusive CE ownership."""
from __future__ import annotations

from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else encode(value).encode()).hexdigest()


def write_json(path: Path, value) -> None:
    """Atomically publish a summary; event streams are separately append-only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False))
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Events:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path

    def emit(self, kind: str, **data) -> None:
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(encode({"at": datetime.now(timezone.utc).isoformat(), "kind": kind, **data}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())


SECRET = re.compile(r"key|token|secret|password|credential|authorization|cookie", re.I)


def environment(condition: dict) -> dict:
    env = {k: v for k, v in os.environ.items() if not SECRET.search(k)}
    for key, value in condition.get("env", {}).items():
        if SECRET.search(key):
            raise ValueError("Do not place credentials in benchmark server environment")
        env[key] = str(value)
    env["CE_MCP_ENABLE_ONLINE"] = "0"
    return env


def environment_record(env: dict) -> dict:
    # Unknown variables may contain credentials even when their names do not.
    visible = {"PATH", "PYTHONPATH", "SYSTEMROOT", "COMSPEC", "TEMP", "TMP",
               "CE_MCP_ENABLE_ONLINE", "CE_MCP_MANUALS_DIR", "CE_MCP_SCHEMA_DIR"}
    return {k: v if k.upper() in visible else {"sha256": digest(v)} for k, v in env.items()}


def git_metadata(directory: str | Path) -> dict:
    def git(*args):
        return subprocess.check_output(["git", "-C", str(directory), *args], stderr=subprocess.DEVNULL)
    try:
        root = git("rev-parse", "--show-toplevel").decode().strip()
        head = git("rev-parse", "HEAD").decode().strip()
        status = git("status", "--porcelain=v1", "-z")
        files = git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0")
        untracked = {p: digest((Path(root) / p).read_bytes()) for p in files if p and (Path(root) / p).is_file()}
        return {"root": root, "revision": head, "dirty": bool(status),
                "dirty_fingerprint": digest([status.decode(), git("diff", "HEAD", "--binary").decode(), untracked])}
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return {"revision": None, "dirty_fingerprint": None}


def tree_fingerprint(path: Path) -> dict:
    if not path.is_dir():
        return {"path": str(path), "sha256": None}
    entries = {p.relative_to(path).as_posix(): digest(p.read_bytes())
               for p in sorted(path.rglob("*")) if p.is_file()}
    return {"path": str(path), "sha256": digest(entries), "files": entries}


def load_config(path: str) -> dict:
    config = read_json(Path(path))
    allowed_keys = {"provider", "model", "cpu", "ce_version", "fixture", "workspace", "results",
                    "tool_timeout", "request_timeout", "workflow_timeout", "max_turns", "max_tool_calls", "conditions"}
    if set(config) - allowed_keys:
        raise ValueError("Unknown configuration fields; credentials belong only in env or an ignored file")
    base = Path(path).resolve().parent
    provider = config.setdefault("provider", {"name": "openai"})
    if provider.get("name") not in {"openai", "deepseek"} or set(provider) - {"name", "api_key_env", "api_key_file"}:
        raise ValueError("Provider must be openai or deepseek; credentials belong in env or ignored file")
    if provider.get("api_key_file"):
        provider["api_key_file"] = str((base / provider["api_key_file"]).resolve())
    for key in ("workspace", "results", "fixture"):
        config[key] = str((base / config[key]).resolve())
    for name, condition in config["conditions"].items():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("Condition names must contain only letters, digits, underscores or hyphens")
        condition["cwd"] = str((base / condition["cwd"]).resolve())
        if condition.get("documentation") not in (True, False):
            raise ValueError(f"{name}: explicit documentation boolean required")
        if not condition.get("command") or not isinstance(condition.get("args", []), list):
            raise ValueError("Server command and argument list required")
        if set(condition) - {"command", "args", "cwd", "env", "documentation"}:
            raise ValueError("Unknown server condition fields")
        if any(re.search(r"sk-[a-z0-9_-]{10,}|--(?:api[-_]?key|password|token|secret)", arg, re.I)
               for arg in condition.get("args", [])):
            raise ValueError("Do not pass credentials in benchmark server arguments")
        environment(condition)
    model = config.get("model", {})
    if not model.get("id"):
        raise ValueError("Explicit API model ID/snapshot required")
    allowed = {"id", "identity", "reasoning_effort", "max_output_tokens", "temperature", "top_p"}
    if set(model) - allowed:
        raise ValueError("Unknown model parameters")
    if model.get("identity", "pinned") not in {"pinned", "alias"}:
        raise ValueError("Model identity must be pinned or alias")
    if provider["name"] == "deepseek":
        if model.get("reasoning_effort") not in {"none", "low", "high", "max"}:
            raise ValueError("DeepSeek requires explicit reasoning_effort: none/low/high/max")
        if "temperature" in model or "top_p" in model:
            raise ValueError("DeepSeek adapter omits sampling knobs to avoid silently ignored parameters")
    for key in ("tool_timeout", "request_timeout", "workflow_timeout", "max_turns", "max_tool_calls"):
        if config.get(key, 0) <= 0:
            raise ValueError(f"Positive {key} required")
    return config


def snapshot(config: dict) -> dict:
    from .tasks import PROMPTS, RUBRIC_VERSION, ORIENTATION
    from .provider import connection_retry_policy
    deps = {}
    for name in ("control-expert-mcp", "mcp", "openai", "pywin32"):
        try:
            deps[name] = version(name)
        except PackageNotFoundError:
            deps[name] = None
    servers = {}
    for name, condition in config["conditions"].items():
        env = environment(condition)
        corpus = env.get("CE_MCP_MANUALS_DIR")
        runtime = server_runtime(condition)
        servers[name] = {"runtime": runtime,
                         "source": git_metadata(runtime["package_path"]) if runtime.get("package_path") else {"revision": None, "dirty_fingerprint": None},
                         "environment": environment_record(env),
                         "documentation": tree_fingerprint(Path(corpus)) if corpus else None}
    return {"config": copy.deepcopy(config), "fixture_sha256": digest(Path(config["fixture"]).read_bytes()),
            "harness": git_metadata(Path(__file__).parent), "dependencies": deps,
            "machine": {"hostname": platform.node(), "platform": platform.platform(),
                        "python": platform.python_version(), "processor": platform.processor()},
            "servers": servers, "prompts": PROMPTS, "orientation": ORIENTATION,
            "rubric_version": RUBRIC_VERSION, "provider_retry_policy": connection_retry_policy()}


def server_runtime(condition: dict) -> dict:
    """Probe the selected Python interpreter, never assume the harness environment.

    Arbitrary wrappers remain unknown; a cwd is not proof of an imported revision.
    This imports only package metadata, not the COM bridge or server.
    """
    if condition.get("args") != ["-m", "control_expert_mcp"]:
        return {"package_path": None, "dependencies": None}
    code = (
        "import importlib.util,importlib.metadata,json; "
        "s=importlib.util.find_spec('control_expert_mcp'); "
        "print(json.dumps({'package_path':list(s.submodule_search_locations)[0],"
        "'dependencies':{n:importlib.metadata.version(n) for n in ['control-expert-mcp','mcp']}}))"
    )
    try:
        result = json.loads(subprocess.check_output([condition["command"], "-c", code],
            cwd=condition["cwd"], env=environment(condition), stderr=subprocess.DEVNULL, timeout=15))
        result["package_tree"] = tree_fingerprint_python(Path(result["package_path"]))
        return result
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"package_path": None, "dependencies": None}


def tree_fingerprint_python(path: Path) -> str:
    return digest({p.relative_to(path).as_posix(): digest(p.read_bytes()) for p in sorted(path.rglob("*.py"))})


def guard_directory() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "control-expert-mcp" / "benchmark-session"


def mark_tainted(workspace: Path, reason: dict):
    write_json(workspace / "TAINTED.json", reason)
    write_json(guard_directory() / "TAINTED.json", {**reason, "workspace": str(workspace)})


@contextmanager
def ce_lock(workspace: Path, *, allow_taint: bool = False):
    """OS releases ownership on crash; persistent taint blocks uncertain recovery."""
    workspace.mkdir(parents=True, exist_ok=True)
    guard = guard_directory()
    guard.mkdir(parents=True, exist_ok=True)
    if not allow_taint and ((workspace / "TAINTED.json").exists() or (guard / "TAINTED.json").exists()):
        raise RuntimeError("CE session tainted. Verify CE idle/recovered, then use recover --verified-idle.")
    with (guard / "ce.lock").open("a+b") as stream:
        stream.seek(0)
        stream.write(b"0")
        stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            if not allow_taint and (guard / "TAINTED.json").exists():
                raise RuntimeError("CE session tainted; verified recovery required")
            yield
        except BaseException as exc:
            # Tool failures mark taint at the transport boundary. Ordinary config
            # and scoring failures have no outstanding COM operation.
            if not isinstance(exc, Exception):
                mark_tainted(workspace, {"reason": type(exc).__name__})
            raise
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)
