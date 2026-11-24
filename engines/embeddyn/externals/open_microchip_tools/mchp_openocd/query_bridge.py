from __future__ import annotations

import argparse
import copy
import json
import socket
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


def build_list_families_request(args: argparse.Namespace) -> Dict[str, object]:
    request_args: Dict[str, object] = {}
    if args.search_prefix:
        request_args["searchPrefix"] = args.search_prefix
    if args.capability:
        request_args["capabilities"] = list(args.capability)
    if args.signature:
        request_args["signatures"] = list(args.signature)
    if args.group:
        request_args["groups"] = list(args.group)
    if args.capability_match != "any":
        request_args["capabilityMatch"] = args.capability_match
    if args.signature_match != "any":
        request_args["signatureMatch"] = args.signature_match
    if args.group_match != "any":
        request_args["groupMatch"] = args.group_match
    return {"command": "listFamilies", "args": request_args}


def build_probe_tool_request(args: argparse.Namespace) -> Dict[str, object]:
    request_args: Dict[str, object] = {
        "tool": args.tool,
        "vid": args.vid,
        "pid": args.pid,
    }
    if args.key:
        request_args["keys"] = list(args.key)
    return {"command": "probeTool", "args": request_args}


def build_start_session_request(args: argparse.Namespace) -> Dict[str, object]:
    request_args: Dict[str, object] = {
        "tool": args.tool,
        "vid": args.vid,
        "pid": args.pid,
        "processor": args.processor,
        "scriptsPath": args.scripts_path,
    }
    if args.tool_scripts_path:
        request_args["toolScriptsPath"] = args.tool_scripts_path
    if args.script_suffix:
        request_args["scriptSuffix"] = args.script_suffix
    if args.pc_bytes != 4:
        request_args["pcBytes"] = args.pc_bytes
    if args.family:
        request_args["family"] = args.family
    return {"command": "startSession", "args": request_args}


def build_session_status_request(args: argparse.Namespace) -> Dict[str, object]:
    return {"command": "sessionStatus", "args": {}}


def build_target_status_request(args: argparse.Namespace) -> Dict[str, object]:
    return {"command": "targetStatus", "args": {}}


def build_end_session_request(args: argparse.Namespace) -> Dict[str, object]:
    return {"command": "endSession", "args": {}}


def build_enter_debug_mode_request(args: argparse.Namespace) -> Dict[str, object]:
    return {"command": "enterDebugMode", "args": {}}


def build_get_pc_request(args: argparse.Namespace) -> Dict[str, object]:
    return {"command": "getPc", "args": {}}


def build_set_pc_request(args: argparse.Namespace) -> Dict[str, object]:
    return {"command": "setPc", "args": {"address": args.address}}


def build_run_script_request(args: argparse.Namespace) -> Dict[str, object]:
    request_args: Dict[str, object] = {"name": args.name}
    if args.param:
        request_args["params"] = [_parse_cli_param(value) for value in args.param]
    if args.timeout_ms != -1:
        request_args["timeoutMs"] = args.timeout_ms
    if args.upload_length is not None:
        request_args["uploadLength"] = args.upload_length
    if args.download_hex is not None:
        request_args["downloadHex"] = args.download_hex
    return {"command": "runScript", "args": request_args}


def build_run_request(args: argparse.Namespace) -> Dict[str, object]:
    return {"command": "run", "args": {}}


def build_step_request(args: argparse.Namespace) -> Dict[str, object]:
    request_args: Dict[str, object] = {}
    if args.ufex:
        request_args["ufex"] = True
    return {"command": "step", "args": request_args}


def build_halt_request(args: argparse.Namespace) -> Dict[str, object]:
    return {"command": "halt", "args": {}}


def build_erase_chip_request(args: argparse.Namespace) -> Dict[str, object]:
    request_args: Dict[str, object] = {}
    if args.mode is not None:
        request_args["mode"] = args.mode
    return {"command": "eraseChip", "args": request_args}


def build_program_hex_request(args: argparse.Namespace) -> Dict[str, object]:
    request_args: Dict[str, object] = {"path": args.path}
    if not args.erase_first:
        request_args["eraseFirst"] = False
    if args.verify:
        request_args["verify"] = True
    chunk_size = getattr(args, "chunk_size", 1024)
    if chunk_size != 1024:
        request_args["chunkSize"] = chunk_size
    return {"command": "programHex", "args": request_args}


def build_verify_hex_request(args: argparse.Namespace) -> Dict[str, object]:
    request_args: Dict[str, object] = {"path": args.path}
    chunk_size = getattr(args, "chunk_size", 1024)
    if chunk_size != 1024:
        request_args["chunkSize"] = chunk_size
    return {"command": "verifyHex", "args": request_args}


def build_set_breakpoint_request(args: argparse.Namespace) -> Dict[str, object]:
    request_args: Dict[str, object] = {"address": args.address}
    if args.slot is not None:
        request_args["slot"] = args.slot
    return {"command": "setBreakpoint", "args": request_args}


def build_set_watchpoint_request(args: argparse.Namespace) -> Dict[str, object]:
    request_args: Dict[str, object] = {
        "address": args.address,
        "access": args.access,
        "length": args.length,
    }
    if args.slot is not None:
        request_args["slot"] = args.slot
    return {"command": "setWatchpoint", "args": request_args}


def build_clear_hardware_point_request(args: argparse.Namespace) -> Dict[str, object]:
    return {"command": "clearHardwarePoint", "args": {"slot": args.slot}}


def build_list_hardware_points_request(args: argparse.Namespace) -> Dict[str, object]:
    return {"command": "listHardwarePoints", "args": {}}


def build_read_program_request(args: argparse.Namespace) -> Dict[str, object]:
    return {
        "command": "readProgram",
        "args": {
            "address": args.address,
            "size": args.size,
        },
    }


def build_write_program_request(args: argparse.Namespace) -> Dict[str, object]:
    return {
        "command": "writeProgram",
        "args": {
            "address": args.address,
            "dataHex": args.data_hex,
        },
    }


def _substitute_batch_value(value: Any, variables: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        result = value
        for key, replacement in variables.items():
            result = result.replace("${" + key + "}", replacement)
        return result
    if isinstance(value, list):
        return [_substitute_batch_value(item, variables) for item in value]
    if isinstance(value, dict):
        return {str(k): _substitute_batch_value(v, variables) for k, v in value.items()}
    return value


def _parse_cli_vars(raw_vars: Optional[List[str]]) -> Dict[str, str]:
    variables: Dict[str, str] = {}
    for item in raw_vars or []:
        if "=" not in item:
            raise RuntimeError(f"Invalid --var value '{item}'. Expected NAME=VALUE")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise RuntimeError("Batch variable names cannot be empty")
        variables[key] = value
    return variables


def load_batch_requests(path: str, cli_vars: Optional[List[str]] = None) -> tuple[list[Dict[str, object]], bool]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    stop_on_error = True
    requests: object = payload
    variables: Dict[str, str] = {}
    if isinstance(payload, dict):
        requests = payload.get("requests")
        stop_on_error = bool(payload.get("stopOnError", True))
        raw_variables = payload.get("variables", {})
        if raw_variables is not None:
            if not isinstance(raw_variables, dict) or not all(
                isinstance(key, str) and isinstance(value, str) for key, value in raw_variables.items()
            ):
                raise RuntimeError("Batch file variables must be an object with string values")
            variables.update(raw_variables)
    if not isinstance(requests, list) or not all(isinstance(item, dict) for item in requests):
        raise RuntimeError("Batch file must contain a list of request objects or an object with a 'requests' list")
    variables.update(_parse_cli_vars(cli_vars))
    substituted = [_substitute_batch_value(copy.deepcopy(item), variables) for item in requests]
    return substituted, stop_on_error


def send_batch_requests(
    host: str,
    port: int,
    requests: List[Dict[str, object]],
    *,
    stop_on_error: bool = True,
) -> List[Dict[str, object]]:
    responses: List[Dict[str, object]] = []
    for request in requests:
        response = send_request(host, port, request)
        responses.append(response)
        if stop_on_error and not response.get("ok", False):
            break
    return responses


def send_request(host: str, port: int, request: Dict[str, object]) -> Dict[str, object]:
    payload = json.dumps(request).encode("utf-8") + b"\n"
    with socket.create_connection((host, port)) as sock:
        sock.sendall(payload)
        reader = sock.makefile("rb")
        try:
            line = reader.readline()
        finally:
            reader.close()
    if not line:
        raise RuntimeError("Bridge closed the connection without returning a response")
    response = json.loads(line.decode("utf-8"))
    if not isinstance(response, dict):
        raise RuntimeError("Bridge returned a non-object response")
    return response


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query the repo-local OpenOCD RI4 bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9123)
    parser.add_argument("--compact", action="store_true", help="Emit compact JSON instead of pretty-printed output")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_families = subparsers.add_parser("list-families", help="Query bridge family inventory")
    list_families.add_argument("--search-prefix", default="")
    list_families.add_argument("--capability", action="append", default=[])
    list_families.add_argument("--signature", action="append", default=[])
    list_families.add_argument("--group", action="append", default=[])
    list_families.add_argument("--capability-match", choices=["any", "all"], default="any")
    list_families.add_argument("--signature-match", choices=["any", "all"], default="any")
    list_families.add_argument("--group-match", choices=["any", "all"], default="any")
    list_families.set_defaults(build_request=build_list_families_request)

    probe_tool = subparsers.add_parser("probe-tool", help="Query tool status values from the bridge")
    probe_tool.add_argument("--tool", required=True, choices=["pk4", "icd4"])
    probe_tool.add_argument("--vid", required=True)
    probe_tool.add_argument("--pid", required=True)
    probe_tool.add_argument("--key", action="append", default=[])
    probe_tool.set_defaults(build_request=build_probe_tool_request)

    start_session = subparsers.add_parser("start-session", help="Open a bridge hardware session")
    start_session.add_argument("--tool", required=True, choices=["pk4", "icd4"])
    start_session.add_argument("--vid", required=True)
    start_session.add_argument("--pid", required=True)
    start_session.add_argument("--processor", required=True)
    start_session.add_argument("--scripts-path", required=True)
    start_session.add_argument("--tool-scripts-path", default="")
    start_session.add_argument("--script-suffix", default="")
    start_session.add_argument("--pc-bytes", type=int, default=4)
    start_session.add_argument("--family", default="")
    start_session.set_defaults(build_request=build_start_session_request)

    session_status = subparsers.add_parser("session-status", help="Get the current bridge session inventory")
    session_status.set_defaults(build_request=build_session_status_request)

    target_status = subparsers.add_parser("target-status", help="Query whether the active target is halted")
    target_status.set_defaults(build_request=build_target_status_request)

    end_session = subparsers.add_parser("end-session", help="Close the active bridge session")
    end_session.set_defaults(build_request=build_end_session_request)

    enter_debug_mode = subparsers.add_parser("enter-debug-mode", help="Enter debug mode on the active session")
    enter_debug_mode.set_defaults(build_request=build_enter_debug_mode_request)

    get_pc = subparsers.add_parser("get-pc", help="Read the program counter from the active session")
    get_pc.set_defaults(build_request=build_get_pc_request)

    set_pc = subparsers.add_parser("set-pc", help="Set the program counter on the active session")
    set_pc.add_argument("--address", required=True)
    set_pc.set_defaults(build_request=build_set_pc_request)

    run_script = subparsers.add_parser("run-script", help="Run an arbitrary named RI4 script on the active session")
    run_script.add_argument("name")
    run_script.add_argument("--param", action="append", default=[])
    run_script.add_argument("--timeout-ms", type=int, default=-1)
    run_script.add_argument("--upload-length", type=int)
    run_script.add_argument("--download-hex")
    run_script.set_defaults(build_request=build_run_script_request)

    run = subparsers.add_parser("run", help="Resume target execution")
    run.set_defaults(build_request=build_run_request)

    step = subparsers.add_parser("step", help="Single-step target execution")
    step.add_argument("--ufex", action="store_true")
    step.set_defaults(build_request=build_step_request)

    halt = subparsers.add_parser("halt", help="Halt target execution")
    halt.set_defaults(build_request=build_halt_request)

    erase_chip = subparsers.add_parser("erase-chip", help="Erase the target through the active session")
    erase_chip.add_argument("--mode", type=_parse_cli_int)
    erase_chip.set_defaults(build_request=build_erase_chip_request)

    program_hex = subparsers.add_parser("program-hex", help="Program a HEX file through the active session")
    program_hex.add_argument("path")
    program_hex.add_argument("--no-erase", dest="erase_first", action="store_false")
    program_hex.add_argument("--verify", action="store_true")
    program_hex.add_argument("--chunk-size", type=int, default=1024)
    program_hex.set_defaults(erase_first=True, build_request=build_program_hex_request)

    verify_hex = subparsers.add_parser("verify-hex", help="Verify target program memory against a HEX file")
    verify_hex.add_argument("path")
    verify_hex.add_argument("--chunk-size", type=int, default=1024)
    verify_hex.set_defaults(build_request=build_verify_hex_request)

    read_program = subparsers.add_parser("read-program", help="Read program memory through the active session")
    read_program.add_argument("--address", required=True)
    read_program.add_argument("--size", required=True)
    read_program.set_defaults(build_request=build_read_program_request)

    write_program = subparsers.add_parser("write-program", help="Write program memory through the active session")
    write_program.add_argument("--address", required=True)
    write_program.add_argument("--data-hex", required=True)
    write_program.set_defaults(build_request=build_write_program_request)

    set_breakpoint = subparsers.add_parser("set-breakpoint", help="Set a hardware execute breakpoint")
    set_breakpoint.add_argument("--address", required=True)
    set_breakpoint.add_argument("--slot", type=int)
    set_breakpoint.set_defaults(build_request=build_set_breakpoint_request)

    set_watchpoint = subparsers.add_parser("set-watchpoint", help="Set a hardware data watchpoint")
    set_watchpoint.add_argument("--address", required=True)
    set_watchpoint.add_argument("--access", choices=["read", "write", "access"], default="access")
    set_watchpoint.add_argument("--length", type=int, default=1)
    set_watchpoint.add_argument("--slot", type=int)
    set_watchpoint.set_defaults(build_request=build_set_watchpoint_request)

    clear_hardware_point = subparsers.add_parser(
        "clear-hardware-point", help="Clear a hardware breakpoint or watchpoint slot"
    )
    clear_hardware_point.add_argument("--slot", required=True, type=int)
    clear_hardware_point.set_defaults(build_request=build_clear_hardware_point_request)

    list_hardware_points = subparsers.add_parser(
        "list-hardware-points", help="List active hardware breakpoints and watchpoints"
    )
    list_hardware_points.set_defaults(build_request=build_list_hardware_points_request)

    batch = subparsers.add_parser("batch", help="Replay a JSON list of bridge requests")
    batch.add_argument("path", help="Path to a JSON file containing bridge request objects")
    batch.add_argument("--keep-going", action="store_true", help="Continue after bridge errors in the batch")
    batch.add_argument("--var", action="append", default=[], help="Substitute ${NAME} placeholders in the batch file")
    batch.set_defaults(build_request=None)
    return parser


def _parse_cli_int(value: str) -> int:
    return int(value, 0)


def _parse_cli_param(value: str) -> object:
    try:
        return _parse_cli_int(value)
    except ValueError:
        pass
    lowered = value.lower()
    if lowered in {"true", "false", "null"} or value.startswith(("[", "{", '"')):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


def _normalize_args(args: argparse.Namespace) -> None:
    if hasattr(args, "address") and isinstance(args.address, str):
        args.address = _parse_cli_int(args.address)
    if hasattr(args, "size") and isinstance(args.size, str):
        args.size = _parse_cli_int(args.size)


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _normalize_args(args)
    if args.command == "batch":
        requests, stop_on_error = load_batch_requests(args.path, args.var)
        responses = send_batch_requests(args.host, args.port, requests, stop_on_error=stop_on_error and not args.keep_going)
        if args.compact:
            print(json.dumps(responses, sort_keys=True))
        else:
            print(json.dumps(responses, indent=2, sort_keys=True))
        return 0
    build_request = getattr(args, "build_request", None)
    if not callable(build_request):
        parser.error(f"Unsupported command: {args.command}")
    response = send_request(args.host, args.port, build_request(args))
    if args.compact:
        print(json.dumps(response, sort_keys=True))
    else:
        print(json.dumps(response, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
