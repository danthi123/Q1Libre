"""End-to-end integration tests for the full build pipeline.

Requires stock firmware at stock/QD_Q1_SOC relative to the project root.
Tests are skipped automatically when the file is not available.
"""

from __future__ import annotations

import io
import lzma
import tarfile
import tempfile
from pathlib import Path

import pytest

from tools.build import build_firmware
from tools.deb import parse_deb
from tools.extract import extract_deb
from tools.validate import validate_deb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STOCK_FIRMWARE = PROJECT_ROOT / "stock" / "QD_Q1_SOC"
OVERLAY_DIR = PROJECT_ROOT / "overlay"
PATCHES_DIR = PROJECT_ROOT / "patches"
BASE_DIR = PROJECT_ROOT / "base"

skip_no_stock = pytest.mark.skipif(
    not STOCK_FIRMWARE.exists(),
    reason=f"Stock firmware not found at {STOCK_FIRMWARE}",
)


@skip_no_stock
def test_full_build_pipeline(tmp_path: Path) -> None:
    """Extract stock -> overlay -> build -> validate -> re-extract and verify."""

    # 1. Extract stock firmware into a base/ directory
    base_dir = tmp_path / "base"
    extract_deb(str(STOCK_FIRMWARE), str(base_dir))

    # 2. Verify extraction produced expected structure
    version_file = base_dir / "data" / "root" / "xindi" / "version"
    assert version_file.exists(), "Extraction must produce root/xindi/version"

    # 3. Build firmware using project overlay
    output_path = tmp_path / "dist" / "QD_Q1_SOC"
    build_firmware(
        base_dir=base_dir,
        overlay_dir=OVERLAY_DIR,
        patches_dir=PATCHES_DIR,
        output_path=output_path,
        q1libre_version="0.1.0",
    )

    # 4. Verify output file exists
    assert output_path.exists(), "Build must produce output file"
    assert output_path.stat().st_size > 0, "Output file must not be empty"

    # 5. Validate the output using validate_deb()
    errors = validate_deb(output_path)
    assert errors == [], f"Built firmware must be valid, got errors: {errors}"

    # 6. Re-extract the built output into a check/ directory
    check_dir = tmp_path / "check"
    extract_deb(str(output_path), str(check_dir))

    data = check_dir / "data"

    # 7a. Version file contains "q1libre" marker
    check_version = data / "root" / "xindi" / "version"
    assert check_version.exists(), "Re-extracted firmware must have version file"
    version_text = check_version.read_text(encoding="utf-8")
    assert "q1libre" in version_text, (
        f"Version file must contain 'q1libre', got:\n{version_text}"
    )

    # 7b. q1libre_version.txt marker file exists
    marker = data / "root" / "q1libre_version.txt"
    assert marker.exists(), "q1libre_version.txt marker must exist"

    # 7c. moonraker.conf contains [update_manager] (not commented)
    moonraker_conf = data / "home" / "mks" / "klipper_config" / "moonraker.conf"
    assert moonraker_conf.exists(), "moonraker.conf must exist"
    moonraker_text = moonraker_conf.read_text(encoding="utf-8")
    # Find a line that starts with [update_manager] (no leading #)
    has_update_manager = any(
        line.strip().startswith("[update_manager]")
        for line in moonraker_text.splitlines()
    )
    assert has_update_manager, (
        "moonraker.conf must contain uncommented [update_manager]"
    )

    # 7d. Logrotate config exists
    logrotate = data / "etc" / "logrotate.d" / "q1libre"
    assert logrotate.exists(), "Logrotate config must exist at etc/logrotate.d/q1libre"

    # 7e. Info script exists
    info_script = data / "root" / "scripts" / "q1libre_info.sh"
    assert info_script.exists(), "Info script must exist at root/scripts/q1libre_info.sh"


@skip_no_stock
def test_validate_stock_firmware() -> None:
    """Stock firmware file must pass validation on its own."""
    errors = validate_deb(STOCK_FIRMWARE)
    assert errors == [], f"Stock firmware must be valid, got errors: {errors}"


def test_phase1_patches_in_built_deb():
    """All Phase 1 patch files must be present in a built deb's archives."""
    patches = PROJECT_ROOT / "patches"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        base = tmp / "base"

        # Minimal fake base
        ctrl = base / "control"
        ctrl.mkdir(parents=True)
        (ctrl / "control").write_text("Package: qd-q1-soc\nVersion: 4.4.24\n")
        (ctrl / "postinst").write_text("#!/bin/sh\n# STOCK\nexit 0\n")
        data = base / "data"
        version_dir = data / "root" / "xindi"
        version_dir.mkdir(parents=True)
        (version_dir / "version").write_text(
            "[version]\nmcu = V0.10.0\nui = V4.4.24\nsoc = V4.4.24\n"
        )
        (base / "debian-binary").write_text("2.0\n")

        output = tmp / "dist" / "QD_Q1_SOC"
        output.parent.mkdir(parents=True)
        build_firmware(base, OVERLAY_DIR, patches, output, q1libre_version="0.1.0-test")

        parts = parse_deb(output.read_bytes())

        # ── data.tar.xz checks ──
        with lzma.open(io.BytesIO(parts["data.tar.xz"].data)) as lz:
            with tarfile.open(fileobj=io.BytesIO(lz.read())) as tf:
                data_names = tf.getnames()
                moonraker_content = tf.extractfile(
                    next(m for m in tf.getmembers() if "moonraker.conf" in m.name)
                ).read().decode()
                bashrc_content = tf.extractfile(
                    next(m for m in tf.getmembers() if ".bashrc" in m.name)
                ).read().decode()

        assert any("moonraker.conf" in n for n in data_names), "moonraker.conf missing from data"
        assert any(".bashrc" in n for n in data_names), ".bashrc missing from data"
        assert any("sudoers.d/q1libre" in n for n in data_names), "sudoers q1libre missing from data"
        assert any("logrotate" in n for n in data_names), "logrotate config missing from data"
        assert any("q1libre_info.sh" in n for n in data_names), "q1libre_info.sh missing from data"

        # moonraker.conf must have mainsail
        assert "[update_manager mainsail]" in moonraker_content

        # .bashrc must have aliases
        assert "alias klog=" in bashrc_content
        assert "alias krestart=" in bashrc_content

        # ── control.tar.xz checks ──
        with lzma.open(io.BytesIO(parts["control.tar.xz"].data)) as lz:
            with tarfile.open(fileobj=io.BytesIO(lz.read())) as tf:
                postinst = tf.extractfile("./postinst").read().decode()

        assert "chmod 777" not in postinst, "chmod 777 must not be in postinst"
        assert "resolv.conf" not in postinst, "hardcoded DNS must not be in postinst"
        assert "sysctl.conf" not in postinst, "IPv6 disable must not be in postinst"
        assert "q1libre_version.txt" in postinst, "Q1Libre marker must be in postinst"


@skip_no_stock
def test_moonraker_in_built_deb(tmp_path: Path) -> None:
    """Built deb must contain the upgraded moonraker tree."""
    output_deb = tmp_path / "q1libre-test.deb"
    build_firmware(
        base_dir=BASE_DIR,
        overlay_dir=OVERLAY_DIR,
        patches_dir=PATCHES_DIR,
        output_path=output_deb,
        q1libre_version="0.2.0-phase2a",
    )
    assert output_deb.exists(), "build must produce output file"

    parts = parse_deb(output_deb.read_bytes())
    with lzma.open(io.BytesIO(parts["data.tar.xz"].data)) as lz:
        with tarfile.open(fileobj=io.BytesIO(lz.read())) as tf:
            names = tf.getnames()

    moonraker_files = [n for n in names if "moonraker/moonraker.py" in n]
    assert moonraker_files, f"moonraker.py not found in deb. Files: {names[:20]}"


@skip_no_stock
def test_python38_debs_in_built_deb(tmp_path: Path) -> None:
    """Built deb must contain the python3.8 .deb packages."""
    output_deb = tmp_path / "q1libre-test.deb"
    build_firmware(
        base_dir=BASE_DIR,
        overlay_dir=OVERLAY_DIR,
        patches_dir=PATCHES_DIR,
        output_path=output_deb,
        q1libre_version="0.2.0-phase2a",
    )
    assert output_deb.exists(), "build must produce output file"

    parts = parse_deb(output_deb.read_bytes())
    with lzma.open(io.BytesIO(parts["data.tar.xz"].data)) as lz:
        with tarfile.open(fileobj=io.BytesIO(lz.read())) as tf:
            names = tf.getnames()

    py38_files = [n for n in names if "python38_debs" in n and ".deb" in n]
    assert py38_files, f"python3.8 .deb packages not found in built deb. Files: {names[:30]}"
