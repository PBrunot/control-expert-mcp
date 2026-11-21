"""Serialized OPC DA client using a matching-bitness STA helper process."""

from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
from threading import RLock, Thread


class OpcError(RuntimeError):
    """An actionable OPC connection or item error."""


class OpcClient:
    """Own one local OPC Automation session, independent of the UDE project."""

    def __init__(self, python: str | None = None, timeout: float = 30):
        self.python = python or os.environ.get("CE_MCP_OPC_PYTHON", sys.executable)
        self.timeout = timeout
        self._lock = RLock()
        self._process = None
        self._responses = None
        atexit.register(self.disconnect)

    def _start(self):
        if self._process is not None and self._process.poll() is None:
            return
        self._stop()
        try:
            self._process = subprocess.Popen(
                [self.python, "-u", str(Path(__file__).with_name("opc_worker.py"))],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            raise OpcError(f"Cannot start OPC Python {self.python}: {exc}") from None
        self._responses = queue.Queue()
        process, responses = self._process, self._responses

        def receive():
            try:
                for line in process.stdout:
                    responses.put(line)
            finally:
                responses.put(None)

        Thread(target=receive, daemon=True, name="opc-responses").start()

    def _stop(self):
        process, self._process = self._process, None
        self._responses = None
        if process is None:
            return
        try:
            process.stdin.close()
            process.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
            process.wait(timeout=3)
        finally:
            process.stdout.close()

    def _call(self, method, **params):
        if self._process is None:
            raise OpcError("Not connected. Call opc_connect first.")
        try:
            payload = json.dumps({"method": method, "params": params}, allow_nan=False)
            self._process.stdin.write(payload + "\n")
            self._process.stdin.flush()
            line = self._responses.get(timeout=self.timeout)
            if line is None:
                self._stop()
                raise OpcError("OPC helper exited. Check CE_MCP_OPC_PYTHON and its pywin32 installation.")
            response = json.loads(line)
        except (OSError, queue.Empty, json.JSONDecodeError) as exc:
            self._stop()
            raise OpcError(f"OPC helper failed or timed out; session disconnected: {exc}") from None
        if "error" in response:
            raise OpcError(response["error"] + " Check OFS and a matching-bitness OPC Automation wrapper/Python (CE_MCP_OPC_PYTHON).")
        return response["result"]

    def connect(self, progid="Schneider-Aut.OFS.2", alias="", automation_progid="OPC.Automation") -> dict:
        with self._lock:
            self._start()
            try:
                return self._call("connect", progid=progid, alias=alias, automation_progid=automation_progid)
            except Exception:
                self._stop()
                raise

    def disconnect(self) -> dict:
        with self._lock:
            self._stop()
            return {"connected": False}

    def status(self) -> dict:
        with self._lock:
            return self._call("status") if self._process else {"connected": False}

    def browse(self, branches: list[str], flat=False, offset=0, max_results=200) -> dict:
        if offset < 0 or not 1 <= max_results <= 5000:
            raise OpcError("offset must be >= 0 and max_results between 1 and 5000")
        with self._lock:
            return self._call("browse", branches=branches, flat=flat, offset=offset, max_results=max_results)

    def read(self, tags: list[str]) -> dict:
        with self._lock:
            return self._call("read", tags=tags)

    def write(self, values: dict) -> dict:
        with self._lock:
            return self._call("write", values=values)
