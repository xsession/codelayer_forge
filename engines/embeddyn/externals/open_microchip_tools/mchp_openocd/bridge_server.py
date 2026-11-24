from __future__ import annotations

import argparse
import json
import socketserver
from typing import Any, Callable, Dict, Optional

from interfaces.ICD4.icd4_drv import ICD4Driver, ICD4UsbIds
from interfaces.PK4.pk4_drv import PK4Driver, PK4UsbIds
from mchp_ri4.family_profiles import family_inventory
from mchp_ri4.named_session import NamedScriptSession


class BridgeError(RuntimeError):
    pass


def _parse_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise BridgeError(f"Expected integer-compatible value, got {type(value).__name__}")


def _tool_driver(tool: str, vid: int, pid: int):
    kind = (tool or "").strip().lower()
    if kind == "pk4":
        return PK4Driver(PK4UsbIds(vid=vid, pid=pid))
    if kind == "icd4":
        return ICD4Driver(ICD4UsbIds(vid=vid, pid=pid))
    raise BridgeError(f"Unsupported tool type: {tool}")


def _parse_capability_filter(args: Dict[str, Any]) -> tuple[list[str], str]:
    raw_capabilities = args.get("capabilities")
    raw_capability = args.get("capability")
    capabilities: list[str] = []
    if isinstance(raw_capability, str) and raw_capability.strip():
        capabilities.append(raw_capability.strip())
    if raw_capabilities is None:
        pass
    elif isinstance(raw_capabilities, list) and all(isinstance(item, str) for item in raw_capabilities):
        capabilities.extend(item.strip() for item in raw_capabilities if item.strip())
    else:
        raise BridgeError("capabilities must be a list of strings")
    match = str(args.get("capabilityMatch") or "any").strip().lower()
    if match not in {"any", "all"}:
        raise BridgeError("capabilityMatch must be 'any' or 'all'")
    return capabilities, match


def _parse_string_filter(
    args: Dict[str, Any],
    *,
    singular_key: str,
    plural_key: str,
    match_key: str,
) -> tuple[list[str], str]:
    raw_items = args.get(plural_key)
    raw_item = args.get(singular_key)
    items: list[str] = []
    if isinstance(raw_item, str) and raw_item.strip():
        items.append(raw_item.strip())
    if raw_items is None:
        pass
    elif isinstance(raw_items, list) and all(isinstance(item, str) for item in raw_items):
        items.extend(item.strip() for item in raw_items if item.strip())
    else:
        raise BridgeError(f"{plural_key} must be a list of strings")
    match = str(args.get(match_key) or "any").strip().lower()
    if match not in {"any", "all"}:
        raise BridgeError(f"{match_key} must be 'any' or 'all'")
    return items, match


def _parse_optional_string(args: Dict[str, Any], key: str) -> str:
    value = args.get(key, "")
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    raise BridgeError(f"{key} must be a string")


def _parse_params(args: Dict[str, Any], key: str = "params") -> list[Any]:
    raw = args.get(key, [])
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise BridgeError(f"{key} must be a list")
    return list(raw)


def _parse_hex_bytes(args: Dict[str, Any], key: str) -> Optional[bytes]:
    value = args.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise BridgeError(f"{key} must be a hex string")
    text = "".join(value.split())
    if not text:
        return b""
    try:
        return bytes.fromhex(text)
    except ValueError as exc:
        raise BridgeError(f"{key} must be valid hex") from exc


class BridgeState:
    def __init__(self) -> None:
        self.session: Optional[NamedScriptSession] = None

    def require_session(self) -> NamedScriptSession:
        if self.session is None:
            raise BridgeError("No hardware session is active")
        return self.session

    def close_session(self) -> Optional[Dict[str, Any]]:
        session = self.session
        if session is None:
            return None
        summary = session.script_inventory()
        try:
            session.close()
        finally:
            self.session = None
        return summary


class BridgeProtocol:
    def __init__(self, state: BridgeState):
        self._state = state
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {
            "ping": self._ping,
            "listFamilies": self._list_families,
            "probeTool": self._probe_tool,
            "startSession": self._start_session,
            "sessionStatus": self._session_status,
            "targetStatus": self._target_status,
            "endSession": self._end_session,
            "enterDebugMode": self._enter_debug_mode,
            "getPc": self._get_pc,
            "setPc": self._set_pc,
            "runScript": self._run_script,
            "run": self._run,
            "step": self._step,
            "halt": self._halt,
            "eraseChip": self._erase_chip,
            "programHex": self._program_hex,
            "verifyHex": self._verify_hex,
            "readProgram": self._read_program,
            "writeProgram": self._write_program,
            "setBreakpoint": self._set_breakpoint,
            "setWatchpoint": self._set_watchpoint,
            "clearHardwarePoint": self._clear_hardware_point,
            "listHardwarePoints": self._list_hardware_points,
        }

    def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        command = str(request.get("command") or "").strip()
        handler = self._handlers.get(command)
        if handler is None:
            raise BridgeError(f"Unknown command: {command}")
        args = request.get("args") or {}
        return {"ok": True, "result": handler(args)}

    def _ping(self, args: Dict[str, Any]) -> Dict[str, str]:
        return {"message": "pong"}

    def _list_families(self, args: Dict[str, Any]) -> Any:
        capabilities, match = _parse_capability_filter(args)
        signatures, signature_match = _parse_string_filter(
            args,
            singular_key="signature",
            plural_key="signatures",
            match_key="signatureMatch",
        )
        groups, group_match = _parse_string_filter(
            args,
            singular_key="group",
            plural_key="groups",
            match_key="groupMatch",
        )
        search_prefix = _parse_optional_string(args, "searchPrefix")
        return family_inventory(
            required_capabilities=capabilities,
            capability_match=match,
            required_signatures=signatures,
            signature_match=signature_match,
            required_groups=groups,
            group_match=group_match,
            search_prefix=search_prefix,
        )

    def _probe_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        tool = str(args.get("tool") or "")
        vid = _parse_int(args.get("vid"))
        pid = _parse_int(args.get("pid"))
        keys = args.get("keys") or ["Commands in progress"]
        driver = _tool_driver(tool, vid, pid)
        try:
            values = {key: driver.get_status_value(key) for key in keys}
        finally:
            driver.close()
        return {"tool": tool.upper(), "vid": f"0x{vid:04X}", "pid": f"0x{pid:04X}", "status": values}

    def _start_session(self, args: Dict[str, Any]) -> Dict[str, Any]:
        tool = str(args.get("tool") or "")
        processor = str(args.get("processor") or "").strip()
        scripts_path = str(args.get("scriptsPath") or "").strip()
        if not processor or not scripts_path:
            raise BridgeError("processor and scriptsPath are required")
        self._state.close_session()
        self._state.session = NamedScriptSession.open_usb(
            tool=tool,
            processor=processor,
            vid=_parse_int(args.get("vid")),
            pid=_parse_int(args.get("pid")),
            scripts_path=scripts_path,
            tool_scripts_path=str(args.get("toolScriptsPath") or "").strip() or None,
            script_suffix=str(args.get("scriptSuffix") or "").strip() or None,
            pc_bytes=_parse_int(args.get("pcBytes", 4)),
            family=str(args.get("family") or "").strip() or None,
        )
        return self._state.session.script_inventory()

    def _session_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._state.require_session().script_inventory()

    def _target_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._state.require_session().target_status()

    def _end_session(self, args: Dict[str, Any]) -> Dict[str, Any]:
        summary = self._state.close_session()
        return {
            "closed": summary is not None,
            "previousSession": summary,
        }

    def _enter_debug_mode(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._state.require_session().enter_debug_mode()

    def _get_pc(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._state.require_session().get_pc()

    def _set_pc(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._state.require_session().set_pc(_parse_int(args.get("address", 0)))

    def _run_script(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = _parse_optional_string(args, "name")
        if not name:
            raise BridgeError("name is required")
        params = _parse_params(args)
        timeout_ms = _parse_int(args.get("timeoutMs", -1))
        upload_length = args.get("uploadLength")
        download_data = _parse_hex_bytes(args, "downloadHex")
        if upload_length is not None and download_data is not None:
            raise BridgeError("uploadLength and downloadHex cannot be used together")
        session = self._state.require_session()
        if upload_length is not None:
            data = session.run_script_with_upload(name, _parse_int(upload_length), *params)
            return {"script": name, "length": len(data), "payloadHex": data.hex()}
        if download_data is not None:
            return session.run_script_with_download(name, download_data, *params)
        return session.run_script(name, *params, timeout_ms=timeout_ms)

    def _run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._state.require_session().run_target()

    def _step(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._state.require_session().step_target(ufex=bool(args.get("ufex", False)))

    def _halt(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._state.require_session().halt_target()

    def _erase_chip(self, args: Dict[str, Any]) -> Dict[str, Any]:
        mode = args.get("mode")
        session = self._state.require_session()
        if mode is None:
            return session.erase_target()
        return session.erase_target(_parse_int(mode))

    def _program_hex(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = str(args.get("path") or "").strip()
        if not path:
            raise BridgeError("path is required")
        return self._state.require_session().program_hex(
            path,
            erase_first=bool(args.get("eraseFirst", True)),
            verify=bool(args.get("verify", False)),
            chunk_size=_parse_int(args.get("chunkSize", NamedScriptSession.DEFAULT_TRANSFER_CHUNK)),
        )

    def _verify_hex(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = str(args.get("path") or "").strip()
        if not path:
            raise BridgeError("path is required")
        return self._state.require_session().verify_hex(
            path,
            chunk_size=_parse_int(args.get("chunkSize", NamedScriptSession.DEFAULT_TRANSFER_CHUNK)),
        )

    def _read_program(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._state.require_session().read_program(
            _parse_int(args.get("address", 0)),
            _parse_int(args.get("size", 16)),
        )

    def _write_program(self, args: Dict[str, Any]) -> Dict[str, Any]:
        data = _parse_hex_bytes(args, "dataHex")
        if data is None:
            raise BridgeError("dataHex is required")
        return self._state.require_session().write_program(
            _parse_int(args.get("address", 0)),
            data,
        )

    def _set_breakpoint(self, args: Dict[str, Any]) -> Dict[str, Any]:
        slot = args.get("slot")
        return self._state.require_session().set_hardware_breakpoint(
            _parse_int(args.get("address")),
            slot=None if slot is None else _parse_int(slot),
        )

    def _set_watchpoint(self, args: Dict[str, Any]) -> Dict[str, Any]:
        slot = args.get("slot")
        return self._state.require_session().set_hardware_watchpoint(
            _parse_int(args.get("address")),
            access=str(args.get("access") or "access"),
            length=_parse_int(args.get("length", 1)),
            slot=None if slot is None else _parse_int(slot),
        )

    def _clear_hardware_point(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._state.require_session().clear_hardware_point(_parse_int(args.get("slot")))

    def _list_hardware_points(self, args: Dict[str, Any]) -> list[Dict[str, Any]]:
        return self._state.require_session().list_hardware_points()


class _BridgeRequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        protocol: BridgeProtocol = self.server.protocol  # type: ignore[attr-defined]
        while True:
            line = self.rfile.readline()
            if not line:
                return
            try:
                request = json.loads(line.decode("utf-8"))
                response = protocol.handle(request)
            except Exception as exc:
                response = {"ok": False, "error": str(exc)}
            self.wfile.write((json.dumps(response) + "\n").encode("utf-8"))
            self.wfile.flush()


class ThreadedBridgeServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler_class=_BridgeRequestHandler):
        super().__init__(server_address, handler_class)
        self.state = BridgeState()
        self.protocol = BridgeProtocol(self.state)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="OpenOCD TCP bridge for repo-local RI4 sessions")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9123)
    args = parser.parse_args(argv)

    with ThreadedBridgeServer((args.host, args.port)) as server:
        print(json.dumps({"listening": True, "host": args.host, "port": args.port}), flush=True)
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
