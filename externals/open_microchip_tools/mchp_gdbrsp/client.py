from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Union

from .rsp import (
    RspChecksumError,
    RspProtocolError,
    RspStreamParser,
    ascii_payload,
    encode_packet,
    hex_to_bytes,
    iter_kv_semi,
)


@dataclass(frozen=True)
class StopReply:
    raw: str
    kind: str
    signal: Optional[int] = None


class GdbRemoteClient:
    """Minimal GDB RSP client for talking to an RSP server (e.g. OpenOCD).

    This is intentionally small: enough for basic connect, memory read/write,
    continue/step, breakpoints, and stop-reply parsing.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 3333,
        timeout: float = 3.0,
        try_no_ack: bool = True,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.try_no_ack = try_no_ack

        self._sock: Optional[socket.socket] = None
        self._parser = RspStreamParser()
        self._no_ack = False

    def connect(self) -> Dict[str, str]:
        if self._sock is not None:
            return {}
        s = socket.create_connection((self.host, self.port), timeout=self.timeout)
        s.settimeout(self.timeout)
        self._sock = s

        # Basic capability discovery.
        supported = self.qSupported()
        if self.try_no_ack and supported.get("QStartNoAckMode") == "+":
            if self._send_and_expect_ok("QStartNoAckMode"):
                self._no_ack = True
        return supported

    def close(self) -> None:
        if self._sock is None:
            return
        try:
            self._sock.close()
        finally:
            self._sock = None
            self._no_ack = False

    def __enter__(self) -> "GdbRemoteClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def interrupt(self) -> None:
        self._require_sock()
        self._sock.sendall(b"\x03")

    def qSupported(self) -> Dict[str, str]:
        reply = self.send_command("qSupported")
        text = reply.decode("ascii", errors="replace")
        out: Dict[str, str] = {}
        for part in iter_kv_semi(text):
            if "=" in part:
                k, v = part.split("=", 1)
                out[k] = v
            elif part.endswith("+") or part.endswith("-"):
                out[part[:-1]] = part[-1]
            else:
                out[part] = ""
        return out

    def read_memory(self, addr: int, length: int) -> bytes:
        payload = f"m{addr:x},{length:x}".encode("ascii")
        reply = self.send_command(payload)
        text = reply.decode("ascii", errors="replace")
        if text.startswith("E"):
            raise RuntimeError(f"RSP error: {text}")
        return hex_to_bytes(text)

    def write_memory(self, addr: int, data: bytes) -> None:
        hexdata = data.hex()
        payload = f"M{addr:x},{len(data):x}:{hexdata}".encode("ascii")
        if not self._send_and_expect_ok(payload):
            raise RuntimeError("write_memory failed")

    def continue_exec(self, addr: Optional[int] = None) -> StopReply:
        payload = f"c{addr:x}".encode("ascii") if addr is not None else b"c"
        reply = self.send_command(payload)
        return self._parse_stop_reply(reply)

    def step(self, addr: Optional[int] = None) -> StopReply:
        payload = f"s{addr:x}".encode("ascii") if addr is not None else b"s"
        reply = self.send_command(payload)
        return self._parse_stop_reply(reply)

    def set_sw_breakpoint(self, addr: int, kind: int = 2) -> bool:
        return self._set_point(0, addr, kind)

    def clear_sw_breakpoint(self, addr: int, kind: int = 2) -> bool:
        return self._clear_point(0, addr, kind)

    def set_hw_breakpoint(self, addr: int, kind: int = 2) -> bool:
        return self._set_point(1, addr, kind)

    def clear_hw_breakpoint(self, addr: int, kind: int = 2) -> bool:
        return self._clear_point(1, addr, kind)

    def set_write_watchpoint(self, addr: int, length: int = 1) -> bool:
        return self._set_point(2, addr, length)

    def clear_write_watchpoint(self, addr: int, length: int = 1) -> bool:
        return self._clear_point(2, addr, length)

    def set_read_watchpoint(self, addr: int, length: int = 1) -> bool:
        return self._set_point(3, addr, length)

    def clear_read_watchpoint(self, addr: int, length: int = 1) -> bool:
        return self._clear_point(3, addr, length)

    def set_access_watchpoint(self, addr: int, length: int = 1) -> bool:
        return self._set_point(4, addr, length)

    def clear_access_watchpoint(self, addr: int, length: int = 1) -> bool:
        return self._clear_point(4, addr, length)

    def _set_point(self, point_type: int, addr: int, kind: int) -> bool:
        if addr < 0 or kind <= 0:
            raise ValueError("Breakpoint/watchpoint address must be non-negative and kind must be positive")
        payload = f"Z{point_type:x},{addr:x},{kind:x}".encode("ascii")
        return self._send_and_expect_ok(payload)

    def _clear_point(self, point_type: int, addr: int, kind: int) -> bool:
        if addr < 0 or kind <= 0:
            raise ValueError("Breakpoint/watchpoint address must be non-negative and kind must be positive")
        payload = f"z{point_type:x},{addr:x},{kind:x}".encode("ascii")
        return self._send_and_expect_ok(payload)

    def send_command(self, payload: Union[bytes, str]) -> bytes:
        self._require_sock()
        if isinstance(payload, str):
            payload_b = ascii_payload(payload)
        else:
            payload_b = payload
        self._send_packet(payload_b)
        return self._recv_packet()

    def _send_and_expect_ok(self, payload: Union[bytes, str]) -> bool:
        reply = self.send_command(payload)
        return reply == b"OK"

    def _send_packet(self, payload: bytes) -> None:
        self._require_sock()
        pkt = encode_packet(payload)
        while True:
            self._sock.sendall(pkt)
            if self._no_ack:
                return
            ack = self._recv_ack()
            if ack == b"+":
                return
            if ack == b"-":
                continue
            raise RspProtocolError(f"unexpected ack byte: {ack!r}")

    def _recv_ack(self) -> bytes:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            self._feed_from_socket()
            ack = self._parser.pop_ack()
            if ack is not None:
                return ack
        raise TimeoutError("timed out waiting for ack")

    def _recv_packet(self) -> bytes:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            self._feed_from_socket()
            pkt = self._parser.pop_packet()
            if pkt is None:
                continue
            if not self._no_ack:
                self._sock.sendall(b"+")
            return pkt.payload
        raise TimeoutError("timed out waiting for packet")

    def _feed_from_socket(self) -> None:
        self._require_sock()
        try:
            data = self._sock.recv(4096)
        except socket.timeout:
            return
        if not data:
            raise ConnectionError("RSP connection closed")
        try:
            self._parser.push(data)
        except (RspChecksumError, RspProtocolError):
            if not self._no_ack:
                try:
                    self._sock.sendall(b"-")
                except OSError:
                    pass
            raise

    def _parse_stop_reply(self, payload: bytes) -> StopReply:
        text = payload.decode("ascii", errors="replace")
        if not text:
            return StopReply(raw=text, kind="empty")
        if text[0] in ("S", "T") and len(text) >= 3:
            try:
                sig = int(text[1:3], 16)
            except ValueError:
                sig = None
            return StopReply(raw=text, kind=text[0], signal=sig)
        if text[0] in ("W", "X") and len(text) >= 3:
            return StopReply(raw=text, kind=text[0])
        return StopReply(raw=text, kind="other")

    def _require_sock(self) -> None:
        if self._sock is None:
            raise RuntimeError("not connected; call connect() first")
