"""End-to-end integration tests for the full build pipeline.

Requires stock firmware at stock/QD_Q1_SOC relative to the project root.
Tests are skipped automatically when the file is not available.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.build import build_firmware
from tools.extract import extract_deb
from tools.validate import validate_deb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STOCK_FIRMWARE = PROJECT_ROOT / "stock" / "QD_Q1_SOC"
OVERLAY_DIR = PROJECT_ROOT / "overlay"
PATCHES_DIR = PROJECT_ROOT / "patches"

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
