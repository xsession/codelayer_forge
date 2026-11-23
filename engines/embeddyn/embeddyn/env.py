# Copyright (c) 2023-2024 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import sys
import yaml

from functools import wraps
from pathlib import Path


# Global Embeddyn environment
__embeddyn_workspace = None
__embeddyn_env = None


def setup_embeddyn_env():
    """
    Set up the environment for Embeddyn from an initialized workspace.

    EMBEDDYN_WORKSPACE is preferred. VSD_WORKSPACE and the legacy vsd-env.yml
    file are accepted during migration from the former project identity.
    """
    global __embeddyn_workspace
    global __embeddyn_env

    if __embeddyn_workspace:
        return

    workspace_value = os.environ.get("EMBEDDYN_WORKSPACE") or os.environ.get("VSD_WORKSPACE")
    workspace = Path(workspace_value) if workspace_value else Path(".")

    env_file = workspace / "embeddyn-env.yml"
    if not env_file.exists():
        legacy_env_file = workspace / "vsd-env.yml"
        if legacy_env_file.exists():
            env_file = legacy_env_file
        else:
            logging.error(
                f"Can't find {workspace / 'embeddyn-env.yml'}. Have you initialized an Embeddyn workspace?\n"
                "Run `embeddyn init [workspace dir]` or export EMBEDDYN_WORKSPACE."
            )
            sys.exit(1)

    with open(env_file, encoding="utf-8") as f:
        values = yaml.safe_load(f) or {}

    os.environ.update(values)
    __embeddyn_workspace = workspace
    __embeddyn_env = values


def setup_env(func):
    """Decorator that initializes the Embeddyn environment before a command."""
    @wraps(func)
    def inner(*args, **kwargs):
        if not __embeddyn_env:
            setup_embeddyn_env()
        return func(*args, **kwargs)
    return inner


def _embeddyn_env_not_found_err():
    logging.error(
        "Embeddyn environment not found.\n"
        "Call embeddyn.env.setup_embeddyn_env() or decorate the function with embeddyn.env.setup_env."
    )
    sys.exit(1)


def get_workspace():
    if not __embeddyn_workspace:
        _embeddyn_env_not_found_err()
    return __embeddyn_workspace


def get_var(var_name):
    if not __embeddyn_workspace:
        _embeddyn_env_not_found_err()
    return __embeddyn_env.get(var_name)


def get_env():
    if not __embeddyn_workspace:
        _embeddyn_env_not_found_err()
    return __embeddyn_env


# Compatibility alias used by older integrations.
setup_vsd_env = setup_embeddyn_env
