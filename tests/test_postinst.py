# tests/test_postinst.py
from pathlib import Path
import pytest

POSTINST = Path(__file__).parent.parent / "overlay" / "control" / "postinst"


def _src() -> str:
    return POSTINST.read_text(encoding="utf-8")


def test_postinst_installs_python38_debs():
    """postinst must install the bundled python3.8 deb packages."""
    src = _src()
    assert "python38_debs" in src, "must reference python38_debs directory"
    assert "dpkg -i" in src, "must use dpkg -i to install packages"


def test_postinst_backs_up_moonraker():
    """postinst must back up existing moonraker before replacing."""
    src = _src()
    assert "moonraker.bak" in src, "must create moonraker.bak backup"


def test_postinst_chowns_new_moonraker():
    """postinst must chown the new moonraker tree to mks:mks."""
    src = _src()
    assert "chown -R mks:mks /home/mks/moonraker" in src


def test_postinst_rebuilds_moonraker_venv_with_python38():
    """postinst must rebuild the moonraker venv using python3.8."""
    src = _src()
    assert "python3.8" in src, "must use python3.8 to rebuild venv"
    assert "moonraker-env" in src, "must reference moonraker-env"
    # venv rebuild: either 'python3.8 -m venv' or recreating with python3.8
    assert "-m venv" in src, "must use -m venv to create the venv"


def test_postinst_pip_installs_moonraker_requirements():
    """postinst must pip install moonraker requirements after venv rebuild."""
    src = _src()
    assert "moonraker-requirements.txt" in src or "moonraker/scripts/" in src
    assert "pip install" in src


def test_postinst_upgrade_block_before_restart():
    """All upgrade steps must come before the service restart."""
    src = _src()
    backup_pos = src.find("moonraker.bak")
    restart_pos = src.find("systemctl restart moonraker.service")
    assert backup_pos != -1, "backup step not found"
    assert restart_pos != -1, "service restart not found"
    assert backup_pos < restart_pos, "upgrade block must precede service restart"
