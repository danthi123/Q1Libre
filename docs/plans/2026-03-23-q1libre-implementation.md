# Q1Libre Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a patch-based firmware build system for the Qidi Q1 Pro that produces USB-deployable `.deb` packages, starting with Phase 1 quick wins.

**Architecture:** Python-based build toolchain that extracts stock Qidi `.deb` firmware, applies patches/overlays, and repacks into a valid `.deb`. Stock firmware is never committed — users provide their own. Output is a drop-in replacement for `QD_Update/QD_Q1_SOC` on a USB stick.

**Tech Stack:** Python 3.12+, standard library only (struct, tarfile, lzma, configparser, shutil, subprocess), Git, dpkg-deb format (reimplemented in pure Python for cross-platform builds).

---

## Task 1: Initialize Git Repository and Project Scaffold

**Files:**
- Create: `q1libre/README.md`
- Create: `q1libre/.gitignore`
- Create: `q1libre/LICENSE`
- Create: `q1libre/pyproject.toml`

**Step 1: Create project root directory**

```bash
mkdir -p E:/Projects/q1libre
cd E:/Projects/q1libre
git init
```

**Step 2: Create .gitignore**

```gitignore
# Stock firmware — never committed (copyright)
base/
stock/

# Build output
build/
dist/
*.deb

# Python
__pycache__/
*.pyc
.venv/

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
```

**Step 3: Create LICENSE**

GPLv3 full text (matching Klipper).

**Step 4: Create README.md**

```markdown
# Q1Libre

Open firmware patches for the Qidi Q1 Pro 3D printer.

Q1Libre produces `.deb` packages compatible with the stock Qidi update mechanism.
No special hardware needed — just a USB stick.

## Quick Start

1. Place your stock `QD_Q1_SOC` firmware file in `stock/`
2. Run `python tools/extract.py`
3. Run `python tools/build.py`
4. Copy `dist/QD_Q1_SOC` to a USB stick under `QD_Update/`
5. Plug USB into printer — the stock update flow handles installation

## Reversibility

To restore stock firmware, copy the original `QD_Q1_SOC` to `QD_Update/` on a USB stick and update again.

## Phases

- **Phase 1:** Config improvements, security fixes, QoL patches (no Klipper version change)
- **Phase 2:** Upgrade Klipper to v0.12+ with ported Qidi hardware modules
- **Phase 3:** Full upstream Klipper + Moonraker with native Qidi support

## License

GPLv3 — matching Klipper.
```

**Step 5: Create pyproject.toml**

```toml
[project]
name = "q1libre"
version = "0.1.0"
description = "Open firmware patches for the Qidi Q1 Pro"
requires-python = ">=3.10"
license = "GPL-3.0-or-later"

[project.scripts]
q1libre-extract = "tools.extract:main"
q1libre-build = "tools.build:main"
q1libre-validate = "tools.validate:main"
q1libre-diff = "tools.diff:main"
```

**Step 6: Create directory skeleton**

```bash
mkdir -p tools patches/klipper patches/moonraker patches/configs patches/system
mkdir -p overlay/klipper overlay/scripts
mkdir -p docs tests
```

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: initialize q1libre project scaffold"
```

---

## Task 2: Build the Stock Firmware Extractor (`tools/extract.py`)

**Files:**
- Create: `q1libre/tools/__init__.py`
- Create: `q1libre/tools/extract.py`
- Create: `q1libre/tools/deb.py` (shared .deb parsing library)
- Test: `q1libre/tests/test_deb.py`
- Test: `q1libre/tests/test_extract.py`

**Step 1: Write test for .deb ar archive parsing**

```python
# tests/test_deb.py
import struct
import io
import pytest
from tools.deb import parse_ar_archive, ArMember

def make_ar_archive(members: list[tuple[str, bytes]]) -> bytes:
    """Build a minimal ar archive for testing."""
    buf = io.BytesIO()
    buf.write(b"!<arch>\n")
    for name, data in members:
        header = f"{name:<16s}0           0     0     100644  {len(data):<10d}`\n"
        buf.write(header.encode("ascii"))
        buf.write(data)
        if len(data) % 2:
            buf.write(b"\n")
    return buf.getvalue()

def test_parse_ar_archive_basic():
    raw = make_ar_archive([
        ("debian-binary", b"2.0\n"),
        ("control.tar.xz", b"fake-control-data"),
        ("data.tar.xz", b"fake-data-payload"),
    ])
    members = parse_ar_archive(raw)
    assert len(members) == 3
    assert members[0].name == "debian-binary"
    assert members[0].data == b"2.0\n"
    assert members[1].name == "control.tar.xz"
    assert members[2].name == "data.tar.xz"
    assert members[2].data == b"fake-data-payload"

def test_parse_ar_archive_bad_magic():
    with pytest.raises(ValueError, match="Not an ar archive"):
        parse_ar_archive(b"not-an-archive")
```

**Step 2: Run test to verify it fails**

```bash
cd E:/Projects/q1libre
python -m pytest tests/test_deb.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'tools.deb'`

**Step 3: Implement `tools/deb.py` — ar archive parser and .deb builder**

```python
# tools/deb.py
"""
Pure-Python .deb (ar archive) parser and builder.
Cross-platform — no dpkg or ar binary needed.
"""
from __future__ import annotations
import io
import struct
import time
from dataclasses import dataclass

AR_MAGIC = b"!<arch>\n"
AR_HEADER_SIZE = 60

@dataclass
class ArMember:
    name: str
    timestamp: int
    owner_id: int
    group_id: int
    mode: int
    data: bytes

def parse_ar_archive(raw: bytes) -> list[ArMember]:
    """Parse an ar archive into its members."""
    if not raw.startswith(AR_MAGIC):
        raise ValueError("Not an ar archive: bad magic")

    members = []
    offset = len(AR_MAGIC)

    while offset < len(raw):
        if offset + AR_HEADER_SIZE > len(raw):
            break

        header = raw[offset:offset + AR_HEADER_SIZE]
        name = header[0:16].decode("ascii").rstrip()
        # Strip trailing '/' from name (common in ar)
        name = name.rstrip("/")
        timestamp = int(header[16:28].decode("ascii").strip() or "0")
        owner_id = int(header[28:34].decode("ascii").strip() or "0")
        group_id = int(header[34:40].decode("ascii").strip() or "0")
        mode = int(header[40:48].decode("ascii").strip() or "0", 8)
        size = int(header[48:58].decode("ascii").strip())

        if header[58:60] != b"`\n":
            raise ValueError(f"Bad ar header terminator for member '{name}'")

        data_start = offset + AR_HEADER_SIZE
        data = raw[data_start:data_start + size]

        members.append(ArMember(
            name=name,
            timestamp=timestamp,
            owner_id=owner_id,
            group_id=group_id,
            mode=mode,
            data=data,
        ))

        # ar pads to even byte boundary
        offset = data_start + size + (size % 2)

    return members

def build_ar_archive(members: list[ArMember]) -> bytes:
    """Build an ar archive from members."""
    buf = io.BytesIO()
    buf.write(AR_MAGIC)

    for member in members:
        name_field = f"{member.name + '/':<16s}" if "/" not in member.name else f"{member.name:<16s}"
        # Use simple name without trailing slash for debian packages
        name_field = f"{member.name:<16s}"
        header = (
            f"{name_field}"
            f"{member.timestamp:<12d}"
            f"{member.owner_id:<6d}"
            f"{member.group_id:<6d}"
            f"{member.mode:<8o}"
            f"{len(member.data):<10d}"
            "`\n"
        )
        buf.write(header.encode("ascii"))
        buf.write(member.data)
        if len(member.data) % 2:
            buf.write(b"\n")

    return buf.getvalue()

def parse_deb(raw: bytes) -> dict[str, ArMember]:
    """Parse a .deb file. Returns dict keyed by member name."""
    members = parse_ar_archive(raw)
    return {m.name: m for m in members}

def build_deb(debian_binary: bytes, control_tar: bytes, data_tar: bytes,
              timestamp: int | None = None) -> bytes:
    """Build a .deb file from its three components."""
    ts = timestamp or int(time.time())
    members = [
        ArMember("debian-binary", ts, 0, 0, 0o100644, debian_binary),
        ArMember("control.tar.xz", ts, 0, 0, 0o100644, control_tar),
        ArMember("data.tar.xz", ts, 0, 0, 0o100644, data_tar),
    ]
    return build_ar_archive(members)
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_deb.py -v
```

Expected: PASS

**Step 5: Write test for extract tool**

```python
# tests/test_extract.py
import os
import tempfile
import pytest
from tools.deb import make_test_deb
from tools.extract import extract_deb

# This test uses a real stock firmware file if available,
# otherwise tests basic extraction logic with a synthetic deb.

def test_extract_creates_output_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        stock_path = os.path.join(tmpdir, "QD_Q1_SOC")
        out_path = os.path.join(tmpdir, "base")
        # Create minimal synthetic deb for testing
        # (Real stock firmware test is in tests/test_extract_stock.py)
        from tools.deb import build_deb
        import lzma, tarfile, io

        # Build a minimal control.tar.xz
        control_buf = io.BytesIO()
        with tarfile.open(fileobj=control_buf, mode="w:xz") as tar:
            info = tarfile.TarInfo("./control")
            content = b"Package: test\nVersion: 0.1\n"
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        control_data = control_buf.getvalue()

        # Build a minimal data.tar.xz
        data_buf = io.BytesIO()
        with tarfile.open(fileobj=data_buf, mode="w:xz") as tar:
            info = tarfile.TarInfo("./test.txt")
            content = b"hello"
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        data_data = data_buf.getvalue()

        deb_bytes = build_deb(b"2.0\n", control_data, data_data)
        with open(stock_path, "wb") as f:
            f.write(deb_bytes)

        extract_deb(stock_path, out_path)

        assert os.path.isdir(out_path)
        assert os.path.isdir(os.path.join(out_path, "data"))
        assert os.path.isdir(os.path.join(out_path, "control"))
        assert os.path.isfile(os.path.join(out_path, "data", "test.txt"))
        assert os.path.isfile(os.path.join(out_path, "control", "control"))
```

**Step 6: Implement `tools/extract.py`**

```python
# tools/extract.py
"""
Extract a stock Qidi QD_Q1_SOC firmware file (.deb) into base/ for analysis.
"""
from __future__ import annotations
import io
import lzma
import os
import shutil
import sys
import tarfile
from pathlib import Path

from tools.deb import parse_ar_archive

def extract_tar_xz(data: bytes, dest: Path) -> None:
    """Extract a .tar.xz blob to a directory."""
    dest.mkdir(parents=True, exist_ok=True)
    with lzma.open(io.BytesIO(data)) as xz:
        with tarfile.open(fileobj=io.BytesIO(xz.read())) as tar:
            tar.extractall(dest, filter="data")

def extract_deb(deb_path: str, output_dir: str) -> None:
    """Extract a .deb into output_dir/control/ and output_dir/data/."""
    deb_path = Path(deb_path)
    output = Path(output_dir)

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    raw = deb_path.read_bytes()
    members = parse_ar_archive(raw)
    member_map = {m.name: m for m in members}

    # Extract control archive
    control_key = next((k for k in member_map if k.startswith("control.tar")), None)
    if control_key:
        extract_tar_xz(member_map[control_key].data, output / "control")

    # Extract data archive
    data_key = next((k for k in member_map if k.startswith("data.tar")), None)
    if data_key:
        extract_tar_xz(member_map[data_key].data, output / "data")

    # Save debian-binary version
    if "debian-binary" in member_map:
        (output / "debian-binary").write_bytes(member_map["debian-binary"].data)

    print(f"Extracted to {output}")
    print(f"  control/: {sum(1 for _ in (output / 'control').rglob('*') if _.is_file())} files")
    print(f"  data/:    {sum(1 for _ in (output / 'data').rglob('*') if _.is_file())} files")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract stock Qidi firmware .deb")
    parser.add_argument("input", help="Path to QD_Q1_SOC file")
    parser.add_argument("-o", "--output", default="base", help="Output directory (default: base/)")
    args = parser.parse_args()
    extract_deb(args.input, args.output)

if __name__ == "__main__":
    main()
```

**Step 7: Run tests**

```bash
python -m pytest tests/ -v
```

Expected: ALL PASS

**Step 8: Test with real firmware**

```bash
cd E:/Projects/q1libre
mkdir -p stock
cp "E:/Downloads/Q1_V4.4.24/QD_Update/QD_Q1_SOC" stock/
python -m tools.extract stock/QD_Q1_SOC -o base
```

Expected: Extracts 123 files, prints summary.

**Step 9: Commit**

```bash
git add tools/ tests/
git commit -m "feat: add .deb parser and stock firmware extractor"
```

---

## Task 3: Build the Patch/Overlay System (`tools/build.py`)

**Files:**
- Create: `q1libre/tools/build.py`
- Create: `q1libre/tools/version.py`
- Test: `q1libre/tests/test_build.py`

**Step 1: Write test for version bumping**

```python
# tests/test_build.py
import tempfile
import os
from pathlib import Path
from tools.version import read_version, write_version

def test_read_write_version():
    with tempfile.TemporaryDirectory() as tmpdir:
        version_file = Path(tmpdir) / "version"
        version_file.write_text(
            "[version]\n"
            "mcu             = V0.10.0\n"
            "ui              = V4.4.24\n"
            "soc             = V4.4.24\n"
        )
        ver = read_version(version_file)
        assert ver["soc"] == "V4.4.24"

        write_version(version_file, soc="V4.4.24-q1libre0.1.0")
        ver2 = read_version(version_file)
        assert ver2["soc"] == "V4.4.24-q1libre0.1.0"
        # mcu and ui untouched
        assert ver2["mcu"] == "V0.10.0"
        assert ver2["ui"] == "V4.4.24"
```

**Step 2: Run test — verify fail**

```bash
python -m pytest tests/test_build.py::test_read_write_version -v
```

**Step 3: Implement `tools/version.py`**

```python
# tools/version.py
"""Read and write the xindi version file."""
from __future__ import annotations
import configparser
from pathlib import Path

def read_version(path: Path) -> dict[str, str]:
    cp = configparser.ConfigParser()
    cp.read(path)
    return dict(cp["version"])

def write_version(path: Path, **updates: str) -> None:
    cp = configparser.ConfigParser()
    cp.read(path)
    for key, value in updates.items():
        cp["version"][key] = value
    with open(path, "w") as f:
        cp.write(f)
```

**Step 4: Run test — verify pass**

**Step 5: Write test for full build pipeline**

```python
# tests/test_build.py (append)
from tools.build import build_firmware
from tools.extract import extract_deb
from tools.deb import parse_ar_archive
import lzma, tarfile, io

def _make_fake_base(tmpdir: str) -> Path:
    """Create a minimal fake extracted base for build testing."""
    base = Path(tmpdir) / "base"

    # control files
    control_dir = base / "control"
    control_dir.mkdir(parents=True)
    (control_dir / "control").write_text(
        "Package: Makerbase-Client\nVersion: 0.1.1\nArchitecture: arm64\n"
    )
    (control_dir / "postinst").write_text("#!/bin/bash\necho stock\n")
    (control_dir / "preinst").write_text("#!/bin/bash\necho pre\n")
    (control_dir / "postrm").write_text("#!/bin/bash\n")

    # data files
    data_dir = base / "data"
    (data_dir / "root" / "xindi").mkdir(parents=True)
    (data_dir / "root" / "xindi" / "version").write_text(
        "[version]\nmcu = V0.10.0\nui = V4.4.24\nsoc = V4.4.24\n"
    )
    (data_dir / "home" / "mks" / "klipper_config").mkdir(parents=True)
    (data_dir / "home" / "mks" / "klipper_config" / "moonraker.conf").write_text(
        "# stock moonraker\n"
    )
    (base / "debian-binary").write_bytes(b"2.0\n")
    return base

def test_build_produces_valid_deb(tmp_path):
    base = _make_fake_base(str(tmp_path))

    # Create an overlay
    overlay_dir = tmp_path / "overlay"
    config_dir = overlay_dir / "home" / "mks" / "klipper_config"
    config_dir.mkdir(parents=True)
    (config_dir / "moonraker.conf").write_text("# q1libre moonraker\n")

    output = tmp_path / "dist" / "QD_Q1_SOC"
    build_firmware(
        base_dir=base,
        overlay_dir=overlay_dir,
        patches_dir=None,
        output_path=output,
        q1libre_version="0.1.0",
    )

    assert output.exists()
    assert output.stat().st_size > 0

    # Verify it's a valid ar archive
    raw = output.read_bytes()
    members = parse_ar_archive(raw)
    names = [m.name for m in members]
    assert "debian-binary" in names
    assert any("control" in n for n in names)
    assert any("data" in n for n in names)
```

**Step 6: Implement `tools/build.py`**

```python
# tools/build.py
"""
Build a patched Q1Libre .deb from extracted base + patches + overlays.
"""
from __future__ import annotations
import io
import lzma
import os
import shutil
import tarfile
from pathlib import Path

from tools.deb import ArMember, build_ar_archive
from tools.version import read_version, write_version

Q1LIBRE_VERSION_KEY = "q1libre_version"

def _build_tar_xz(source_dir: Path) -> bytes:
    """Build a .tar.xz from a directory."""
    buf = io.BytesIO()
    raw_tar = io.BytesIO()
    with tarfile.open(fileobj=raw_tar, mode="w") as tar:
        for root, dirs, files in os.walk(source_dir):
            for d in sorted(dirs):
                full = Path(root) / d
                arcname = "./" + str(full.relative_to(source_dir)).replace("\\", "/")
                tar.add(full, arcname=arcname, recursive=False)
            for f in sorted(files):
                full = Path(root) / f
                arcname = "./" + str(full.relative_to(source_dir)).replace("\\", "/")
                tar.add(full, arcname=arcname)

    raw_tar.seek(0)
    compressed = lzma.compress(raw_tar.read(), preset=6)
    return compressed

def build_firmware(
    base_dir: Path,
    overlay_dir: Path | None,
    patches_dir: Path | None,
    output_path: Path,
    q1libre_version: str,
) -> None:
    """Build a patched .deb firmware file."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        work = Path(tmpdir)
        work_data = work / "data"
        work_control = work / "control"

        # 1. Copy base
        shutil.copytree(base_dir / "data", work_data)
        shutil.copytree(base_dir / "control", work_control)

        # 2. Apply overlays (file replacement)
        if overlay_dir and overlay_dir.exists():
            for src_file in overlay_dir.rglob("*"):
                if src_file.is_file():
                    rel = src_file.relative_to(overlay_dir)
                    dest = work_data / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dest)
                    print(f"  overlay: {rel}")

        # 3. Apply patches (unified diff format)
        if patches_dir and patches_dir.exists():
            _apply_patches(patches_dir, work_data, work_control)

        # 4. Update version
        version_file = work_data / "root" / "xindi" / "version"
        if version_file.exists():
            write_version(version_file, soc=f"V4.4.24-q1libre{q1libre_version}")

        # 5. Add Q1Libre marker
        marker = work_data / "root" / "q1libre_version.txt"
        marker.write_text(f"q1libre {q1libre_version}\n")

        # 6. Build tar archives
        control_tar = _build_tar_xz(work_control)
        data_tar = _build_tar_xz(work_data)
        debian_binary = (base_dir / "debian-binary").read_bytes()

        # 7. Build .deb
        import time
        ts = int(time.time())
        members = [
            ArMember("debian-binary", ts, 0, 0, 0o100644, debian_binary),
            ArMember("control.tar.xz", ts, 0, 0, 0o100644, control_tar),
            ArMember("data.tar.xz", ts, 0, 0, 0o100644, data_tar),
        ]
        deb_bytes = build_ar_archive(members)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(deb_bytes)
        print(f"\nBuilt: {output_path} ({len(deb_bytes):,} bytes)")

def _apply_patches(patches_dir: Path, data_dir: Path, control_dir: Path) -> None:
    """Apply .patch files from patches directory."""
    # For now, patches are organized as:
    #   patches/configs/*.patch  -> applied to data/home/mks/klipper_config/
    #   patches/system/*.patch   -> applied to data/ (root paths)
    #   patches/klipper/*.patch  -> applied to data/home/mks/klipper/
    #   patches/moonraker/*.patch -> applied to data/home/mks/moonraker/
    #   patches/control/*.patch  -> applied to control/
    # Each .patch file is a unified diff.
    # For Phase 1, we primarily use overlays (full file replacement).
    # Patch support is for surgical single-line changes.
    pass  # Implemented in Task 6 when we have actual patches

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build Q1Libre firmware .deb")
    parser.add_argument("--base", default="base", help="Extracted base directory")
    parser.add_argument("--overlay", default="overlay", help="Overlay directory")
    parser.add_argument("--patches", default="patches", help="Patches directory")
    parser.add_argument("-o", "--output", default="dist/QD_Q1_SOC", help="Output path")
    parser.add_argument("--version", default="0.1.0", help="Q1Libre version")
    args = parser.parse_args()

    build_firmware(
        base_dir=Path(args.base),
        overlay_dir=Path(args.overlay),
        patches_dir=Path(args.patches),
        output_path=Path(args.output),
        q1libre_version=args.version,
    )

if __name__ == "__main__":
    main()
```

**Step 7: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: ALL PASS

**Step 8: Commit**

```bash
git add tools/ tests/
git commit -m "feat: add firmware build pipeline with overlay support"
```

---

## Task 4: Build the Validator (`tools/validate.py`)

**Files:**
- Create: `q1libre/tools/validate.py`
- Test: `q1libre/tests/test_validate.py`

**Step 1: Write test**

```python
# tests/test_validate.py
from pathlib import Path
from tools.validate import validate_deb
from tools.deb import build_deb, ArMember, build_ar_archive
import lzma, tarfile, io

def _make_valid_deb() -> bytes:
    """Build a minimal valid .deb for testing."""
    control_buf = io.BytesIO()
    with tarfile.open(fileobj=control_buf, mode="w:xz") as tar:
        info = tarfile.TarInfo("./control")
        content = b"Package: test\nVersion: 0.1\nArchitecture: arm64\n"
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))
        info2 = tarfile.TarInfo("./postinst")
        script = b"#!/bin/bash\necho ok\n"
        info2.size = len(script)
        info2.mode = 0o755
        tar.addfile(info2, io.BytesIO(script))

    data_buf = io.BytesIO()
    with tarfile.open(fileobj=data_buf, mode="w:xz") as tar:
        info = tarfile.TarInfo("./root/xindi/version")
        content = b"[version]\nmcu = V0.10.0\nui = V4.4.24\nsoc = V4.4.24-q1libre0.1.0\n"
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))

    return build_deb(b"2.0\n", control_buf.getvalue(), data_buf.getvalue())

def test_validate_valid_deb(tmp_path):
    deb_path = tmp_path / "QD_Q1_SOC"
    deb_path.write_bytes(_make_valid_deb())
    errors = validate_deb(deb_path)
    assert errors == [], f"Unexpected errors: {errors}"

def test_validate_bad_magic(tmp_path):
    bad = tmp_path / "QD_Q1_SOC"
    bad.write_bytes(b"not a deb file")
    errors = validate_deb(bad)
    assert any("ar archive" in e.lower() or "magic" in e.lower() for e in errors)
```

**Step 2: Run test — verify fail**

**Step 3: Implement `tools/validate.py`**

```python
# tools/validate.py
"""Validate a built Q1Libre .deb before deployment."""
from __future__ import annotations
import io
import lzma
import tarfile
from pathlib import Path

from tools.deb import parse_ar_archive

def validate_deb(deb_path: Path) -> list[str]:
    """Validate a .deb file. Returns list of error strings (empty = valid)."""
    errors = []
    raw = deb_path.read_bytes()

    # 1. Valid ar archive
    try:
        members = parse_ar_archive(raw)
    except ValueError as e:
        return [f"Invalid ar archive: {e}"]

    member_names = [m.name for m in members]

    # 2. Required members
    if "debian-binary" not in member_names:
        errors.append("Missing debian-binary member")
    if not any("control.tar" in n for n in member_names):
        errors.append("Missing control.tar.xz member")
    if not any("data.tar" in n for n in member_names):
        errors.append("Missing data.tar.xz member")

    if errors:
        return errors

    member_map = {m.name: m for m in members}

    # 3. debian-binary version
    version = member_map["debian-binary"].data.strip()
    if version != b"2.0":
        errors.append(f"Unexpected debian-binary version: {version}")

    # 4. Control archive contents
    control_member = next(m for m in members if "control.tar" in m.name)
    try:
        with lzma.open(io.BytesIO(control_member.data)) as xz:
            with tarfile.open(fileobj=io.BytesIO(xz.read())) as tar:
                control_names = [m.name for m in tar.getmembers()]
                if "./control" not in control_names:
                    errors.append("Missing ./control in control archive")
                if "./postinst" not in control_names:
                    errors.append("Missing ./postinst in control archive")
    except Exception as e:
        errors.append(f"Failed to read control archive: {e}")

    # 5. Data archive — check for version file
    data_member = next(m for m in members if "data.tar" in m.name)
    try:
        with lzma.open(io.BytesIO(data_member.data)) as xz:
            with tarfile.open(fileobj=io.BytesIO(xz.read())) as tar:
                data_names = [m.name for m in tar.getmembers()]
                if not any("xindi/version" in n for n in data_names):
                    errors.append("Missing root/xindi/version in data archive")
    except Exception as e:
        errors.append(f"Failed to read data archive: {e}")

    # 6. File size sanity
    if len(raw) < 10_000:
        errors.append(f"Suspiciously small .deb: {len(raw)} bytes")

    return errors

def main():
    import argparse, sys
    parser = argparse.ArgumentParser(description="Validate Q1Libre firmware .deb")
    parser.add_argument("input", help="Path to .deb file to validate")
    args = parser.parse_args()

    errors = validate_deb(Path(args.input))
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("VALID: .deb passes all checks")

if __name__ == "__main__":
    main()
```

**Step 4: Run tests — verify pass**

**Step 5: Commit**

```bash
git add tools/validate.py tests/test_validate.py
git commit -m "feat: add .deb validator for pre-deployment checks"
```

---

## Task 5: Create Phase 1 Patches — Security & Moonraker Fixes

**Files:**
- Create: `q1libre/overlay/home/mks/klipper_config/moonraker.conf`
- Create: `q1libre/overlay/root/scripts/q1libre_postinst_hook.sh`
- Modify: patch `postinst` to fix chmod 777

For this task, we create the actual overlay files that will be our first release.

**Step 1: Create improved moonraker.conf**

Copy stock `moonraker.conf` from `base/`, then:
- Uncomment `[update_manager]` section
- Add Fluidd update tracking
- Keep all existing trusted_clients and cors_domains

Save to `overlay/home/mks/klipper_config/moonraker.conf`.

**Step 2: Create postinst security patch**

Create `patches/control/fix-permissions.patch` — a unified diff that:
- Changes `chmod 777 -R /home/mks/klipper_config` to `chmod 755 -R /home/mks/klipper_config && chown -R mks:mks /home/mks/klipper_config`
- Changes `chmod 777 /home/mks/klipper_config/Adaptive_Mesh.cfg` to `chmod 644`
- Removes hardcoded `resolv.conf` override (comment it out)

Since we don't have a patch applier yet, for Phase 1 we create the full replacement `postinst` in `overlay/` control area and handle it in `build.py`.

**Step 3: Create Q1Libre version marker script**

```bash
# overlay/root/scripts/q1libre_info.sh
#!/bin/bash
echo "============================="
echo " Q1Libre $(cat /root/q1libre_version.txt)"
echo " Qidi Q1 Pro Custom Firmware"
echo "============================="
echo " IP: $(hostname -I | awk '{print $1}')"
echo " Klipper: $(systemctl is-active klipper)"
echo " Moonraker: $(systemctl is-active moonraker)"
echo "============================="
```

**Step 4: Test end-to-end build**

```bash
cd E:/Projects/q1libre
python -m tools.extract stock/QD_Q1_SOC -o base
python -m tools.build --base base --overlay overlay --output dist/QD_Q1_SOC --version 0.1.0
python -m tools.validate dist/QD_Q1_SOC
```

Expected: Extract succeeds, build produces .deb, validator passes.

**Step 5: Compare output to stock**

```bash
python -m tools.extract dist/QD_Q1_SOC -o build_check
diff -rq base/data build_check/data | head -20
```

Verify only expected files changed.

**Step 6: Commit**

```bash
git add overlay/ patches/
git commit -m "feat: phase 1 patches — moonraker unlock, security fixes, version marker"
```

---

## Task 6: Create Firmware Analysis Documentation

**Files:**
- Create: `q1libre/docs/firmware-analysis.md`
- Create: `q1libre/docs/update-protocol.md`

**Step 1: Write firmware-analysis.md**

Document everything discovered during reverse engineering:
- .deb structure (ar archive, control.tar.xz, data.tar.xz)
- Complete file inventory with sizes and purposes
- Klipper modifications (28 files, categorized)
- xindi binary analysis (C++, Boost.Beast, nlohmann-json, key strings)
- TJC display protocol (BT magic header, serial communication)
- System architecture (rk3328, Armbian Buster, serial ports, services)

**Step 2: Write update-protocol.md**

Document the USB update mechanism:
- xindi monitors `/home/mks/gcode_files/sda1/QD_Update/`
- File naming: `QD_Q1_SOC`, `QD_Q1_UI`, `QD_Q1_PATCH`, `mks.deb`
- SOC install command: `dpkg -i --force-overwrite`
- UI flash: copy to `/root/800_480.tft`, serial flash to TJC
- MCU update: `hid-flash` via ttyS0
- Recovery: `mksscreen.recovery`, `mksclient.recovery`
- Backdoor: `mks-super.sh` (arbitrary script execution from USB)

**Step 3: Commit**

```bash
git add docs/
git commit -m "docs: firmware analysis and update protocol documentation"
```

---

## Task 7: Create Klipper Diff Tool (`tools/diff.py`)

**Files:**
- Create: `q1libre/tools/diff.py`
- Test: `q1libre/tests/test_diff.py`

**Step 1: Write test**

```python
# tests/test_diff.py
from pathlib import Path
from tools.diff import categorize_klipper_mods

def test_categorize_identifies_qidi_custom(tmp_path):
    # qdprobe.py doesn't exist in upstream — should be categorized as "qidi_custom"
    stock = tmp_path / "stock"
    (stock / "extras").mkdir(parents=True)
    (stock / "extras" / "qdprobe.py").write_text("# qidi probe\n")

    upstream = tmp_path / "upstream"
    (upstream / "extras").mkdir(parents=True)
    # qdprobe.py does NOT exist upstream

    result = categorize_klipper_mods(stock / "extras", upstream / "extras")
    assert "qdprobe.py" in result["qidi_custom"]
```

**Step 2: Implement `tools/diff.py`**

Tool that:
1. Takes extracted stock Klipper dir and a cloned upstream Klipper dir
2. For each modified file in stock, checks if it exists upstream
3. If not upstream: categorize as `qidi_custom`
4. If upstream: generate unified diff, estimate divergence
5. Outputs a report: `docs/klipper-diff-report.md`

**Step 3: Run against real firmware**

```bash
git clone --depth 1 https://github.com/Klipper3d/klipper.git /tmp/klipper-upstream
python -m tools.diff --stock base/data/home/mks/klipper/klippy --upstream /tmp/klipper-upstream/klippy
```

**Step 4: Commit**

```bash
git add tools/diff.py tests/test_diff.py
git commit -m "feat: add Klipper diff tool for upstream comparison"
```

---

## Task 8: End-to-End Integration Test

**Files:**
- Create: `q1libre/tests/test_integration.py`

**Step 1: Write integration test**

Tests the full pipeline: extract stock -> apply overlays -> build -> validate -> re-extract and verify changes.

```python
# tests/test_integration.py
import os
import pytest
from pathlib import Path

STOCK_FIRMWARE = Path("stock/QD_Q1_SOC")

@pytest.mark.skipif(not STOCK_FIRMWARE.exists(), reason="Stock firmware not available")
def test_full_build_pipeline(tmp_path):
    from tools.extract import extract_deb
    from tools.build import build_firmware
    from tools.validate import validate_deb

    # Extract
    base = tmp_path / "base"
    extract_deb(str(STOCK_FIRMWARE), str(base))
    assert (base / "data" / "root" / "xindi" / "version").exists()

    # Build with overlays
    output = tmp_path / "dist" / "QD_Q1_SOC"
    build_firmware(
        base_dir=base,
        overlay_dir=Path("overlay"),
        patches_dir=Path("patches"),
        output_path=output,
        q1libre_version="0.1.0-test",
    )
    assert output.exists()

    # Validate
    errors = validate_deb(output)
    assert errors == [], f"Validation failed: {errors}"

    # Re-extract and verify
    check = tmp_path / "check"
    extract_deb(str(output), str(check))

    # Version was updated
    version_text = (check / "data" / "root" / "xindi" / "version").read_text()
    assert "q1libre" in version_text

    # Q1Libre marker exists
    assert (check / "data" / "root" / "q1libre_version.txt").exists()
```

**Step 2: Run full test suite**

```bash
python -m pytest tests/ -v
```

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end integration test for full build pipeline"
```

---

## Summary

| Task | Description | Commits |
|------|-------------|---------|
| 1 | Project scaffold + git init | 1 |
| 2 | .deb parser + extractor | 1 |
| 3 | Build pipeline + overlay system | 1 |
| 4 | Validator | 1 |
| 5 | Phase 1 patches (moonraker, security, QoL) | 1 |
| 6 | RE documentation | 1 |
| 7 | Klipper diff tool | 1 |
| 8 | Integration test | 1 |

**Total: 8 tasks, ~8 commits, delivers a working Phase 1 build system.**

After this plan is complete, the community can:
1. Download a release `.deb`
2. Copy to USB stick as `QD_Update/QD_Q1_SOC`
3. Plug into Q1 Pro
4. Get unlocked Moonraker update_manager, fixed permissions, and version tracking
