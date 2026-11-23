"""Session-scoped user choices enforced before live MCP operations."""

from contextlib import contextmanager
from threading import RLock


class LiveAccessPolicy:
    """Start offline; never infer consent from environment variables or probing."""

    def __init__(self, enabled: bool):
        self.enabled = enabled
        self.lock = RLock()
        self.config = self.validate(False)
        self.configured = False

    def validate(self, allow_live_connection: bool, protocol: str = "opc",
                 ofs_alias: str = "", opc_server_confirmed_running: bool = False,
                 allow_closed_loop: bool = False) -> dict:
        if protocol not in ("opc", "modbus", "engineering"):
            raise ValueError("protocol must be 'opc' (preferred), 'modbus' or 'engineering'; no automatic fallback")
        if allow_live_connection and not self.enabled:
            raise ValueError("Live tools are disabled. Set CE_MCP_ENABLE_ONLINE=1 and restart, then repeat setup.")
        ofs_alias = ofs_alias.strip()
        if allow_live_connection and protocol == "opc" and not ofs_alias:
            raise ValueError("OPC live access requires the user-confirmed OFS device alias")
        if allow_closed_loop:
            if not allow_live_connection:
                raise ValueError("Closed-loop operation requires permission for live connections")
            if protocol == "opc" and not opc_server_confirmed_running:
                raise ValueError("The user must confirm OFS is available and running before allowing closed-loop operation")
        return {"allow_live_connection": allow_live_connection, "protocol": protocol,
                "ofs_alias": ofs_alias, "opc_server_confirmed_running": opc_server_confirmed_running,
                "allow_closed_loop": allow_closed_loop}

    def status(self) -> dict:
        with self.lock:
            return {"online_tools_enabled": self.enabled, "configured": self.configured,
                    "preferred_protocol": "opc", "default_test_ofs_alias": "Dev_Alias_2", **self.config,
                    "setup_required": not self.configured}

    @contextmanager
    def guard(self, tool: str):
        live = tool.startswith(("opc_", "modbus_", "plc_")) or tool in ("read_tags", "write_tags")
        # Cleanup/status are always possible, including after access is revoked.
        exempt = tool.endswith(("_disconnect", "_status"))
        if not live or exempt:
            yield
            return
        with self.lock:
            if not self.configured or not self.config["allow_live_connection"]:
                raise ValueError("Live access is blocked. Ask the user and call configure_live_access first.")
            protocol = "opc" if tool.startswith("opc_") else "modbus" if (
                tool.startswith("modbus_") or tool in ("read_tags", "write_tags")) else None
            if protocol and self.config["protocol"] != protocol:
                raise ValueError(f"Session protocol is {self.config['protocol']}; {protocol} access is blocked. No automatic fallback.")
            if tool in ("opc_write_tags", "write_tags", "plc_transfer", "plc_command"):
                if not self.config["allow_closed_loop"]:
                    raise ValueError("Writes/PLC control require explicit user approval for closed-loop operation in configure_live_access.")
            yield
