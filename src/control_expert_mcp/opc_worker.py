"""Private JSON-lines OPC DA Automation worker; run with matching-bitness Python.

All COM objects stay on this process's main STA thread. No project write token
is acquired, and no subscriptions/callbacks cross the process boundary.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime


def _json_value(value):
    import math
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("OPC returned a non-finite numeric value")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


class AutomationSession:
    def __init__(self):
        self.server = None
        self.group = None
        self.alias = ""
        self.items = {}

    def disconnect(self):
        self.items.clear()
        self.group = None
        server, self.server = self.server, None
        if server is not None:
            server.Disconnect()
        return {"connected": False}

    def status(self):
        if self.server is None:
            return {"connected": False}
        state = int(self.server.ServerState)
        return {"connected": state == 1, "server_state": state,
                "server_name": str(self.server.ServerName), "alias": self.alias,
                "version": f"{self.server.MajorVersion}.{self.server.MinorVersion}",
                "worker_bits": 32 if sys.maxsize <= 2**32 else 64}

    def connect(self, progid, alias, automation_progid):
        import win32com.client

        self.disconnect()
        try:
            self.server = win32com.client.Dispatch(automation_progid)
            self.server.Connect(progid)
            self.group = self.server.OPCGroups.Add("ControlExpertMCP")
            self.group.IsActive = True
            self.group.IsSubscribed = False
            self.alias = alias
            return self.status()
        except Exception:
            self.disconnect()
            raise

    def browse(self, branches, flat, offset, max_results):
        if self.server is None:
            raise ValueError("Not connected. Call opc_connect first.")
        browser = self.server.CreateBrowser()
        browser.MoveToRoot()
        for branch in branches:
            browser.MoveDown(branch)
        browser.ShowBranches()
        # Do not use the cached COM enumerator: OFS reuses it after ShowLeafs.
        branch_count = int(browser.Count)
        total = branch_count
        entries = []
        if not flat:
            for index in range(max(0, offset), min(branch_count, offset + max_results)):
                entries.append({"kind": "branch", "name": str(browser.Item(index + 1))})
        browser.ShowLeafs(flat)
        leaf_count = int(browser.Count)
        if flat:
            total = leaf_count
            start, stop = offset, offset + max_results
        else:
            total += leaf_count
            start, stop = max(0, offset - branch_count), offset + max_results - branch_count
        for index in range(start, min(leaf_count, stop)):
            name = str(browser.Item(index + 1))
            item_id = name if flat else str(browser.GetItemID(name))
            entries.append({"kind": "item", "name": name, "item_id": item_id})
        end = offset + len(entries)
        return {"branches": branches, "entries": entries, "total": total,
                "next_offset": end if end < total else None}

    def _item(self, tag):
        if self.group is None:
            raise ValueError("Not connected. Call opc_connect first.")
        if not isinstance(tag, str) or not tag.strip():
            raise ValueError("OPC tag must be a nonempty string")
        item_id = tag if "!" in tag or not self.alias else f"{self.alias}!{tag}"
        if self.alias and not item_id.startswith(self.alias + "!"):
            raise ValueError("OPC item is outside the configured device alias")
        if item_id not in self.items:
            item = self.group.OPCItems.AddItem(item_id, len(self.items) + 1)
            if item is None:
                raise ValueError(f"OPC item not found or not exposed: {item_id}; browse scalar members and check the data dictionary")
            self.items[item_id] = item
        return item_id, self.items[item_id]

    def read(self, tags):
        values, samples, errors = {}, {}, {}
        for tag in tags:
            try:
                item_id, item = self._item(tag)
                value, quality, timestamp = item.Read(2)  # OPCDevice, never cache
                quality = int(quality)
                samples[tag] = {"item_id": item_id, "value": _json_value(value),
                                "quality": quality, "good": quality & 0xC0 == 0xC0,
                                "timestamp": _json_value(timestamp),
                                "canonical_type": int(item.CanonicalDataType),
                                "access_rights": int(item.AccessRights)}
                if samples[tag]["good"]:
                    values[tag] = _json_value(value)
                else:
                    errors[tag] = f"OPC quality is not good: 0x{quality:04X}"
            except Exception as exc:
                errors[tag] = str(exc)
        return {"values": values, "samples": samples, "errors": errors}

    def write(self, values):
        import win32com.client

        written, errors = {}, {}
        for tag, value in values.items():
            try:
                _, item = self._item(tag)
                if not int(item.AccessRights) & 2:
                    raise ValueError("OPC item is read-only")
                vt = int(item.CanonicalDataType)
                if vt == 11 and not isinstance(value, bool):
                    raise ValueError("BOOL/EBOOL writes require a JSON boolean")
                if vt in (2, 3, 16, 17, 18, 19, 20, 21, 22, 23):
                    if isinstance(value, bool) or not isinstance(value, int):
                        raise ValueError("Integer OPC item requires a JSON integer")
                    ranges = {2: (-2**15, 2**15-1), 3: (-2**31, 2**31-1),
                              16: (-128, 127), 17: (0, 255), 18: (0, 65535),
                              19: (0, 2**32-1), 20: (-2**63, 2**63-1),
                              21: (0, 2**64-1), 22: (-2**31, 2**31-1), 23: (0, 2**32-1)}
                    low, high = ranges[vt]
                    if not low <= value <= high:
                        raise ValueError("Integer outside the OPC item's type range")
                elif vt in (4, 5):
                    import math
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                        raise ValueError("Floating OPC item requires a finite JSON number")
                elif vt == 8:
                    if not isinstance(value, str):
                        raise ValueError("String OPC item requires a JSON string")
                elif vt != 11:
                    raise ValueError(f"Unsupported write VARIANT type {vt}; browse scalar members")
                item.Write(win32com.client.VARIANT(vt, value))
                written[tag] = value
            except Exception as exc:
                errors[tag] = str(exc)
        return {"written": written, "errors": errors}


def main():
    import pythoncom

    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
    session = AutomationSession()
    try:
        for line in sys.stdin:
            try:
                request = json.loads(line)
                method = request["method"]
                if method not in ("connect", "disconnect", "status", "browse", "read", "write"):
                    raise ValueError("Unknown OPC worker method")
                result = getattr(session, method)(**request.get("params", {}))
                response = {"result": result}
                encoded = json.dumps(response, ensure_ascii=True, allow_nan=False)
            except Exception as exc:
                response = {"error": str(exc)}
                encoded = json.dumps(response, ensure_ascii=True)
            print(encoded, flush=True)
    finally:
        session.disconnect()
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    main()
