from pathlib import Path

from embeddyn.local.firmware import FirmwareAnalyzer


def test_raw_firmware_and_compare(tmp_path):
    first = tmp_path / "a.bin"
    second = tmp_path / "b.bin"
    first.write_bytes(b"Hello firmware\x00" + bytes(range(64)))
    second.write_bytes(b"Hello firmware\x00" + bytes(range(63)) + b"X")
    analyzer = FirmwareAnalyzer()
    report = analyzer.analyze(first, "arm")
    assert report["format"] == "Raw binary"
    assert report["size"] == first.stat().st_size
    assert any("Hello firmware" in item["value"] for item in report["strings"])
    comparison = analyzer.compare(first, second)
    assert comparison["changed_bytes"] >= 1


def test_intel_hex_detection(tmp_path):
    image = tmp_path / "test.hex"
    image.write_text(":0400000001020304F2\n:00000001FF\n")
    report = FirmwareAnalyzer().analyze(image)
    assert report["format"] == "Intel HEX"
    assert report["intel_hex"]["data_bytes"] == 4


def _intel_hex_record(address: int, record_type: int, payload: bytes) -> str:
    body = bytes([len(payload)]) + address.to_bytes(2, "big") + bytes([record_type]) + payload
    checksum = (-sum(body)) & 0xFF
    return ":" + (body + bytes([checksum])).hex().upper()


def test_standard_uf2_detection_and_block_validation(tmp_path):
    import struct

    block = bytearray(512)
    struct.pack_into(
        "<IIIIIIII",
        block,
        0,
        0x0A324655,
        0x9E5D5157,
        0,
        0x20000000,
        4,
        0,
        1,
        0xE48BFF56,
    )
    block[32:36] = b"UF2!"
    struct.pack_into("<I", block, 508, 0x0AB16F30)
    image = tmp_path / "valid.uf2"
    image.write_bytes(block)

    report = FirmwareAnalyzer().analyze(image)
    assert report["format"] == "UF2"
    assert report["uf2"]["block_count"] == 1
    assert report["uf2"]["invalid_blocks"] == 0
    assert report["uf2"]["address_min"] == 0x20000000


def test_intel_hex_ranges_are_order_independent_and_reject_bad_lengths(tmp_path):
    image = tmp_path / "out-of-order.hex"
    lines = [
        _intel_hex_record(0x1000, 0x00, b"ABCD"),
        _intel_hex_record(0x0000, 0x00, b"EFGH"),
        ":04000000010203F6",  # Declares four payload bytes but encodes only three.
        _intel_hex_record(0x0000, 0x01, b""),
    ]
    image.write_text("\n".join(lines) + "\n", encoding="ascii")
    report = FirmwareAnalyzer().analyze(image)["intel_hex"]
    assert report["ranges"] == [[0, 4], [0x1000, 0x1004]]
    assert report["data_bytes"] == 8
    assert any("length mismatch" in error for error in report["errors"])
