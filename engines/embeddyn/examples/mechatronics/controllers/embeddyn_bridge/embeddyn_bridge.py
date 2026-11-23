"""Reference Webots Supervisor bridge for Embeddyn line-delimited JSON protocol."""
from controller import Supervisor
import json, os, socket

robot = Supervisor()
step_ms = int(robot.getBasicTimeStep())
host = os.getenv("EMBEDDYN_COSIM_HOST") or os.getenv("VSD_COSIM_HOST", "127.0.0.1")
port = int(os.getenv("EMBEDDYN_COSIM_PORT") or os.getenv("VSD_COSIM_PORT", "8765"))
server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((host, port))
server.listen(1)
connection, _ = server.accept()
stream = connection.makefile("rwb")
velocity = 0.0
position = 0.0
while True:
    line = stream.readline()
    if not line:
        break
    request = json.loads(line)
    command = request.get("command")
    if command == "stop":
        response = {"ok": True}
        stream.write((json.dumps(response) + "\n").encode()); stream.flush(); break
    if command == "initialize":
        response = {"ok": True}
    elif command == "step":
        inputs = request.get("inputs", {})
        dt = float(request.get("dt", step_ms / 1000.0))
        torque = float(inputs.get("mechanical.motor_torque", 0.0))
        load = float(inputs.get("mechanical.load_torque", 0.0))
        inertia = max(float(inputs.get("mechanical.inertia", 0.02)), 1e-9)
        damping = float(inputs.get("mechanical.damping", 0.08))
        acceleration = (torque - load - damping * velocity) / inertia
        velocity += acceleration * dt
        position += velocity * dt
        robot.step(max(1, round(dt * 1000)))
        response = {"outputs": {
            "mechanical.position": position,
            "mechanical.velocity": velocity,
            "mechanical.acceleration": acceleration,
        }}
    else:
        response = {"error": "unknown command"}
    stream.write((json.dumps(response) + "\n").encode()); stream.flush()
stream.close(); connection.close(); server.close()
