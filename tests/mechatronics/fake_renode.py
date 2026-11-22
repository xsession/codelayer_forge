"""In-process fake of Renode's External Control server for adapter tests.

It implements the same binary framing as
``src/Renode/Network/ExternalControl/ExternalControlServer.cs`` (custom-cores
branch) and a tiny "firmware": every RunFor it reads ADC channel 0 (speed
sensor), computes a proportional PWM duty, and emits GPIO edge events for each
PWM period with virtual-time timestamps, like a timer-driven PWM pin would.
"""
from __future__ import annotations

import socket
import struct
import threading

VERSIONS = {1: 0, 2: 0, 3: 0, 4: 0, 5: 1, 6: 0}
OK_DATA, OK, HANDSHAKE, EVENT, FAILED, FATAL = 3, 4, 5, 6, 0, 1

TIM_CCR = 0x40000034
TIM_ARR = 0x4000002C


class FakeRenode:
    def __init__(self, machine: str = "stm32", pwm_period_us: int = 100, target_counts: int = 800,
                 kp: float = 0.002) -> None:
        self.machine_name = machine
        self.period = pwm_period_us
        self.target_counts, self.kp = target_counts, kp
        self.time_us = 0
        self.adc = {0: 0}
        self.gpio_in: dict[int, bool] = {}
        self.pwm_pin = 8
        self.pwm_level = False
        self.duty = 0.0
        self.memory = {TIM_ARR: 999, TIM_CCR: 0}
        self.subscriptions: dict[int, int] = {}  # pin -> descriptor
        self.run_for_calls: list[int] = []
        self.server = socket.socket()
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(1)
        self.port = self.server.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    # -------------------------------------------------------------- firmware model
    def _firmware_tick(self) -> None:
        error = self.target_counts - self.adc.get(0, 0)
        self.duty = max(0.0, min(1.0, self.kp * error))
        self.memory[TIM_CCR] = round(self.duty * (self.memory[TIM_ARR] + 1))

    def _run(self, conn: socket.socket, interval: int) -> None:
        self.run_for_calls.append(interval)
        self._firmware_tick()
        end = self.time_us + interval
        t = self.time_us
        while t < end:
            period_start = t - (t % self.period)
            high_until = period_start + round(self.duty * self.period)
            level = t < high_until
            next_change = high_until if level else period_start + self.period
            if level != self.pwm_level:
                self._set_pwm(conn, level, t)
            t = min(end, max(next_change, t + 1))
        self.time_us = end

    def _set_pwm(self, conn: socket.socket, level: bool, t: int) -> None:
        self.pwm_level = level
        descriptor = self.subscriptions.get(self.pwm_pin)
        if descriptor is not None:
            data = struct.pack("<Q?7x", t, level)  # C# EventData: ulong + bool, padded
            conn.sendall(struct.pack("<BBiI", EVENT, 5, descriptor, len(data)) + data)

    # -------------------------------------------------------------- protocol
    def _serve(self) -> None:
        conn, _ = self.server.accept()
        with conn:
            try:
                count = struct.unpack("<H", self._recv(conn, 2))[0]
                for _ in range(count):
                    cmd, ver = self._recv(conn, 2)
                    if VERSIONS.get(cmd) != ver:
                        msg = f"Encountered invalid version (0x{ver:X}) for {cmd}".encode()
                        conn.sendall(struct.pack("<BI", FATAL, len(msg)) + msg)
                        return
                conn.sendall(bytes([HANDSHAKE]))
                while True:
                    header = self._recv(conn, 7)
                    assert header[:2] == b"RE"
                    cmd, size = struct.unpack("<BI", header[2:])
                    payload = self._recv(conn, size)
                    conn.sendall(self._handle(conn, cmd, payload))
            except ConnectionError:
                return

    @staticmethod
    def _recv(conn: socket.socket, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                raise ConnectionError
            buf += chunk
        return buf

    @staticmethod
    def _ok(cmd: int, data: bytes | None = None) -> bytes:
        if data:
            return struct.pack("<BBI", OK_DATA, cmd, len(data)) + data
        return bytes([OK, cmd])

    @staticmethod
    def _fail(cmd: int, msg: str) -> bytes:
        raw = msg.encode()
        return struct.pack("<BBI", FAILED, cmd, len(raw)) + raw

    def _handle(self, conn: socket.socket, cmd: int, p: bytes) -> bytes:
        if cmd == 1:
            self._run(conn, struct.unpack("<Q", p)[0])
            return self._ok(cmd)
        if cmd == 2:
            return self._ok(cmd, struct.pack("<Q", self.time_us))
        if cmd == 3:
            (n,) = struct.unpack_from("<i", p)
            name = p[4:4 + n].decode()
            return self._ok(cmd, struct.pack("<i", 0)) if name == self.machine_name else self._fail(cmd, "Machine not found")
        instance = struct.unpack_from("<i", p)[0]
        if instance == -1:  # registration: machine id + name
            return self._ok(cmd, struct.pack("<i", 7))
        body = p[4:]
        if cmd == 4:
            op = body[0]
            if op == 0:
                return self._ok(cmd, struct.pack("<i", 4))
            channel = struct.unpack_from("<i", body, 1)[0]
            if op == 1:
                return self._ok(cmd, struct.pack("<I", self.adc.get(channel, 0)))
            self.adc[channel] = struct.unpack_from("<I", body, 5)[0]
            return self._ok(cmd)
        if cmd == 5:
            op, pin = body[0], struct.unpack_from("<i", body, 1)[0]
            if op == 0:
                return self._ok(cmd, bytes([self.pwm_level if pin == self.pwm_pin else 0]))
            if op == 1:
                self.gpio_in[pin] = bool(body[5])
                return self._ok(cmd)
            self.subscriptions[pin] = struct.unpack_from("<i", body, 5)[0]
            return self._ok(cmd)
        if cmd == 6:
            op, width, address, count = struct.unpack_from("<BBQI", body)
            fmt = {1: "<B", 2: "<H", 4: "<I", 8: "<Q"}[width]
            if op == 0:
                return self._ok(cmd, struct.pack(fmt, self.memory.get(address, 0)))
            self.memory[address] = struct.unpack_from(fmt, body, 14)[0]
            return self._ok(cmd)
        return bytes([2, cmd])

    def close(self) -> None:
        self.server.close()
