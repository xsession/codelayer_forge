import json

from importlib.resources import files
from io import BytesIO

from embeddyn.local.store import LocalStore


def test_catalog_assets_and_projects(tmp_path):
    store = LocalStore(tmp_path)
    imported = store.import_component_catalog(files("embeddyn.local.assets").joinpath("components.csv"))
    assert imported == 500
    assert store.component_stats()["total"] == 500
    assert len(store.search_components("ssd1306")) >= 1

    library = tmp_path / "designer-library.json"
    library.write_text(json.dumps({
        "components": [
            {
                "id": "pic32mz-ef",
                "category": "controller",
                "name": "PIC32MZ EF",
                "manufacturer": "Microchip",
                "renode_class": "Antmicro.Renode.Peripherals.CPU.PIC32MZ",
            }
        ]
    }), encoding="utf-8")
    assert store.import_component_library(library) == 1
    assert store.search_components("PIC32MZ")[0].metadata["source"] == "designer-antmicro-library"

    first = store.put_asset(BytesIO(b"firmware"), name="fw.bin")
    second = store.put_asset(BytesIO(b"firmware"), name="copy.bin")
    assert first.id == second.id
    assert first.stored_path.read_bytes() == b"firmware"

    project_id = store.save_project("demo", {"nodes": [{"id": "n1"}], "edges": []})
    project = store.get_project(project_id)
    assert project["name"] == "demo"
    assert project["graph"]["nodes"][0]["id"] == "n1"


def test_asset_dedup_preserves_original_metadata_and_cleans_failed_temp(tmp_path):
    store = LocalStore(tmp_path)
    first = store.put_asset(BytesIO(b"same"), name="first.bin", mime="application/octet-stream")
    second = store.put_asset(BytesIO(b"same"), name="renamed.txt", mime="text/plain")
    assert second.id == first.id
    assert second.name == "first.bin"
    assert second.mime == "application/octet-stream"

    class BrokenReader:
        def __init__(self):
            self.calls = 0

        def read(self, _size):
            self.calls += 1
            if self.calls == 1:
                return b"partial"
            raise OSError("read failed")

    import pytest
    with pytest.raises(OSError, match="read failed"):
        store.put_asset(BrokenReader(), name="broken.bin")
    assert not list(tmp_path.glob(".asset-*.tmp"))


def test_log_timestamp_zero_is_preserved(tmp_path):
    store = LocalStore(tmp_path)
    store.append_log(message="epoch", timestamp=0.0)
    assert store.query_logs()[0]["timestamp"] == 0.0


def test_component_library_rejects_unknown_format_and_bad_metadata(tmp_path):
    import pytest

    store = LocalStore(tmp_path / "store")
    unknown = tmp_path / "library.txt"
    unknown.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported component library format"):
        store.import_component_library(unknown)

    malformed = tmp_path / "library.json"
    malformed.write_text(json.dumps({"components": [{"id": "bad", "metadata": "not-an-object"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="metadata must be an object"):
        store.import_component_library(malformed)
