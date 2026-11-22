from pathlib import Path

import pytest

from embeddyn.mechatronics.adapters.renode import RenodeAdapter, load_renode_bindings
from embeddyn.mechatronics.adapters.renode_api import RenodeApiError, RenodeExternalControl
from embeddyn.mechatronics.factory import build_adapters
from embeddyn.mechatronics.model import Domain, MechatronicProject
from embeddyn.mechatronics.orchestrator import CoSimulationOrchestrator

from tests.mechatronics.fake_renode import TIM_ARR, TIM_CCR, FakeRenode

ROOT = Path(__file__).resolve().parents[2]

BINDINGS = [
    {"signal": "firmware.pwm_duty", "direction": "output", "property": "gpio_duty",
     "object": "sysbus.gpioPortA", "pin": 8},
    {"signal": "firmware.ccr_duty", "direction": "output", "property": "register_ratio",
     "address": hex(TIM_CCR), "denominator_address": hex(TIM_ARR), "denominator_offset": 1},
    {"signal": "firmware.measured_velocity", "direction": "input", "property": "adc",
     "object": "sysbus.adc1", "channel": 0, "scale": 100.0},
]


@pytest.fixture
def fake():
    server = FakeRenode()
    yield server
    server.close()


def test_client_protocol_roundtrip(fake):
    client = RenodeExternalControl.connect("127.0.0.1", fake.port)
    try:
        assert client.get_time_us() == 0
        client.adc_set("stm32", "sysbus.adc1", 0, 123)
        assert client.adc_get("stm32", "sysbus.adc1", 0) == 123
        assert client.adc_channel_count("stm32", "sysbus.adc1") == 4
        client.bus_write("stm32", 0x20000000, 0xDEADBEEF)
        assert client.bus_read("stm32", 0x20000000) == 0xDEADBEEF
        client.run_for(250)
        assert client.get_time_us() == 250
        with pytest.raises(RenodeApiError, match="Machine not found"):
            client.machine("missing")
    finally:
        client.close()


def test_adapter_measures_pwm_duty_from_gpio_edges(fake):
    adapter = RenodeAdapter(port=fake.port, machine="stm32", inline_bindings=BINDINGS)
    adapter.start({"firmware.measured_velocity": 0.0})
    try:
        # ADC = 0 -> error 800 counts -> duty clamps at 1.0
        result = adapter.step(0.001, 0.001, {"firmware.measured_velocity": 0.0})
        assert result.outputs["firmware.pwm_duty"] == pytest.approx(1.0)
        # 6 rad/s * 100 counts -> 600 counts -> error 200 -> duty 0.4
        result = adapter.step(0.002, 0.001, {"firmware.measured_velocity": 6.0})
        assert fake.adc[0] == 600
        assert result.outputs["firmware.pwm_duty"] == pytest.approx(0.4, abs=0.011)
        assert result.outputs["firmware.ccr_duty"] == pytest.approx(0.4)
        assert result.diagnostics["renode_time_us"] == 2000
    finally:
        adapter.stop()


def test_adapter_uses_absolute_integer_time(fake):
    adapter = RenodeAdapter(port=fake.port, machine="stm32", inline_bindings=BINDINGS)
    adapter.start({})
    try:
        t = 0.0
        for _ in range(10):  # 0.0001 is not exactly representable; sum drifts in float
            t += 0.0001
            adapter.step(t, 0.0001, {})
        assert fake.time_us == 1000
        assert set(fake.run_for_calls) == {100}
    finally:
        adapter.stop()


def test_binding_validation_reports_all_problems():
    with pytest.raises(ValueError) as info:
        load_renode_bindings(None, None, [
            {"signal": "a", "direction": "output", "property": "adc", "object": "x", "channel": 0},
            {"signal": "b", "direction": "input", "property": "adc", "object": "x"},
        ])
    text = str(info.value)
    assert "unsupported output property 'adc'" in text
    assert "no Renode machine name" in text


def test_binding_manifest_file(tmp_path):
    path = tmp_path / "renode.yaml"
    path.write_text("""
adapter: renode
machine: stm32
bindings:
  - signal: firmware.pwm_duty
    endpoint: {object: sysbus.gpioPortA, property: gpio_duty, pin: 8, direction: output}
  - signal: mechanical.other
    endpoint: {adapter: webots, object: motor, property: torque, direction: input}
""")
    bindings = load_renode_bindings(path, None)
    assert [b.signal for b in bindings] == ["firmware.pwm_duty"]
    assert bindings[0].machine == "stm32"


def test_launch_command_includes_script_and_server(tmp_path):
    script = tmp_path / "board.resc"
    script.write_text("")
    adapter = RenodeAdapter(port=4321, launch=True, script=str(script), executable="renode")
    command = adapter.launch_command()
    assert command[:4] == ["renode", "--disable-gui", "--console", "--plain"]
    assert command[-1] == f'include @{script.resolve()}; emulation CreateExternalControlServer "embeddyn" 4321'
    adapter.firmware = str(tmp_path / "fw.elf")
    assert adapter.launch_command()[-1].startswith(f"$bin=@{(tmp_path / 'fw.elf').resolve()}; include @")
    adapter.firmware = str(tmp_path / "bad;name.elf")
    with pytest.raises(ValueError, match="must not contain"):
        adapter.launch_command()


def test_closed_loop_cosimulation_with_renode_firmware(fake, tmp_path):
    project = MechatronicProject.load(ROOT / "examples/mechatronics/dc-motor-renode.yaml")
    project.duration_seconds = 0.05
    fake.pwm_pin = 0  # example binds TIM1 channel 1 output line (sysbus.timer1#0)
    project.simulators[Domain.FIRMWARE].options["port"] = fake.port
    project.simulators[Domain.FIRMWARE].options["launch"] = False
    adapters = build_adapters(project)
    assert isinstance(adapters[Domain.FIRMWARE], RenodeAdapter)
    rows = CoSimulationOrchestrator(project, adapters).run(tmp_path / "run.csv")
    assert fake.time_us == 50_000
    duties = [row["firmware.pwm_duty"] for row in rows]
    assert duties[1] == pytest.approx(1.0)
    assert rows[-1]["mechanical.velocity"] > 0.5
    assert 0.0 <= min(duties) and max(duties) <= 1.0


def test_sysbus_float32_roundtrip(fake):
    adapter = RenodeAdapter(port=fake.port, machine="stm32", inline_bindings=[
        {"signal": "cal.target", "direction": "input", "property": "sysbus", "address": 0x20000004, "float32": True},
        {"signal": "cal.readback", "direction": "output", "property": "sysbus", "address": 0x20000004, "float32": True},
    ])
    adapter.start({"cal.target": 812.5})
    try:
        assert fake.memory[0x20000004] == 0x444B2000  # 812.5f
        assert adapter.step(0.001, 0.001, {"cal.target": 812.5}).outputs["cal.readback"] == 812.5
    finally:
        adapter.stop()
