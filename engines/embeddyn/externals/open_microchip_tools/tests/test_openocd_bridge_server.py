import unittest
from unittest.mock import patch

from mchp_openocd.bridge_server import BridgeError, BridgeProtocol, BridgeState


class TestOpenOcdBridgeProtocol(unittest.TestCase):
    def setUp(self) -> None:
        self.protocol = BridgeProtocol(BridgeState())

    def test_list_families(self):
        response = self.protocol.handle({"command": "listFamilies", "args": {}})
        self.assertTrue(response["ok"])
        self.assertGreaterEqual(len(response["result"]), 28)
        pic32 = next(entry for entry in response["result"] if entry["family"] == "PIC32MZ")
        self.assertIn("programmerLineage", pic32)
        pic16e = next(entry for entry in response["result"] if entry["family"] == "PIC16Enhanced")
        self.assertIn("target-vpp-control", pic16e["programmerRawCommandCapabilities"])
        self.assertIn("vpp-operational-value", pic16e["programmerRawCommandSignatures"])

    def test_list_families_can_filter_by_capability(self):
        response = self.protocol.handle(
            {"command": "listFamilies", "args": {"capabilities": ["target-vpp-control"]}}
        )
        self.assertTrue(response["ok"])
        families = {entry["family"] for entry in response["result"]}
        self.assertIn("PIC16Enhanced", families)
        self.assertTrue(response["result"])
        for entry in response["result"]:
            capabilities = set(entry["programmerRawCommandCapabilities"]) | set(entry["debuggerRawCommandCapabilities"])
            self.assertIn("target-vpp-control", capabilities)

    def test_list_families_can_require_all_capabilities(self):
        response = self.protocol.handle(
            {
                "command": "listFamilies",
                "args": {
                    "capabilities": ["target-vpp-control", "target-reset-pulse"],
                    "capabilityMatch": "all",
                },
            }
        )
        self.assertTrue(response["ok"])
        families = {entry["family"] for entry in response["result"]}
        self.assertIn("EFC_6450", families)
        self.assertNotIn("PIC16Enhanced", families)

    def test_list_families_can_filter_by_signature(self):
        response = self.protocol.handle(
            {"command": "listFamilies", "args": {"signatures": ["vpp-operational-value"]}}
        )
        self.assertTrue(response["ok"])
        self.assertTrue(response["result"])
        for entry in response["result"]:
            signatures = set(entry["programmerRawCommandSignatures"]) | set(entry["debuggerRawCommandSignatures"])
            self.assertIn("vpp-operational-value", signatures)

    def test_list_families_can_filter_by_group(self):
        response = self.protocol.handle(
            {"command": "listFamilies", "args": {"groups": ["trace"]}}
        )
        self.assertTrue(response["ok"])
        self.assertTrue(response["result"])
        for entry in response["result"]:
            groups = set(entry["programmerRawCommandGroups"]) | set(entry["debuggerRawCommandGroups"])
            self.assertIn("trace", groups)

    def test_list_families_can_filter_by_search_prefix(self):
        response = self.protocol.handle(
            {"command": "listFamilies", "args": {"searchPrefix": "ProgrammerPIC32"}}
        )
        self.assertTrue(response["ok"])
        self.assertTrue(response["result"])
        for entry in response["result"]:
            self.assertTrue(
                entry["family"].lower().startswith("programmerpic32")
                or entry["programmerClass"].lower().startswith("programmerpic32")
                or entry["debuggerClass"].lower().startswith("programmerpic32")
            )

    def test_start_session_dispatch(self):
        with patch("mchp_openocd.bridge_server.NamedScriptSession") as session_type:
            session = session_type.open_usb.return_value
            session.script_inventory.return_value = {"family": "PIC32MZ", "tool": "PK4"}
            response = self.protocol.handle(
                {
                    "command": "startSession",
                    "args": {
                        "tool": "pk4",
                        "vid": "0x04D8",
                        "pid": "0x9012",
                        "family": "PIC32MZ",
                        "processor": "PIC32MZ2048EFH",
                        "scriptsPath": "scripts.xml",
                    },
                }
            )

        self.assertTrue(response["ok"])
        self.assertEqual(response["result"]["family"], "PIC32MZ")

    def test_probe_tool_always_releases_usb_driver(self):
        with patch("mchp_openocd.bridge_server._tool_driver") as tool_driver:
            tool_driver.return_value.get_status_value.return_value = "0"
            response = self.protocol.handle(
                {
                    "command": "probeTool",
                    "args": {
                        "tool": "pk4",
                        "vid": "0x04D8",
                        "pid": "0x9012",
                        "keys": ["Commands in progress"],
                    },
                }
            )

        self.assertTrue(response["ok"])
        tool_driver.return_value.close.assert_called_once_with()

    def test_end_session_closes_active_session(self):
        session = self.protocol._state.session = unittest.mock.Mock()
        session.script_inventory.return_value = {"family": "PIC32MZ", "tool": "PK4"}

        response = self.protocol.handle({"command": "endSession", "args": {}})

        self.assertTrue(response["ok"])
        self.assertTrue(response["result"]["closed"])
        self.assertEqual(response["result"]["previousSession"]["family"], "PIC32MZ")
        session.close.assert_called_once_with()
        self.assertIsNone(self.protocol._state.session)

    def test_target_status_dispatch(self):
        session = self.protocol._state.session = unittest.mock.Mock()
        session.target_status.return_value = {"halted": True, "rawHalted": "1"}

        response = self.protocol.handle({"command": "targetStatus", "args": {}})

        self.assertTrue(response["result"]["halted"])
        session.target_status.assert_called_once_with()

    def test_start_session_replaces_existing_session(self):
        existing = self.protocol._state.session = unittest.mock.Mock()
        existing.script_inventory.return_value = {"family": "PIC16Enhanced", "tool": "PK4"}
        with patch("mchp_openocd.bridge_server.NamedScriptSession") as session_type:
            session = session_type.open_usb.return_value
            session.script_inventory.return_value = {"family": "PIC32MZ", "tool": "PK4"}

            response = self.protocol.handle(
                {
                    "command": "startSession",
                    "args": {
                        "tool": "pk4",
                        "vid": "0x04D8",
                        "pid": "0x9012",
                        "family": "PIC32MZ",
                        "processor": "PIC32MZ2048EFH",
                        "scriptsPath": "scripts.xml",
                    },
                }
            )

        self.assertTrue(response["ok"])
        existing.close.assert_called_once_with()

    def test_run_script_dispatches_basic_script(self):
        session = self.protocol._state.session = unittest.mock.Mock()
        session.run_script.return_value = {"script": "EnterDebugMode", "status": 0, "payloadHex": ""}

        response = self.protocol.handle(
            {"command": "runScript", "args": {"name": "EnterDebugMode", "params": [1, "two"], "timeoutMs": 10}}
        )

        self.assertTrue(response["ok"])
        session.run_script.assert_called_once_with("EnterDebugMode", 1, "two", timeout_ms=10)

    def test_run_script_dispatches_upload(self):
        session = self.protocol._state.session = unittest.mock.Mock()
        session.run_script_with_upload.return_value = b"\xAA\x55"

        response = self.protocol.handle(
            {"command": "runScript", "args": {"name": "GetPC", "uploadLength": 2, "params": [0, 2]}}
        )

        self.assertTrue(response["ok"])
        self.assertEqual(response["result"]["payloadHex"], "aa55")

    def test_run_script_rejects_upload_and_download_together(self):
        with self.assertRaisesRegex(BridgeError, "cannot be used together"):
            self.protocol.handle(
                {"command": "runScript", "args": {"name": "Bad", "uploadLength": 2, "downloadHex": "AA55"}}
            )

    def test_breakpoint_and_watchpoint_dispatch(self):
        session = self.protocol._state.session = unittest.mock.Mock()
        session.set_hardware_breakpoint.return_value = {"slot": 2, "type": "execute"}
        session.set_hardware_watchpoint.return_value = {"slot": 3, "type": "write"}

        bp = self.protocol.handle(
            {"command": "setBreakpoint", "args": {"address": "0x100", "slot": 2}}
        )
        wp = self.protocol.handle(
            {
                "command": "setWatchpoint",
                "args": {"address": "0x200", "slot": 3, "access": "write", "length": 4},
            }
        )

        self.assertTrue(bp["ok"])
        self.assertTrue(wp["ok"])
        session.set_hardware_breakpoint.assert_called_once_with(0x100, slot=2)
        session.set_hardware_watchpoint.assert_called_once_with(0x200, access="write", length=4, slot=3)

    def test_verify_hex_dispatch(self):
        session = self.protocol._state.session = unittest.mock.Mock()
        session.verify_hex.return_value = {"verified": True}

        response = self.protocol.handle(
            {"command": "verifyHex", "args": {"path": "firmware.hex", "chunkSize": 256}}
        )

        self.assertTrue(response["result"]["verified"])
        session.verify_hex.assert_called_once_with("firmware.hex", chunk_size=256)
