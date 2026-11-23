from embeddyn.library.database import LibraryDatabase


def test_fts_upsert_replaces_stale_search_row(tmp_path):
    db = LibraryDatabase(tmp_path / "library.sqlite3")
    db.upsert_entity(
        entity_id="device:1",
        entity_type="device",
        name="Old Name",
        vendor="Vendor",
        category="sensor",
        description="old description",
        source_id="test",
        metadata={"aliases": ["legacy"]},
    )
    db.upsert_entity(
        entity_id="device:1",
        entity_type="device",
        name="New Name",
        vendor="Vendor",
        category="sensor",
        description="new description",
        source_id="test",
        metadata={"aliases": ["current"]},
    )
    assert db.search("Old Name") == []
    assert [item["id"] for item in db.search("New Name")] == ["device:1"]
    with db.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM entity_search WHERE entity_id='device:1'").fetchone()[0] == 1


def test_fts_search_treats_punctuation_as_literal_terms(tmp_path):
    db = LibraryDatabase(tmp_path / "library.sqlite3")
    db.upsert_entity(
        entity_id="mcu:1",
        entity_type="mcu",
        name="STM32F4 Cortex-M4",
        vendor="ST",
        category="mcu",
        description="32-bit MCU",
        source_id="test",
        metadata={},
    )
    # Previously raw FTS5 syntax here could raise sqlite3.OperationalError.
    result = db.search('STM32F4: "Cortex-M4"')
    assert result == [] or result[0]["id"] == "mcu:1"
