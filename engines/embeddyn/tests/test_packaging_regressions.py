from importlib.resources import files
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_embeddyn_resource_packages_and_branding_paths_exist():
    assert files("embeddyn.templates").joinpath("run.resc").is_file()
    assert files("embeddyn.spec_mods").joinpath("interactive.json").is_file()
    assert "files('vsd.templates')" not in (ROOT / "embeddyn" / "build.py").read_text(encoding="utf-8")
    assert "files('vsd.spec_mods')" not in (ROOT / "embeddyn" / "backend.py").read_text(encoding="utf-8")


def test_studio_extra_and_desktop_resource_paths_are_valid():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert "studio" in project["optional-dependencies"]
    desktop = (ROOT / "packaging" / "build_desktop.py").read_text(encoding="utf-8")
    assert "root / 'embeddyn' / 'local' / 'static'" in desktop
    assert "root / 'embeddyn' / 'local' / 'assets'" in desktop
    assert "root / 'vsd' / 'local'" not in desktop
