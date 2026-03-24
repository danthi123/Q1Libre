# tests/test_postinst.py
from pathlib import Path
import pytest

POSTINST = Path(__file__).parent.parent / "overlay" / "control" / "postinst"


def _src() -> str:
    return POSTINST.read_text(encoding="utf-8")


def test_postinst_backs_up_moonraker():
    """postinst must back up existing moonraker before replacing."""
    src = _src()
    assert "moonraker.bak" in src, "must create moonraker.bak backup"


def test_postinst_chowns_new_moonraker():
    """postinst must chown the new moonraker tree to mks:mks."""
    src = _src()
    assert "chown -R mks:mks /home/mks/moonraker" in src


def test_postinst_creates_thirdparty_symlink():
    """postinst must create the thirdparty symlink for module resolution."""
    src = _src()
    assert "ln -sf /home/mks/moonraker/moonraker/thirdparty /home/mks/moonraker/thirdparty" in src


def test_postinst_no_python38():
    """postinst must NOT reference python3.8 (removed in Phase 2B)."""
    src = _src()
    assert "python3.8" not in src, "python3.8 references must be removed"
    assert "python38_debs" not in src, "python38_debs references must be removed"


def test_postinst_protects_moonraker_conf():
    """postinst must uncomment update_manager after merge.py runs."""
    src = _src()
    merge_pos = src.find("merge.py")
    sed_pos = src.find("sed -i 's/^# \\[update_manager\\]")
    assert merge_pos != -1, "merge.py call not found"
    assert sed_pos != -1, "update_manager sed fix not found"
    assert sed_pos > merge_pos, "update_manager fix must come after merge.py call"


def test_postinst_upgrade_block_before_restart():
    """All upgrade steps must come before the service restart."""
    src = _src()
    backup_pos = src.find("moonraker.bak")
    restart_pos = src.find("systemctl restart moonraker.service")
    assert backup_pos != -1, "backup step not found"
    assert restart_pos != -1, "service restart not found"
    assert backup_pos < restart_pos, "upgrade block must precede service restart"
