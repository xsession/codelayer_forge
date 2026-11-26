#!/usr/bin/env python3
"""Render the CodeLayer Forge / embeddyn overview video (theory of operation + tutorial).

  python3 docs/video/make_overview_video.py [out_dir]

Slides are drawn with Pillow at 1920x1080 (diagrams from the architecture docs, the real figures and Lab
screenshots from engines/embeddyn/docs/images, terminal panes with real command output where given),
narrated with espeak-ng, and assembled with ffmpeg (H.264 + AAC, soft English subtitles).
Needs: Pillow, espeak-ng, ffmpeg. Run from the repository root.
"""
import json
import os
import subprocess
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
IMG = os.path.join(ROOT, "engines/embeddyn/docs/images")
W, H = 1920, 1080
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
VOICE = os.environ.get("VIDEO_VOICE", "en-us+m3")
WPM = int(os.environ.get("VIDEO_WPM", "155"))

BG = (247, 248, 250)
INK = (28, 33, 41)
MUTED = (96, 105, 120)
ACCENT = (37, 99, 235)
ACCENT2 = (13, 148, 136)
WARM = (217, 119, 6)
BOX = (255, 255, 255)
LINE = (190, 198, 210)
TERM_BG = (24, 27, 33)
TERM_INK = (220, 226, 235)


def font(size, bold=False, mono=False):
    return ImageFont.truetype(MONO if mono else BOLD if bold else FONT, size)


def base(section, title, n, total):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 8], fill=ACCENT if section.startswith("Part 1") else ACCENT2 if section.startswith("Part 2") else WARM)
    d.text((80, 50), section.upper(), font=font(24, True), fill=MUTED)
    d.text((80, 88), title, font=font(52, True), fill=INK)
    d.text((W - 80, H - 50), "%d / %d" % (n, total), font=font(22), fill=MUTED, anchor="rs")
    d.text((80, H - 50), "CodeLayer Forge · embeddyn", font=font(22), fill=MUTED, anchor="ls")
    return im, d


def wrap(d, text, xy, width_px, size, fill=INK, bold=False, spacing=10, mono=False):
    f = font(size, bold, mono)
    x, y = xy
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            t = (line + " " + word).strip()
            if d.textlength(t, font=f) > width_px and line:
                d.text((x, y), line, font=f, fill=fill)
                y += size + spacing
                line = word
            else:
                line = t
        d.text((x, y), line, font=f, fill=fill)
        y += size + spacing
    return y


def bullets(d, items, x=110, y=210, width=1700, size=36, gap=26):
    for it in items:
        sub = it.startswith("  ")
        it = it.strip()
        bx = x + (50 if sub else 0)
        d.ellipse([bx, y + size // 2 - 6, bx + 12, y + size // 2 + 6], fill=MUTED if sub else ACCENT)
        y = wrap(d, it, (bx + 32, y), width - (bx - x) - 32, size - (6 if sub else 0), fill=MUTED if sub else INK) + gap
    return y


def box(d, x, y, w, h, label, sub=None, fill=BOX, outline=ACCENT, size=30):
    d.rounded_rectangle([x, y, x + w, y + h], radius=14, fill=fill, outline=outline, width=3)
    if sub:
        d.text((x + w / 2, y + h / 2 - 18), label, font=font(size, True), fill=INK, anchor="mm")
        d.text((x + w / 2, y + h / 2 + 20), sub, font=font(size - 8), fill=MUTED, anchor="mm")
    else:
        d.text((x + w / 2, y + h / 2), label, font=font(size, True), fill=INK, anchor="mm")


def arrow(d, a, b, label=None, color=MUTED, width=4, label_side=1):
    d.line([a, b], fill=color, width=width)
    import math
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    L = 20
    p1 = (b[0] - L * math.cos(ang - 0.4), b[1] - L * math.sin(ang - 0.4))
    p2 = (b[0] - L * math.cos(ang + 0.4), b[1] - L * math.sin(ang + 0.4))
    d.polygon([b, p1, p2], fill=color)
    if label:
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        d.text((mx + 16 * label_side, my), label, font=font(24), fill=MUTED, anchor="lm" if label_side > 0 else "rm")


def picture(im, path, box_xyxy):
    p = Image.open(path).convert("RGB")
    x0, y0, x1, y1 = box_xyxy
    s = min((x1 - x0) / p.width, (y1 - y0) / p.height)
    p = p.resize((int(p.width * s), int(p.height * s)), Image.LANCZOS)
    ox = x0 + ((x1 - x0) - p.width) // 2
    oy = y0 + ((y1 - y0) - p.height) // 2
    ImageDraw.Draw(im).rectangle([ox - 2, oy - 2, ox + p.width + 1, oy + p.height + 1], outline=LINE, width=2)
    im.paste(p, (ox, oy))


def terminal(im, lines, xyxy, size=26):
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = xyxy
    d.rounded_rectangle(xyxy, radius=14, fill=TERM_BG)
    for i, c in enumerate([(239, 68, 68), (234, 179, 8), (34, 197, 94)]):
        d.ellipse([x0 + 24 + 30 * i, y0 + 18, x0 + 40 + 30 * i, y0 + 34], fill=c)
    y = y0 + 56
    f = font(size, mono=True)
    for l in lines:
        col = (125, 211, 252) if l.startswith("$") else (134, 239, 172) if l.startswith("#") else TERM_INK
        d.text((x0 + 28, y), l, font=f, fill=col)
        y += size + 10
        if y > y1 - size:
            break


# ------------------------------------------------------------------ slides

def s_title(im, d):
    d.rectangle([0, 0, W, H], fill=(17, 24, 39))
    d.text((W / 2, 380), "CodeLayer Forge", font=font(96, True), fill=(255, 255, 255), anchor="mm")
    d.text((W / 2, 490), "and the embeddyn co-simulation engine", font=font(48), fill=(191, 219, 254), anchor="mm")
    d.text((W / 2, 640), "Theory of operation  ·  Tutorial", font=font(40, True), fill=(94, 234, 212), anchor="mm")
    d.text((W / 2, 900), "firmware · electronics · mechanics — one deterministic simulation", font=font(30),
           fill=(156, 163, 175), anchor="mm")


def s_agenda(im, d):
    box(d, 110, 220, 820, 700, "", fill=BOX, outline=ACCENT)
    d.text((150, 250), "Part 1 · Theory of operation", font=font(38, True), fill=ACCENT)
    bullets(d, ["Forge: shell, registry, plugin hosts", "Plugin lifecycle and capabilities",
                "The embeddyn engine and its layers", "One co-simulation step", "Simulators and their adapters",
                "Analysis: tuning, tolerance, estimation"], x=150, y=330, width=740, size=32, gap=18)
    box(d, 990, 220, 820, 700, "", fill=BOX, outline=ACCENT2)
    d.text((1030, 250), "Part 2 · Tutorial", font=font(38, True), fill=ACCENT2)
    bullets(d, ["Set up and check the environment", "A first simulation: DC motor loop",
                "Swap in ngspice and MuJoCo", "Real firmware in the loop", "Tune gains, check tolerances",
                "The Lab GUI and the Forge plugin"], x=1030, y=330, width=740, size=32, gap=18)


def s_forge(im, d):
    bullets(d, ["A cross-platform engineering workbench that integrates domain tools as isolated plugins",
                "Tauri desktop shell with a dependency-free web front end",
                "Rust plugin registry and CLI (forge-core, forge-protocol, forge-cli)",
                "Python plugin host and SDK, one process per plugin",
                "First-party plugins:",
                "  Pin Configurator · Route Core · OpenHDL Designer",
                "  embeddyn Co-simulation · PyOnTrust adapter",
                "Domain engines live in engines/ — embeddyn is the largest"], size=36)


def s_process(im, d):
    box(d, 660, 200, 600, 110, "Desktop WebView", "browser-native modules")
    arrow(d, (960, 310), (960, 380), "Tauri invoke")
    box(d, 560, 380, 800, 110, "Rust desktop host + registry", "discovery · dispatch · permissions · supervision")
    arrow(d, (960, 490), (960, 570), "newline-delimited JSON-RPC 2.0")
    box(d, 660, 570, 600, 110, "Python plugin host", "one dedicated process per plugin")
    arrow(d, (960, 680), (960, 750), "registered commands / services")
    box(d, 710, 750, 500, 100, "Plugin instance")
    wrap(d, "stdout carries only protocol messages\nstderr carries structured logs\nunregistered calls are refused",
         (1400, 600), 460, 28, fill=MUTED)


def s_lifecycle(im, d):
    steps = [("Discovery", "plugin.toml in bounded roots"), ("Validation", "ids, versions, API range"),
             ("Activation", "host imports entrypoint"), ("Registration", "commands, versioned services"),
             ("Invocation", "JSON-RPC from desktop / CLI"), ("Deactivation", "deactivate(), process ends"),
             ("Recovery", "restart without the shell")]
    x = 70
    for i, (a, b) in enumerate(steps):
        box(d, x, 380, 230, 150, a, size=28)
        yy = 555
        for part in textwrap.wrap(b, 18):
            d.text((x + 115, yy), part, font=font(21), fill=MUTED, anchor="ma")
            yy += 28
        if i < len(steps) - 1:
            arrow(d, (x + 230, 455), (x + 262, 455))
        x += 262
    wrap(d, "Every plugin declares its identity, compatibility, contributions, services and permissions in "
            "plugin.toml. The SDK hands it a restricted context, never the UI or Tauri internals.",
         (110, 700), 1700, 32, fill=INK)


def s_capabilities(im, d):
    bullets(d, ["Plugins depend on versioned capabilities, not on each other's packages",
                "  e.g. codelayer.routing.orthogonal → provided by Route Core",
                "The capability broker keeps plugin hosts alive and routes forge/callCapability",
                "Packages (.cforge-plugin) carry a signed-ready file index with SHA-256 hashes",
                "Installation rejects path traversal, duplicates, oversized archives and hash mismatches,",
                "  then swaps the verified plugin in atomically",
                "Workspace documents carry explicit schema versions"], size=34)


def s_engines(im, d):
    box(d, 80, 230, 430, 100, "Pin Configurator", "pin plan")
    box(d, 80, 420, 430, 100, "OpenHDL Designer", "planned: Verilator")
    box(d, 80, 610, 430, 100, "Desktop shell")
    box(d, 640, 230, 560, 100, "…simulation.renode-bindings", size=26)
    box(d, 640, 610, 560, 100, "…simulation.cosim / .analysis", size=26)
    arrow(d, (510, 280), (640, 280))
    arrow(d, (510, 470), (640, 300), color=LINE)
    arrow(d, (510, 660), (640, 660))
    box(d, 1330, 380, 500, 160, "embeddyn engine", "engines/embeddyn", outline=ACCENT2, size=36)
    arrow(d, (1200, 280), (1330, 430))
    arrow(d, (1200, 660), (1330, 500))
    wrap(d, "drives Renode · ngspice · MuJoCo · FMUs · Webots · Python plants", (1330, 250), 500, 26, fill=MUTED)
    box(d, 1330, 760, 500, 90, "embeddyn Lab · 127.0.0.1", size=28)
    arrow(d, (1580, 540), (1580, 760), "opens", label_side=1)
    wrap(d, "The plugin is a thin adapter: callers only see capabilities, so the engine can move to its own "
            "process or a worker without changing them.", (80, 790), 1150, 28, fill=MUTED)


def s_layers(im, d):
    rows = [("Authoring", "project.yaml · Lab schematic · KiCad · MJCF · netlists · ELF"),
            ("Engineering model", "signals · couplings · instances · parameters · metrics"),
            ("Execution", "orchestrator · scheduler · adapter manager · checkpoints"),
            ("Adapters", "renode · ngspice-shared · mujoco · python · fmu · webots · replay · mock"),
            ("Simulators", "Renode (TCP) · libngspice (in-process) · MuJoCo · FMU binaries · Webots")]
    y = 200
    for i, (a, b) in enumerate(rows):
        box(d, 110, y, 1100, 120, a, b, outline=ACCENT if i < 3 else ACCENT2, size=32)
        if i < len(rows) - 1:
            arrow(d, (660, y + 120), (660, y + 150))
        y += 150
    box(d, 1330, 500, 480, 110, "Run outputs", "rows · CSV · telemetry · manifest", outline=WARM, size=30)
    box(d, 1330, 700, 480, 110, "Analysis", "tuning · tolerance · estimation · verification", outline=WARM, size=30)
    arrow(d, (1210, 560), (1330, 555))
    arrow(d, (1570, 610), (1570, 700))


def s_principles(im, d):
    cards = [("Signal-oriented", "Projects speak of motor.current and arm.angle; adapters translate at the edge, "
                                 "so one simulator can replace another without touching the project."),
             ("Deterministic", "Time is an integer step index, instances run in a fixed order, Renode's clock only "
                               "moves on RunFor, sampling is seeded: same inputs, same rows, bit for bit."),
             ("Real firmware", "The ELF you would flash runs unmodified; the adapter touches only what hardware "
                               "would: pins, peripheral registers, chosen RAM."),
             ("Runs are experiments", "Tuning, tolerance, estimation and verification are outer loops over the "
                                      "same run.")]
    for i, (a, b) in enumerate(cards):
        x = 110 + (i % 2) * 870
        y = 220 + (i // 2) * 380
        box(d, x, y, 830, 330, "", outline=ACCENT)
        d.text((x + 40, y + 40), a, font=font(36, True), fill=ACCENT)
        wrap(d, b, (x + 40, y + 110), 750, 29)


def s_step(im, d):
    lanes = ["Orchestrator", "Renode · firmware", "ngspice · electrical", "MuJoCo · mechanical"]
    xs = [260, 760, 1210, 1640]
    for x, l in zip(xs, lanes):
        box(d, x - 190, 190, 380, 80, l, size=28)
        d.line([(x, 270), (x, 960)], fill=LINE, width=3)
    msgs = [(0, 0, "couplings into firmware (feedback from k−1)"), (0, 1, "ADC / GPIO / RAM inputs, RunFor(h)"),
            (1, 0, "PWM duty, pins, telemetry, bus traffic"), (0, 2, "set sources, resume transient to t_k"),
            (2, 0, "mean currents, voltages over the step"), (0, 3, "ctrl / qfrc inputs, n × mj_step"),
            (3, 0, "qpos, qvel, sensors"), (0, 0, "commit row, telemetry, checkpoint if due")]
    y = 320
    for a, b, t in msgs:
        if a == b:
            d.rounded_rectangle([xs[a] - 170, y - 20, xs[a] + 170, y + 30], radius=8, fill=(239, 246, 255))
            d.text((xs[a] + 190, y + 5), t, font=font(24), fill=INK, anchor="lm")
        else:
            arrow(d, (xs[a], y), (xs[b], y), color=ACCENT if a == 0 else ACCENT2)
            d.text(((xs[a] + xs[b]) / 2, y - 14), t, font=font(23), fill=INK, anchor="mb")
        y += 82


def s_delay(im, d):
    picture(im, os.path.join(IMG, "theory-delay.png"), (100, 190, 1150, 980))
    wrap(d, "The forward path (duty → current → torque) follows the execution order and needs no delay.\n\n"
            "Feedback (velocity → back-EMF, velocity → firmware) runs against the order, so it carries "
            "delay_steps: 1 and reads the value committed at the end of step k−1.\n\n"
            "That one-step delay is what makes the step explicit, deterministic and checkpointable.",
         (1200, 230), 640, 30)


def s_schedule(im, d):
    picture(im, os.path.join(IMG, "theory-schedule.png"), (100, 190, 1820, 900))
    wrap(d, "Instances may run at different rates; the scheduler fires them on the master time grid in a fixed order.",
         (110, 930), 1700, 28, fill=MUTED)


def s_simulators(im, d):
    rows = [("Firmware", "Renode", "process over TCP; virtual time moves only on RunFor; MCU peripheral models"),
            ("Electrical", "ngspice", "shared library in-process; transient resumed step by step"),
            ("Mechanical", "MuJoCo / Webots", "multibody physics, n inner steps per macro step"),
            ("Any domain", "FMI 2.0 / 3.0", "import FMUs; export Python plants as FMI 3.0 with state save"),
            ("Any domain", "Python plants", "ODE models, replayed bench data, mocks for quick runs"),
            ("Design data", "KiCad · openEMS", "netlist / schematic export, RF patch and EMC analysis")]
    y = 210
    d.text((110, y), "Domain", font=font(28, True), fill=MUTED)
    d.text((420, y), "Tool", font=font(28, True), fill=MUTED)
    d.text((800, y), "How embeddyn drives it", font=font(28, True), fill=MUTED)
    y += 60
    for a, b, c in rows:
        d.line([(110, y - 12), (1810, y - 12)], fill=LINE, width=2)
        d.text((110, y), a, font=font(30), fill=INK)
        d.text((420, y), b, font=font(30, True), fill=ACCENT)
        wrap(d, c, (800, y), 1010, 28)
        y += 115


def s_firmware(im, d):
    bullets(d, ["The firmware ELF runs unmodified on Renode's CPU and peripheral models",
                "Bindings map co-simulation signals to the MCU:",
                "  PWM capture from timers, ADC channel voltages, GPIO levels",
                "  SPI and I²C device models (encoders, IMUs, temperature sensors)",
                "  RAM addresses for telemetry or calibration values",
                "UART / CAN traffic can be observed and faults injected; the firmware sees them",
                "MCU support grows platform by platform: Cortex-M, MSPM0, C2000 and Concerto, dsPIC30/33F/33E",
                "  each checked against vendor examples and reference simulators"], size=33)


def s_analysis(im, d):
    cards = [("Metrics", "step response, stats, integrals, energy — computed from every run"),
             ("Tuning", "Nelder–Mead or CMA-ES over parameters, with objectives, constraints and parallel workers"),
             ("Tolerance", "Monte Carlo yield and Sobol sensitivity indices over component spreads"),
             ("Estimation", "fit model parameters to bench recordings, with confidence intervals"),
             ("Verification", "energy balance, step-size convergence, golden waveforms, scenarios")]
    y = 210
    for a, b in cards:
        box(d, 110, y, 360, 120, a, outline=WARM, size=32)
        wrap(d, b, (510, y + 38), 1300, 30)
        y += 150


def s_setup(im, d):
    doctor = open(os.path.join(OUT, "doctor.txt")).read().splitlines() if os.path.exists(os.path.join(OUT, "doctor.txt")) else []
    # the repository path is the viewer's own: show it as <repo>
    doctor = ["Repository: <repo>" if l.startswith("Repository:") else l for l in doctor]
    lines = ["$ python3 scripts/doctor.py"] + [l for l in doctor if l.strip()][:11] + \
            ["", "$ cd engines/embeddyn", '$ pip install -e ".[test]"']
    terminal(im, lines, (110, 200, 1810, 960), size=27)


def s_yaml(im, d):
    lines = ["# examples/mechatronics/dc-motor.yaml", "name: dc-motor-speed-control",
             "step_seconds: 0.0005        # 2 kHz macro step", "duration_seconds: 0.25", "simulators:",
             "  firmware:   {options: {backend: mock}}", "  electrical: {model: motor.cir, options: {backend: mock}}",
             "  mechanical: {options: {backend: mock, headless: true}}", "parameters:",
             "  motor.k: {value: 0.08, unit: N*m/A}", "couplings:",
             "  - {source: firmware.pwm_duty, target: electrical.pwm_duty}",
             "  - {source: electrical.motor_current, target: mechanical.motor_torque, gain: \"@motor.k\"}",
             "  - {source: mechanical.velocity, target: electrical.back_emf, gain: \"@motor.k\", delay_steps: 1}",
             "  - {source: mechanical.velocity, target: firmware.measured_velocity, delay_steps: 1}",
             "metrics:", "  speed: {type: step_response, signal: mechanical.velocity, target: firmware.target_velocity}"]
    terminal(im, lines, (110, 200, 1810, 990), size=25)


def s_run(im, d):
    run = json.load(open(os.path.join(OUT, "run.json"))) if os.path.exists(os.path.join(OUT, "run.json")) else {}
    f, m = run.get("final", {}), run.get("metrics", {})
    lines = ["$ embeddyn mechatronics run examples/mechatronics/dc-motor.yaml --mock -o dc-motor.csv",
             '  "steps": %s,' % run.get("steps", 501), '  "final": {',
             '    "firmware.pwm_duty": %.3f,' % f.get("firmware.pwm_duty", 0),
             '    "electrical.motor_current": %.2f,' % f.get("electrical.motor_current", 0),
             '    "mechanical.velocity": %.3f,' % f.get("mechanical.velocity", 0), "    ...", "  },",
             '  "metrics": {', '    "speed.final_value": %.3f,' % m.get("speed.final_value", 0),
             '    "speed.steady_state_error": %.3f,' % m.get("speed.steady_state_error", 0),
             '    "speed.iae": %.3f,' % m.get("speed.iae", 0), "    ...", "  }",
             "# also written: telemetry, manifest, CSV export, run database"]
    terminal(im, lines, (110, 200, 1810, 960), size=28)


def image_slide(name, caption):
    def f(im, d):
        picture(im, os.path.join(IMG, name), (110, 190, 1810, 900))
        wrap(d, caption, (110, 930), 1700, 28, fill=MUTED)
    return f


def s_ngspice(im, d):
    terminal(im, ["# one word changes the electrical domain", "electrical:",
                  "  model: hbridge.cir",
                  "  options: {backend: ngspice-shared, max_step: 1.0e-6}",
                  "", "$ embeddyn mechatronics run examples/mechatronics/dc-motor-ngspice.yaml -o hbridge.csv"],
             (110, 200, 1810, 520), size=27)
    picture(im, os.path.join(IMG, "tutorial-ngspice.png"), (110, 550, 1810, 990))


def s_firmware_tut(im, d):
    terminal(im, ["$ embeddyn mechatronics run examples/mechatronics/rc-servo-l476.yaml -o servo.csv",
                  "# Renode runs the servo firmware; bindings capture its PWM and feed its ADC"],
             (110, 200, 1810, 330), size=27)
    picture(im, os.path.join(IMG, "tutorial-rc-servo.png"), (110, 360, 1810, 980))


def s_tuning(im, d):
    terminal(im, ["$ embeddyn mechatronics tune examples/mechatronics/tuning/servo-pi.yaml \\",
                  "      --method nelder-mead --workers 4 --max-evaluations 60 -o nm.json",
                  "$ embeddyn mechatronics tune ... --method cmaes --workers 4 -o cma.json"],
             (110, 200, 1810, 380), size=27)
    picture(im, os.path.join(IMG, "tutorial-tuning-convergence.png"), (110, 410, 950, 980))
    picture(im, os.path.join(IMG, "tutorial-tuning-response.png"), (980, 410, 1810, 980))


def s_tolerance(im, d):
    terminal(im, ["$ embeddyn mechatronics tolerance examples/mechatronics/tolerance/servo.yaml --workers 4 -o tol.json"],
             (110, 200, 1810, 290), size=27)
    picture(im, os.path.join(IMG, "tutorial-tolerance.png"), (110, 320, 1810, 980))


def s_lab(im, d):
    terminal(im, ["$ embeddyn mechatronics gui examples/mechatronics/rc-servo-lab.yaml --open"],
             (110, 200, 1810, 290), size=27)
    picture(im, os.path.join(IMG, "lab-schematic.png"), (110, 320, 950, 980))
    picture(im, os.path.join(IMG, "lab-instruments.png"), (980, 320, 1810, 980))


def s_lab3d(im, d):
    picture(im, os.path.join(IMG, "lab-3d-arm.png"), (110, 190, 950, 980))
    picture(im, os.path.join(IMG, "lab-metrics.png"), (980, 190, 1810, 980))


def s_forge_tut(im, d):
    terminal(im, ["$ python3 scripts/build_catalog.py", "$ python3 scripts/demo.py",
                  "$ python3 -m http.server 4173 --directory apps/desktop/web   # open localhost:4173",
                  "", "$ python3 hosts/plugin-broker/forge_broker.py --plugins-root plugins \\",
                  "      --workspace examples/demo-workspace",
                  "# forge/callCapability → codelayer.simulation.cosim.run, .analysis.tune, ...",
                  "", "# commands of the embeddyn plugin:",
                  "#   embeddyn.runProject  embeddyn.validateProject  embeddyn.openLab",
                  "#   embeddyn.bindingsFromPinPlan  embeddyn.exportFmu  embeddyn.checkFmu"],
             (110, 200, 1810, 900), size=28)


def s_next(im, d):
    bullets(d, ["engines/embeddyn/docs: getting started, 11 tutorials, theory of operation, reference",
                "docs/architecture: Forge process model, plugin lifecycle, security model",
                "plugins/embeddyn-cosim/README.md: capabilities and the pin-plan → Renode bindings path",
                "Start small: run the DC motor with --mock, then switch one domain at a time to its real simulator"],
            size=34)


SLIDES = [
    ("", "", s_title,
     "This video explains how CodeLayer Forge and its simulation engine, embeddyn, work. The first part covers the "
     "theory of operation. The second part is a tutorial, from a first simulation to real firmware in the loop, "
     "tuning, tolerance analysis and the Lab."),
    ("Overview", "What this video covers", s_agenda,
     "Part one looks inside: the Forge shell, its plugin hosts and capabilities, then the embeddyn engine, what "
     "happens in one co-simulation step, and the simulators it drives. Part two puts it to work."),
    ("Part 1 · Theory of operation", "CodeLayer Forge", s_forge,
     "Forge is an engineering workbench. It integrates domain tools as isolated plugins, without tying them to one "
     "language or release cycle. A Tauri desktop shell hosts the user interface. A Rust registry discovers plugins and "
     "dispatches commands. Each Python plugin runs in its own host process. Large engines, such as embeddyn, live "
     "separately under the engines folder."),
    ("Part 1 · Theory of operation", "Process model", s_process,
     "Here is the process model. The web view calls the Rust host through Tauri. The host speaks newline delimited "
     "JSON RPC to a dedicated Python plugin host, which runs exactly one plugin. Standard output carries only protocol "
     "messages, standard error carries logs, and a plugin can only be called through commands it registered."),
    ("Part 1 · Theory of operation", "Plugin lifecycle", s_lifecycle,
     "A plugin goes through seven stages. The registry discovers its plugin dot toml, validates identities and version "
     "ranges, and the host activates it. The plugin registers commands and versioned services, receives invocations, "
     "and is deactivated with its process. If a plugin crashes, it can be restarted without losing the shell."),
    ("Part 1 · Theory of operation", "Capabilities, broker and packaging", s_capabilities,
     "Plugins never import each other. They call versioned capabilities, such as orthogonal routing, through the "
     "broker, which keeps hosts alive and routes each call to its provider. Plugin packages carry a hashed file index. "
     "Installation rejects unsafe or tampered archives, and swaps the verified plugin in atomically."),
    ("Part 1 · Theory of operation", "Engines behind capabilities", s_engines,
     "The embeddyn plugin is a thin adapter over the engine. It offers co-simulation, analysis, F M I, and Renode "
     "binding capabilities. Pin Configurator turns a pin plan into Renode bindings, the desktop runs and tunes "
     "projects, and the engine opens its Lab on the local machine. Because callers only see capabilities, the engine "
     "can later move to a worker without changing them."),
    ("Part 1 · Theory of operation", "embeddyn: the layers", s_layers,
     "Inside embeddyn, authoring formats such as project YAML, the Lab schematic, KiCad, M J C F and firmware ELF files "
     "become one engineering model of signals, couplings, instances, parameters and metrics. The execution layer "
     "schedules the instances and checkpoints the run. Adapters translate to each simulator. Every run produces rows, "
     "telemetry and a manifest, which the analysis tools consume."),
    ("Part 1 · Theory of operation", "Design principles", s_principles,
     "Four principles shape the engine. It is signal oriented, so simulators can be swapped at the edge. It is "
     "deterministic: time is an integer step, order is fixed, and Renode's clock only moves when told to. It runs real, "
     "unmodified firmware. And every run is an experiment that outer loops can score and optimise."),
    ("Part 1 · Theory of operation", "One macro step", s_step,
     "One macro step looks like this. The orchestrator applies couplings into the firmware domain, writes its inputs, "
     "and lets Renode run for one step. Renode returns the P W M duty, pin levels and bus traffic. Next the electrical "
     "domain: ngspice resumes its transient to the end of the step. Then the mechanical domain advances its physics. "
     "Finally the orchestrator commits the row, records telemetry, and checkpoints when due."),
    ("Part 1 · Theory of operation", "Why feedback needs a delay", s_delay,
     "Couplings that follow the execution order need no delay. Feedback runs against that order, so it carries a one "
     "step delay and reads the value committed in the previous step. This keeps each step explicit and deterministic, "
     "and it is what makes checkpoints and resume exact."),
    ("Part 1 · Theory of operation", "Scheduling instances", s_schedule,
     "Instances can run at different rates. The scheduler fires each one on the master time grid, always in the same "
     "order, so a project with fast electrical and slow mechanical parts stays reproducible."),
    ("Part 1 · Theory of operation", "Simulators and adapters", s_simulators,
     "These are the dependencies the engine drives. Renode runs firmware as a separate process over T C P. ngspice is "
     "loaded as a shared library and resumed step by step. MuJoCo or Webots provide mechanics. F M I units can be "
     "imported, and Python plants exported as F M I 3 units. KiCad and open E M S feed design data and R F analysis."),
    ("Part 1 · Theory of operation", "Firmware emulation", s_firmware,
     "Firmware runs unmodified on Renode's processor and peripheral models. Bindings connect signals to timers, A D C "
     "channels, G P I O pins, S P I and I squared C device models, and RAM. Serial and CAN traffic can be observed, "
     "and faults injected that the firmware really sees. Microcontroller support is added platform by platform, and "
     "each one is checked against vendor examples and reference simulators."),
    ("Part 1 · Theory of operation", "Analysis loops", s_analysis,
     "Every analysis is an outer loop over runs. Metrics score each run. Tuning searches parameters with Nelder Mead or "
     "C M A E S, in parallel. Tolerance analysis estimates yield by Monte Carlo and ranks causes with Sobol indices. "
     "Estimation fits parameters to bench data, and verification checks energy balance, convergence and golden "
     "waveforms."),
    ("Part 2 · Tutorial", "Set up", s_setup,
     "Now the tutorial. From the repository root, the doctor script checks Python, Node, Rust, Git and Docker. Then "
     "install the engine in editable mode from the engines embeddyn folder. Renode, ngspice and MuJoCo are only needed "
     "by projects that use them."),
    ("Part 2 · Tutorial", "A first project: DC motor speed loop", s_yaml,
     "The first project is a DC motor speed loop. It sets a half millisecond step, picks a simulator per domain, here "
     "the built in mocks, and declares the motor constant once. Couplings carry the P W M duty to the bridge, current to "
     "torque, and velocity back to the back E M F and the controller, each feedback with a one step delay. A step "
     "response metric scores the speed."),
    ("Part 2 · Tutorial", "Run it", s_run,
     "Run it with the mock backends. Five hundred and one steps take about a second. The output shows the final values "
     "of every signal and the metrics: after a quarter of a second the speed is still below the eight radian per second "
     "target, which the steady state error reports. Telemetry, a manifest and a CSV file are written for later analysis."),
    ("Part 2 · Tutorial", "Read the result", image_slide("tutorial-dc-motor.png",
                                                          "Duty saturates at once, current jumps toward 12 A, speed ramps toward the target."),
     "Read the plot from top to bottom. The controller saturates the duty immediately, the current jumps to about "
     "twelve amperes, limited by the inductance, and the speed ramps up toward its target."),
    ("Part 2 · Tutorial", "Swap in a switching H-bridge", s_ngspice,
     "To see switching detail, change one word: the electrical backend becomes ngspice shared, with a switching bridge "
     "netlist. Nothing else in the project changes, and the run now shows the real current ripple."),
    ("Part 2 · Tutorial", "Multibody mechanics with MuJoCo", image_slide("tutorial-mujoco-arm.png",
                                                                         "examples/mechatronics/mujoco-arm.yaml: named instances, Python plants, MuJoCo physics."),
     "The same approach brings in multibody physics. The arm example uses named instances, Python plants and a MuJoCo "
     "model, and the joint angles come back as ordinary signals."),
    ("Part 2 · Tutorial", "Real firmware in the loop", s_firmware_tut,
     "Next, real firmware. The R C servo example runs the servo controller's ELF in Renode. Bindings capture its P W M "
     "output and drive its A D C, so the firmware closes the loop around the simulated motor exactly as on hardware."),
    ("Part 2 · Tutorial", "Faults the firmware really sees", image_slide("tutorial-rc-servo-fault.png",
                                                                        "An injected fault and the firmware's reaction, from the same run."),
     "Faults can be injected into any signal or bus. Here the firmware reacts to an injected fault, which shows up in "
     "the same telemetry as everything else."),
    ("Part 2 · Tutorial", "Tune controller gains", s_tuning,
     "Tuning runs the project many times. Give it an objective, constraints and the parameters to vary, choose Nelder "
     "Mead or C M A E S, and run evaluations on four workers. The plots compare convergence and the tuned step "
     "response. The same works on real firmware."),
    ("Part 2 · Tutorial", "Tolerances and yield", s_tolerance,
     "Tolerance analysis samples component spreads, reports the yield against your limits, and uses Sobol indices to "
     "point at the parameters that matter, so you know which part to tighten."),
    ("Part 2 · Tutorial", "The Lab", s_lab,
     "The Lab is the graphical view of the same project. Start it from the command line, read the schematic, and run "
     "it with virtual instruments such as an oscilloscope and meters. Saving writes an ordinary project file that the "
     "command line runs unchanged."),
    ("Part 2 · Tutorial", "3-D view and metrics", s_lab3d,
     "The 3 D view replays the mechanics, and the metrics tab shows the same numbers the command line prints."),
    ("Part 2 · Tutorial", "Inside Forge", s_forge_tut,
     "Finally, Forge itself. Build the plugin catalog, run the demo, and open the desktop front end in a browser. The "
     "broker exposes every plugin's capabilities, so other tools can run, validate, tune and open the Lab through the "
     "embeddyn plugin's commands."),
    ("Where to go next", "Further reading", s_next,
     "To go further, read the embeddyn documentation with its eleven tutorials and the theory of operation, and the "
     "Forge architecture notes. Start small with the mock DC motor, then switch one domain at a time to its real "
     "simulator. Thanks for watching."),
]


def tts(text, wav):
    subprocess.run(["espeak-ng", "-v", VOICE, "-s", str(WPM), "-g", "4", "-w", wav, text], check=True,
                   stdout=subprocess.DEVNULL)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout
    return float(out.strip())


def srt_time(t):
    ms = int(round(t * 1000))
    return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def main():
    global OUT
    OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "video_out")
    os.makedirs(OUT, exist_ok=True)
    total = len(SLIDES)
    clips, srt, t = [], [], 0.0
    for i, (section, title, draw, narration) in enumerate(SLIDES, 1):
        im, d = base(section, title, i, total)
        draw(im, d)
        png = os.path.join(OUT, "slide_%02d.png" % i)
        im.save(png)
        wav = os.path.join(OUT, "voice_%02d.wav" % i)
        tts(narration, wav)
        dur = duration(wav) + 1.2
        clip = os.path.join(OUT, "clip_%02d.mp4" % i)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", png, "-i", wav,
                        "-af", "adelay=500|500,apad", "-t", "%.3f" % dur, "-r", "30", "-c:v", "libx264", "-tune",
                        "stillimage", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "1",
                        clip], check=True)
        clips.append(clip)
        # subtitles: the narration split into chunks of about 14 words, spread over the clip
        words = narration.split()
        chunks = [" ".join(words[j:j + 14]) for j in range(0, len(words), 14)]
        speech = dur - 1.2
        tt = t + 0.5
        for c in chunks:
            share = speech * len(c.split()) / len(words)
            srt.append((tt, tt + share, c))
            tt += share
        t += duration(clip)
        print("slide %d/%d  %.1f s" % (i, total, dur), flush=True)
    lst = os.path.join(OUT, "clips.txt")
    open(lst, "w").write("".join("file '%s'\n" % c for c in clips))
    srt_path = os.path.join(OUT, "overview.srt")
    open(srt_path, "w").write("".join("%d\n%s --> %s\n%s\n\n" % (k + 1, srt_time(a), srt_time(b), "\n".join(textwrap.wrap(c, 60)))
                                      for k, (a, b, c) in enumerate(srt)))
    joined = os.path.join(OUT, "joined.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined], check=True)
    final = os.path.join(OUT, "codelayer-forge-overview.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", joined, "-i", srt_path, "-c", "copy", "-c:s", "mov_text",
                    "-metadata:s:s:0", "language=eng", "-movflags", "+faststart", final], check=True)
    print("video:", final, "%.0f s" % duration(final))


if __name__ == "__main__":
    main()
