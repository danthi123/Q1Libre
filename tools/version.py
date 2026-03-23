"""Read and write the xindi ini-style version file.

The version file lives at ``root/xindi/version`` inside the firmware
data tree and looks like::

    [version]
    mcu             = V0.10.0
    ui              = V4.4.24
    soc             = V4.4.24
"""

from __future__ import annotations

import configparser
from pathlib import Path

_SECTION = "version"


def read_version(path: Path) -> dict[str, str]:
    """Read the ini-style version file and return key/value pairs.

    Args:
        path: Path to the version file.

    Returns:
        Dict of version keys (e.g. ``{"mcu": "V0.10.0", ...}``).
    """
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")
    return dict(cp[_SECTION])


def write_version(path: Path, **updates: str) -> None:
    """Update specific keys in the version file, preserving others.

    Args:
        path: Path to the version file.
        **updates: Key/value pairs to set (e.g. ``soc="V4.4.24-q1libre1"``).
    """
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")

    for key, value in updates.items():
        cp[_SECTION][key] = value

    with open(path, "w", encoding="utf-8") as f:
        cp.write(f)
