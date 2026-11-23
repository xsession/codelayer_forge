from pathlib import Path

from embeddyn.mechatronics.bindings import BindingManifest
from embeddyn.mechatronics.catalog import ComponentCatalog
from embeddyn.mechatronics.integration import validate_integrations
from embeddyn.mechatronics.kicad import KiCadBridge
from embeddyn.mechatronics.model import MechatronicProject

ROOT = Path(__file__).resolve().parents[2]


def test_component_catalog_contains_motor_and_encoder():
    records = ComponentCatalog([ROOT / "components" / "mechatronics"]).scan()
    ids = {item.component_id for item in records}
    assert "codelayer.motion.dc-motor" in ids
    assert "codelayer.sensors.quadrature-encoder" in ids


def test_spice_inspection():
    report = KiCadBridge().validate_spice_netlist(ROOT / "examples" / "mechatronics" / "motor.cir")
    assert report["valid"]
    assert report["device_count"] >= 1


def test_integration_validation_on_dc_motor():
    project = MechatronicProject.load(ROOT / "examples" / "mechatronics" / "dc-motor.yaml")
    report = validate_integrations(project)
    assert "checks" in report
    assert any(item["name"] == "electrical" for item in report["checks"])


def test_binding_manifest_validation(tmp_path):
    project = MechatronicProject.load(ROOT / "examples" / "mechatronics" / "dc-motor.yaml")
    path = tmp_path / "bindings.yaml"
    signal = next(iter(project.signals))
    path.write_text(f"""bindings:\n  - signal: {signal}\n    endpoint:\n      adapter: webots\n      object: drive_motor\n      property: torque\n      direction: input\n""")
    manifest = BindingManifest.load(path)
    assert manifest.validate(project) == []
