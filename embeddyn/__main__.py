#!/usr/bin/env python

# Copyright (c) 2023-2024 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: Apache-2.0

"""Embeddyn command-line entry point.

Heavy simulation/UI integrations are registered only when their optional
runtime dependencies are importable. Local Studio and mechatronic tooling stay
usable in lightweight environments and CI jobs.
"""

import logging
import os
from typing import Optional

import typer

from embeddyn.init import init, embeddyn_update_workspace, embeddyn_workspace_info
from embeddyn.library.cli import library_app
from embeddyn.local.cli import studio_app
from embeddyn.mechatronics.cli import mechatronics_app

app = typer.Typer(no_args_is_help=True, add_completion=False)
app.command()(init)
app.command("info")(embeddyn_workspace_info)
app.command("update")(embeddyn_update_workspace)
app.add_typer(library_app)
app.add_typer(studio_app)
app.add_typer(mechatronics_app)

# The original Embeddyn commands depend on Git-pinned Pipeline Manager, dts2repl and
# pyrenode packages. Keep them available in a full workspace without making
# independent tooling fail at CLI import time.
try:
    from embeddyn.build import prepare_zephyr_app
    app.command()(prepare_zephyr_app)
except ImportError as error:
    logging.getLogger(__name__).debug("prepare-zephyr-app unavailable: %s", error)

try:
    from embeddyn.backend import start_embeddyn_app
    app.command("run")(start_embeddyn_app)
except ImportError as error:
    logging.getLogger(__name__).debug("interactive Embeddyn backend unavailable: %s", error)

try:
    from embeddyn.simulate import simulate
    app.command()(simulate)
except ImportError as error:
    logging.getLogger(__name__).debug("Renode simulation command unavailable: %s", error)


@app.callback()
def set_logging(log_level: Optional[str] = None):
    if not log_level:
        log_level = os.environ.get("LOGLEVEL", "INFO").upper()
    logging.basicConfig(level=log_level, format="%(levelname)s:EMBEDDYN: %(message)s")


def main():
    logging.addLevelName(logging.INFO, "\033[1;34m%s\033[1;0m" % logging.getLevelName(logging.INFO))
    logging.addLevelName(logging.WARNING, "\033[1;33m%s\033[1;0m" % logging.getLevelName(logging.WARNING))
    logging.addLevelName(logging.ERROR, "\033[1;31m%s\033[1;0m" % logging.getLevelName(logging.ERROR))
    app()


if __name__ == "__main__":
    main()
