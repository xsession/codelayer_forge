from __future__ import annotations

import os
from pathlib import Path

import pytest

from embeddyn.rf import RFAnalysisError, build_openems_project, run_openems_xml


def test_openems_runner_uses_argument_vector_and_xml_only(tmp_path: Path) -> None:
    model = tmp_path / "model;echo-owned.xml"
    model.write_text("<openEMS/>", encoding="utf-8")
    fake = tmp_path / "fake-openems"
    fake.write_text("#!/bin/sh\nprintf '%s\\n' \"$1\"\n", encoding="utf-8")
    fake.chmod(fake.stat().st_mode | 0o111)

    result = run_openems_xml(model, executable=str(fake), timeout_seconds=2)
    assert result.returncode == 0
    assert result.command[1] == str(model.resolve())
    assert result.stdout.strip() == str(model.resolve())
    assert not (tmp_path / "echo-owned.xml").exists()


def test_openems_runner_rejects_non_xml(tmp_path: Path) -> None:
    script = tmp_path / "model.py"
    script.write_text("print('not executed')", encoding="utf-8")
    with pytest.raises(RFAnalysisError, match="XML"):
        run_openems_xml(script, executable="ignored")



def test_openems_build_uses_upstream_driver_with_safe_arguments(tmp_path: Path) -> None:
    source = tmp_path / "openEMS project"
    source.mkdir()
    driver = source / "update_openEMS.sh"
    driver.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@"\n', encoding="utf-8")
    driver.chmod(driver.stat().st_mode | 0o111)
    prefix = tmp_path / "install prefix"

    result = build_openems_project(source, prefix, jobs=3, timeout_seconds=2)
    assert result.returncode == 0
    lines = result.stdout.splitlines()
    assert str(prefix.resolve()) in lines
    assert "--python" in lines
    assert "--disable-GUI" in lines
    assert "--njobs=3" in lines
    assert result.command[0].endswith("bash")
