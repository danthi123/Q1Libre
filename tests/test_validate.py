"""Tests for .deb validation (tools/validate.py)."""

import io
import lzma
import tarfile
import tempfile
from pathlib import Path

from tools.deb import build_deb
from tools.validate import validate_deb


def _build_control_tar(include_postinst: bool = True) -> bytes:
    """Build a control.tar.xz with ./control and optionally ./postinst."""
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w") as tf:
        # ./control
        control_content = b"Package: qd-q1-soc\nVersion: 4.4.24\n"
        info = tarfile.TarInfo(name="./control")
        info.size = len(control_content)
        tf.addfile(info, io.BytesIO(control_content))

        # ./postinst
        if include_postinst:
            postinst_content = b"#!/bin/sh\nexit 0\n"
            info = tarfile.TarInfo(name="./postinst")
            info.size = len(postinst_content)
            tf.addfile(info, io.BytesIO(postinst_content))

    return lzma.compress(tar_buf.getvalue(), preset=6)


def _build_data_tar() -> bytes:
    """Build a data.tar.xz with ./root/xindi/version containing q1libre marker."""
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w") as tf:
        version_content = (
            b"[version]\n"
            b"mcu             = V0.10.0\n"
            b"ui              = V4.4.24\n"
            b"soc             = V4.4.24-q1libre0.1.0\n"
        )
        info = tarfile.TarInfo(name="./root/xindi/version")
        info.size = len(version_content)
        tf.addfile(info, io.BytesIO(version_content))

    return lzma.compress(tar_buf.getvalue(), preset=6)


def test_validate_valid_deb():
    """Build a minimal valid .deb with all required contents, assert no errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        deb_path = Path(tmpdir) / "test.deb"

        control_tar = _build_control_tar(include_postinst=True)
        data_tar = _build_data_tar()
        deb_bytes = build_deb(b"2.0\n", control_tar, data_tar, timestamp=12345)

        deb_path.write_bytes(deb_bytes)

        errors = validate_deb(deb_path)
        # Filter out size warnings — our minimal test .deb is legitimately small
        real_errors = [e for e in errors if "File size" not in e]
        assert real_errors == [], f"Expected no errors, got: {real_errors}"


def test_validate_bad_magic():
    """Write garbage bytes to a file, validate, assert error about ar archive."""
    with tempfile.TemporaryDirectory() as tmpdir:
        deb_path = Path(tmpdir) / "garbage.deb"
        deb_path.write_bytes(b"this is not an ar archive at all")

        errors = validate_deb(deb_path)
        assert len(errors) > 0, "Expected errors for garbage file"
        assert any("ar archive" in e.lower() or "magic" in e.lower() for e in errors), (
            f"Expected error about ar archive or magic, got: {errors}"
        )


def test_validate_missing_postinst():
    """Build a .deb where control.tar.xz is missing ./postinst, assert error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        deb_path = Path(tmpdir) / "no_postinst.deb"

        control_tar = _build_control_tar(include_postinst=False)
        data_tar = _build_data_tar()
        deb_bytes = build_deb(b"2.0\n", control_tar, data_tar, timestamp=12345)

        deb_path.write_bytes(deb_bytes)

        errors = validate_deb(deb_path)
        assert len(errors) > 0, "Expected errors for missing postinst"
        assert any("postinst" in e.lower() for e in errors), (
            f"Expected error about missing postinst, got: {errors}"
        )
