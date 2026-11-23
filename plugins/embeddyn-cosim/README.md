# embeddyn Co-simulation

Connects the embeddyn engine (`engines/embeddyn`) to CodeLayer Forge. The engine
co-simulates firmware in Renode, electronics in ngspice, mechanics as Python
plants or FMUs, and replayed measurements. This plugin exposes it as versioned
capabilities that other plugins can call, the same way they call Route Core.

| Capability | Methods |
|---|---|
| `codelayer.simulation.cosim` | `parts`, `open` (schematic graph), `validate`, `run` (`duration`, `mock`, `output` CSV) |
| `codelayer.simulation.analysis` | `verify`, `tune`, `tolerance` |
| `codelayer.simulation.renode-bindings` | `from_pin_plan` (Pin Configurator plan + device → Renode bindings) |

Commands: `embeddyn.runProject`, `embeddyn.validateProject`, `embeddyn.openLab` /
`embeddyn.stopLab` (the Lab GUI on 127.0.0.1, returns its URL) and
`embeddyn.bindingsFromPinPlan`.

## Engine location

The plugin imports `embeddyn` from `EMBEDDYN_ENGINE_ROOT` if set, else from
`engines/embeddyn` of this monorepo. In a standalone plugin package it falls back
to an installed `embeddyn`. The engine needs PyYAML. Renode, ngspice and Webots
are only needed by projects that use them.

## Pin plan → Renode bindings

Device files can add a `renode` block per pin, mapping a capability to the
Renode peripheral that drives it. Plan signals can add a `cosim` block with the
co-simulation signal name and binding options:

```json
{"name": "PA0", "capabilities": ["GPIO", "PWM"],
 "renode": {"PWM": {"object": "sysbus.timer2", "pin": 0}}}
{"id": "servo_pulse", "requires": ["PWM"],
 "cosim": {"signal": "mcu.servo_pulse", "property": "gpio_pulse_width", "timeout": 0.05}}
```

`examples/demo-workspace/pin-plans/rc-servo.pinplan.json` with
`devices/stm32l476-servo.json` regenerates the pin bindings of the STM32L476
RC-servo example exactly. Bus pins (UART, SPI, I2C, CAN) are reported as
diagnostics until the Renode adapter supports bus bindings.
