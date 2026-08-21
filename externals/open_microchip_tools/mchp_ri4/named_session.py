from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

from mchp_simulator.firmware_image import FirmwareImage, Segment

from .commands import Commands
from .device_file import DeviceFile
from .errors import Ri4ProtocolError
from .family_profiles import FamilyProfile, get_family_profile
from .icd4_comms_usb import ICD4CommsUsb
from .ri4_com import Ri4Com
from .transport import PyusbTransport


def _decode_le_u32(data: bytes) -> int:
    padded = data[:4].ljust(4, b"\x00")
    return int.from_bytes(padded, "little", signed=False)


@dataclass
class NamedScriptSession:
    PROGRAM_SCRIPT_TIMEOUT_MS = 30_000

    """Execute named RI4 scripts loaded from scripts.xml/tool.xml content."""

    commands: Commands
    device_file: DeviceFile
    tool_file: Optional[DeviceFile] = None
    tool: str = "RI4"
    processor: str = ""
    vid: Optional[int] = None
    pid: Optional[int] = None
    pc_bytes: int = 4
    family: Optional[str] = None
    profile: Optional[FamilyProfile] = None
    _hardware_points: Dict[int, Dict[str, Any]] = field(default_factory=dict, init=False, repr=False)

    DEFAULT_TRANSFER_CHUNK = 1024
    MAX_HARDWARE_POINTS = 16

    def __post_init__(self) -> None:
        if self.family is not None:
            self.family = self.family.strip().upper()
        if self.profile is None and self.family is not None:
            self.profile = get_family_profile(self.family)

    @classmethod
    def open_usb(
        cls,
        *,
        tool: str,
        processor: str,
        vid: int,
        pid: int,
        scripts_path: str,
        tool_scripts_path: Optional[str] = None,
        script_suffix: Optional[str] = None,
        pc_bytes: int = 4,
        family: Optional[str] = None,
    ) -> "NamedScriptSession":
        device_file = DeviceFile.from_xml_path(processor, scripts_path)
        if script_suffix:
            device_file.set_script_suffix(script_suffix)

        tool_file = None
        if tool_scripts_path:
            tool_file = DeviceFile.from_xml_path(processor, tool_scripts_path)
            if script_suffix:
                tool_file.set_script_suffix(script_suffix)

        comm = ICD4CommsUsb(Ri4Com(PyusbTransport(vid=vid, pid=pid)))
        return cls(
            commands=Commands(comm),
            device_file=device_file,
            tool_file=tool_file,
            tool=tool.upper(),
            processor=processor,
            vid=vid,
            pid=pid,
            pc_bytes=pc_bytes,
            family=family.strip().upper() if family else None,
            profile=get_family_profile(family),
        )

    def has_script(self, name: str) -> bool:
        return self._lookup_script(name) is not None

    def script_inventory(self) -> Dict[str, Any]:
        device_names = [script.method for script in self.device_file.getScripts()]
        tool_names = [script.method for script in self.tool_file.getScripts()] if self.tool_file is not None else []
        result = {
            "tool": self.tool,
            "processor": self.processor,
            "vid": None if self.vid is None else f"0x{self.vid:04X}",
            "pid": None if self.pid is None else f"0x{self.pid:04X}",
            "pcBytes": self.pc_bytes,
            "deviceScriptCount": len(device_names),
            "toolScriptCount": len(tool_names),
            "sampleScripts": sorted((device_names + tool_names))[:16],
        }
        if self.family is not None:
            result["family"] = self.family
        if self.profile is not None:
            result["profile"] = self.profile.to_dict()
        return result

    def close(self) -> None:
        self.commands.close()

    def run_script(self, name: str, *params: Any, timeout_ms: int = -1) -> Dict[str, Any]:
        script = self._require_script(name)
        result = self.commands.run_script_basic(script.getData(), *params, timeout_ms=timeout_ms)
        payload = result.payload.hex() if result.payload else ""
        return {"script": script.method, "status": result.status, "payloadHex": payload}

    def run_script_with_upload(self, name: str, expected_length: int, *params: Any) -> bytes:
        script = self._require_script(name)
        return self.commands.run_script_with_upload(script.getData(), expected_length, *params)

    def run_script_with_download(self, name: str, data: bytes, *params: Any, timeout_ms: int = -1) -> Dict[str, Any]:
        script = self._require_script(name)
        result = self.commands.run_script_with_download(script.getData(), data, *params, timeout_ms=timeout_ms)
        payload = result.payload.hex() if result.payload else ""
        return {"script": script.method, "status": result.status, "payloadHex": payload}

    def enter_debug_mode(self) -> Dict[str, Any]:
        candidates = self.profile.enter_debug_scripts if self.profile is not None else ("EnterDebugMode",)
        return self.run_first(candidates)

    def get_pc(self) -> Dict[str, Any]:
        candidates = self.profile.get_pc_scripts if self.profile is not None else ("GetPC",)
        data = self.run_first_with_upload(candidates, self.pc_bytes, (0, self.pc_bytes), ())
        return {"pc": _decode_le_u32(data), "rawHex": data.hex()}

    def set_pc(self, address: int) -> Dict[str, Any]:
        candidates = self.profile.set_pc_scripts if self.profile is not None else ("SetPC",)
        if not candidates:
            raise Ri4ProtocolError(f"Set PC is not modeled for family '{self.family or 'generic'}'")
        return self.run_first(candidates, address)

    def run_target(self) -> Dict[str, Any]:
        candidates = self.profile.run_scripts if self.profile is not None else ("Run",)
        return self.run_first(candidates)

    def step_target(self, *, ufex: bool = False) -> Dict[str, Any]:
        candidates = self.profile.step_scripts if self.profile is not None else ("SingleStep", "SingleStepUFEX")
        ordered = tuple(name for name in candidates if (not ufex or name == "SingleStepUFEX" or name == "SingleStep"))
        if ufex and self.has_script("SingleStepUFEX"):
            return self.run_script("SingleStepUFEX")
        return self.run_first(ordered or candidates)

    def halt_target(self) -> Dict[str, Any]:
        candidates = self.profile.halt_scripts if self.profile is not None else ("Halt",)
        return self.run_first(candidates)

    def target_status(self) -> Dict[str, Any]:
        raw_halted = self.commands.comm.get_status_value_from_key("Target Halted")
        normalized = raw_halted.strip().lower()
        if normalized in {"1", "true", "yes", "halted", "stopped"}:
            halted = True
        elif normalized in {"0", "false", "no", "running"}:
            halted = False
        else:
            raise Ri4ProtocolError(f"Unrecognized Target Halted status value: {raw_halted!r}")
        return {"halted": halted, "rawHalted": raw_halted}

    def erase_chip(self, mode: Optional[int] = None) -> Dict[str, Any]:
        candidates = self.profile.erase_scripts if self.profile is not None else ("EraseChip",)
        if mode is None:
            return self.run_first(candidates, timeout_ms=self.PROGRAM_SCRIPT_TIMEOUT_MS)
        return self.run_first(candidates, mode, timeout_ms=self.PROGRAM_SCRIPT_TIMEOUT_MS)

    def erase_target(self, mode: Optional[int] = None) -> Dict[str, Any]:
        program_entered = self.enter_programming_mode()
        try:
            erase_result = self.erase_chip(mode)
        finally:
            program_exited = self.exit_programming_mode()
        return {
            "erased": True,
            "eraseResult": erase_result,
            "programEntry": program_entered,
            "programExit": program_exited,
        }

    def set_hardware_breakpoint(self, address: int, *, slot: Optional[int] = None) -> Dict[str, Any]:
        resolved_slot = self._reserve_hardware_slot(slot)
        try:
            result = self.run_script("SetHWBP", resolved_slot, address)
        except Exception:
            self._hardware_points.pop(resolved_slot, None)
            raise
        point = {
            "slot": resolved_slot,
            "type": "execute",
            "address": int(address),
            "length": 1,
            "script": result["script"],
        }
        self._hardware_points[resolved_slot] = point
        return dict(point)

    def set_hardware_watchpoint(
        self,
        address: int,
        *,
        access: str = "access",
        length: int = 1,
        slot: Optional[int] = None,
    ) -> Dict[str, Any]:
        access_name = str(access).strip().lower()
        access_codes = {"read": 1, "write": 2, "access": 3}
        if access_name not in access_codes:
            raise Ri4ProtocolError("Watchpoint access must be 'read', 'write', or 'access'")
        if int(length) <= 0:
            raise Ri4ProtocolError("Watchpoint length must be positive")
        resolved_slot = self._reserve_hardware_slot(slot)
        try:
            result = self.run_script("SetDataHWBP", access_codes[access_name], resolved_slot, address)
        except Exception:
            self._hardware_points.pop(resolved_slot, None)
            raise
        point = {
            "slot": resolved_slot,
            "type": access_name,
            "address": int(address),
            "length": int(length),
            "script": result["script"],
        }
        self._hardware_points[resolved_slot] = point
        return dict(point)

    def clear_hardware_point(self, slot: int) -> Dict[str, Any]:
        resolved_slot = int(slot)
        if resolved_slot < 0:
            raise Ri4ProtocolError("Hardware breakpoint slot cannot be negative")
        previous = self._hardware_points.get(resolved_slot)
        result = self.run_script("ClearHWBP", resolved_slot)
        self._hardware_points.pop(resolved_slot, None)
        return {
            "slot": resolved_slot,
            "cleared": previous is not None,
            "previous": None if previous is None else dict(previous),
            "script": result["script"],
        }

    def list_hardware_points(self) -> list[Dict[str, Any]]:
        return [dict(self._hardware_points[slot]) for slot in sorted(self._hardware_points)]

    def read_program(self, address: int, length: int, *, script_name: str = "ReadProgmem") -> Dict[str, Any]:
        candidates = (script_name,) if script_name else ()
        if self.profile is not None and script_name == "ReadProgmem":
            candidates = self.profile.read_program_scripts
        elif not candidates:
            candidates = ("ReadProgmem",)
        data, used = self.run_first_with_upload_named(candidates, length, (address, length))
        return {"address": address, "length": len(data), "dataHex": data.hex(), "script": used}

    def write_program(self, address: int, data: bytes, *, script_name: str = "WriteProgmem") -> Dict[str, Any]:
        candidates = (script_name,) if script_name else ()
        if self.profile is not None and script_name == "WriteProgmem":
            candidates = self.profile.write_program_scripts
        elif not candidates:
            candidates = ("WriteProgmem",)
        return self.run_first_with_download(
            candidates,
            data,
            address,
            len(data),
            timeout_ms=self.PROGRAM_SCRIPT_TIMEOUT_MS,
        )

    def enter_programming_mode(self) -> Optional[Dict[str, Any]]:
        if self.profile is None or not self.profile.program_entry_scripts:
            return None
        self._preclean_scripting_engine()
        self._apply_icsp_speed_if_available()
        available = tuple(name for name in self.profile.program_entry_scripts if self.has_script(name))
        if not available:
            return None
        return self.run_first(available)

    def exit_programming_mode(self) -> Optional[Dict[str, Any]]:
        if self.profile is None or not self.profile.program_exit_scripts:
            return None
        available = tuple(name for name in self.profile.program_exit_scripts if self.has_script(name))
        if not available:
            return None
        return self.run_first(available)

    def verify_hex(self, path: str, *, chunk_size: int = DEFAULT_TRANSFER_CHUNK) -> Dict[str, Any]:
        image = FirmwareImage.from_path(path)
        chunk_size = self._validate_chunk_size(chunk_size)
        program_entered = self.enter_programming_mode()
        segments = []
        try:
            for segment in image.segments:
                read_scripts = []
                for offset, expected in self._iter_chunks(segment.data, chunk_size):
                    address = segment.address + offset
                    read_result = self.read_program(address, len(expected))
                    actual = bytes.fromhex(str(read_result["dataHex"]))
                    read_scripts.append(str(read_result["script"]))
                    if actual != expected:
                        mismatch = next(
                            (index for index, pair in enumerate(zip(expected, actual)) if pair[0] != pair[1]),
                            min(len(expected), len(actual)),
                        )
                        expected_byte = expected[mismatch] if mismatch < len(expected) else None
                        actual_byte = actual[mismatch] if mismatch < len(actual) else None
                        raise Ri4ProtocolError(
                            "Verify failed at "
                            f"0x{address + mismatch:x}: expected "
                            f"{self._format_byte(expected_byte)} got {self._format_byte(actual_byte)}"
                        )
                segments.append(
                    {
                        "address": segment.address,
                        "size": len(segment.data),
                        "readScripts": read_scripts,
                    }
                )
        finally:
            program_exited = self.exit_programming_mode()

        return {
            "imagePath": path,
            "segmentCount": len(segments),
            "segments": segments,
            "verified": True,
            "programEntry": program_entered,
            "programExit": program_exited,
        }

    def program_hex(
        self,
        path: str,
        *,
        erase_first: bool = True,
        verify: bool = False,
        chunk_size: int = DEFAULT_TRANSFER_CHUNK,
    ) -> Dict[str, Any]:
        image = FirmwareImage.from_path(path)
        chunk_size = self._validate_chunk_size(chunk_size)
        program_entered = self.enter_programming_mode()

        segments = []
        erase_result = None
        try:
            if erase_first:
                erase_result = self.erase_chip()

            for segment in image.segments:
                write_scripts = []
                for offset, data in self._iter_chunks(segment.data, chunk_size):
                    write_result = self.write_program(segment.address + offset, data)
                    write_scripts.append(str(write_result["script"]))
                segments.append(
                    {
                        "address": segment.address,
                        "size": len(segment.data),
                        "writeScripts": write_scripts,
                        "writeScript": write_scripts[0] if write_scripts else None,
                    }
                )

            if verify:
                for segment in image.segments:
                    for offset, expected in self._iter_chunks(segment.data, chunk_size):
                        address = segment.address + offset
                        read_result = self.read_program(address, len(expected))
                        actual = bytes.fromhex(str(read_result["dataHex"]))
                        if actual != expected:
                            mismatch = next(
                                (index for index, pair in enumerate(zip(expected, actual)) if pair[0] != pair[1]),
                                min(len(expected), len(actual)),
                            )
                            expected_byte = expected[mismatch] if mismatch < len(expected) else None
                            actual_byte = actual[mismatch] if mismatch < len(actual) else None
                            raise Ri4ProtocolError(
                                "Verify failed at "
                                f"0x{address + mismatch:x}: expected "
                                f"{self._format_byte(expected_byte)} got {self._format_byte(actual_byte)}"
                            )
        finally:
            program_exited = self.exit_programming_mode()

        return {
            "imagePath": path,
            "segmentCount": len(segments),
            "segments": segments,
            "erased": erase_first,
            "eraseResult": erase_result,
            "verified": verify,
            "programEntry": program_entered,
            "programExit": program_exited,
        }

    def _reserve_hardware_slot(self, requested: Optional[int]) -> int:
        if requested is not None:
            slot = int(requested)
            if slot < 0:
                raise Ri4ProtocolError("Hardware breakpoint slot cannot be negative")
            if slot in self._hardware_points:
                raise Ri4ProtocolError(f"Hardware breakpoint slot {slot} is already in use")
            self._hardware_points[slot] = {}
            return slot
        for slot in range(self.MAX_HARDWARE_POINTS):
            if slot not in self._hardware_points:
                self._hardware_points[slot] = {}
                return slot
        raise Ri4ProtocolError(f"No free hardware breakpoint slots (limit {self.MAX_HARDWARE_POINTS})")

    @staticmethod
    def _validate_chunk_size(chunk_size: int) -> int:
        value = int(chunk_size)
        if value <= 0:
            raise Ri4ProtocolError("Transfer chunk size must be positive")
        return value

    @staticmethod
    def _iter_chunks(data: bytes, chunk_size: int) -> Iterable[Tuple[int, bytes]]:
        for offset in range(0, len(data), chunk_size):
            yield offset, data[offset : offset + chunk_size]

    @staticmethod
    def _format_byte(value: Optional[int]) -> str:
        return "<missing>" if value is None else f"0x{value:02x}"

    def run_first(self, script_names: Sequence[str], *params: Any, timeout_ms: int = -1) -> Dict[str, Any]:
        last_error: Optional[Exception] = None
        for name in script_names:
            if not self.has_script(name):
                continue
            try:
                return self.run_script(name, *params, timeout_ms=timeout_ms)
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise Ri4ProtocolError(
            f"None of the candidate scripts are available for processor '{self.processor}': {', '.join(script_names)}"
        )

    def run_first_with_upload(
        self,
        script_names: Sequence[str],
        expected_length: int,
        primary_params: Sequence[Any],
        secondary_params: Sequence[Any] = (),
    ) -> bytes:
        data, _ = self.run_first_with_upload_named(script_names, expected_length, tuple(primary_params), tuple(secondary_params))
        return data

    def run_first_with_upload_named(
        self,
        script_names: Sequence[str],
        expected_length: int,
        primary_params: Sequence[Any],
        secondary_params: Sequence[Any] = (),
    ) -> Tuple[bytes, str]:
        last_error: Optional[Exception] = None
        param_sets = [tuple(primary_params)]
        if secondary_params:
            param_sets.append(tuple(secondary_params))
        for name in script_names:
            if not self.has_script(name):
                continue
            for params in param_sets:
                try:
                    return self.run_script_with_upload(name, expected_length, *params), name
                except Exception as exc:
                    last_error = exc
        if last_error is not None:
            raise last_error
        raise Ri4ProtocolError(
            f"None of the candidate upload scripts are available for processor '{self.processor}': {', '.join(script_names)}"
        )

    def run_first_with_download(
        self,
        script_names: Sequence[str],
        data: bytes,
        *params: Any,
        timeout_ms: int = -1,
    ) -> Dict[str, Any]:
        last_error: Optional[Exception] = None
        for name in script_names:
            if not self.has_script(name):
                continue
            try:
                return self.run_script_with_download(name, data, *params, timeout_ms=timeout_ms)
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise Ri4ProtocolError(
            f"None of the candidate download scripts are available for processor '{self.processor}': {', '.join(script_names)}"
        )

    def _lookup_script(self, name: str):
        script = self.device_file.getScriptBasic(name)
        if script is not None:
            return script
        if self.tool_file is not None:
            return self.tool_file.getScriptBasic(name)
        return None

    def _apply_icsp_speed_if_available(self) -> None:
        if self.has_script("SetSpeedFromDevice"):
            last_error: Optional[Exception] = None
            for _ in range(2):
                try:
                    self.run_script("SetSpeedFromDevice")
                    return
                except Exception as exc:
                    last_error = exc
            if last_error is not None:
                raise last_error

    def _preclean_scripting_engine(self) -> None:
        abort = getattr(self.commands.comm, "abort_scripting_engine", None)
        if abort is None:
            return
        try:
            abort()
        except Exception:
            return

    def _effective_read_chunk_size(self, requested_chunk_size: int) -> int:
        effective_chunk_size = requested_chunk_size
        if self.profile is not None and self.profile.max_read_chunk_size > 0:
            effective_chunk_size = min(effective_chunk_size, self.profile.max_read_chunk_size)
        return effective_chunk_size

    def _effective_read_transfer_length(self, requested_length: int, max_chunk_size: int) -> int:
        fixed_window_size = self._fixed_read_window_size()
        if fixed_window_size > 0:
            return fixed_window_size
        width = self._program_data_width()
        if width <= 1:
            return requested_length
        aligned = ((requested_length + width - 1) // width) * width
        if aligned <= max_chunk_size:
            return aligned
        fallback = max_chunk_size - (max_chunk_size % width)
        if fallback <= 0:
            raise Ri4ProtocolError(
                f"Read chunk size {max_chunk_size} is too small for family '{self.family or 'generic'}' width {width}"
            )
        return fallback

    def _buffer_size_to_program_address(self, buffer_size: int) -> int:
        width = self._program_data_width()
        increment = self._program_address_increment()
        if width <= 1:
            return buffer_size
        if buffer_size % width != 0:
            raise Ri4ProtocolError(
                f"Read transfer length {buffer_size} is not aligned to family '{self.family or 'generic'}' width {width}"
            )
        return (buffer_size // width) * increment

    def _program_data_width(self) -> int:
        if self.profile is None:
            return 1
        return max(1, self.profile.program_data_width)

    def _program_address_increment(self) -> int:
        if self.profile is None:
            return 1
        return max(1, self.profile.program_address_increment)

    def _fixed_read_window_size(self) -> int:
        if self.profile is None:
            return 0
        return max(0, self.profile.fixed_read_window_size)

    def _require_script(self, name: str):
        script = self._lookup_script(name)
        if script is None:
            raise Ri4ProtocolError(f"Script '{name}' not found for processor '{self.processor}'")
        return script
