"""Tests for .deb extraction (tools/extract.py)."""

import io
import lzma
import tarfile
import tempfile
from pathlib import Path

from tools.deb import build_deb
from tools.extract import extract_deb


def _make_tar_xz(file_map: dict[str, bytes]) -> bytes:
    """Create a .tar.xz blob containing the given files."""
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w:xz") as tf:
        for name, data in file_map.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return tar_buf.getvalue()


def test_extract_creates_output_directory():
    control_tar = _make_tar_xz({
        "./control": b"Package: test\nVersion: 1.0\n",
        "./postinst": b"#!/bin/sh\nexit 0\n",
    })
    data_tar = _make_tar_xz({
        "./usr/bin/hello": b"#!/bin/sh\necho hello\n",
        "./etc/config": b"key=value\n",
    })
    deb_bytes = build_deb(b"2.0\n", control_tar, data_tar, timestamp=0)

    with tempfile.TemporaryDirectory() as tmpdir:
        deb_path = Path(tmpdir) / "test.deb"
        deb_path.write_bytes(deb_bytes)
        out_dir = Path(tmpdir) / "output"

        extract_deb(str(deb_path), str(out_dir))

        assert (out_dir / "control").is_dir()
        assert (out_dir / "data").is_dir()
        assert (out_dir / "debian-binary").exists()
        assert (out_dir / "debian-binary").read_text() == "2.0\n"

        # Check control contents
        assert (out_dir / "control" / "control").exists()
        assert (out_dir / "control" / "postinst").exists()

        # Check data contents
        assert (out_dir / "data" / "usr" / "bin" / "hello").exists()
        assert (out_dir / "data" / "etc" / "config").exists()
