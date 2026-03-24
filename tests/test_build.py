"""Tests for version handling and firmware build pipeline."""

import io
import lzma
import tarfile
import tempfile
from pathlib import Path

from tools.version import read_version, write_version
from tools.build import build_firmware
from tools.deb import parse_ar_archive


def test_read_write_version():
    """Create a version file, read it, update soc, verify preservation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vfile = Path(tmpdir) / "version"
        vfile.write_text(
            "[version]\n"
            "mcu             = V0.10.0\n"
            "ui              = V4.4.24\n"
            "soc             = V4.4.24\n"
        )

        info = read_version(vfile)
        assert info["mcu"] == "V0.10.0"
        assert info["ui"] == "V4.4.24"
        assert info["soc"] == "V4.4.24"

        write_version(vfile, soc="V4.4.24-q1libre0.1.0")

        info2 = read_version(vfile)
        assert info2["soc"] == "V4.4.24-q1libre0.1.0"
        assert info2["mcu"] == "V0.10.0"
        assert info2["ui"] == "V4.4.24"


def test_build_produces_valid_deb():
    """Build from a fake base/ directory with overlay, verify output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        base = tmp / "base"
        overlay = tmp / "overlay"
        output = tmp / "dist" / "QD_Q1_SOC"

        # --- Create fake base directory ---
        # control files
        ctrl = base / "control"
        ctrl.mkdir(parents=True)
        (ctrl / "control").write_text("Package: qd-q1-soc\nVersion: 4.4.24\n")
        (ctrl / "postinst").write_text("#!/bin/sh\nexit 0\n")
        (ctrl / "preinst").write_text("#!/bin/sh\nexit 0\n")
        (ctrl / "postrm").write_text("#!/bin/sh\nexit 0\n")

        # data files
        data = base / "data"
        version_dir = data / "root" / "xindi"
        version_dir.mkdir(parents=True)
        (version_dir / "version").write_text(
            "[version]\n"
            "mcu             = V0.10.0\n"
            "ui              = V4.4.24\n"
            "soc             = V4.4.24\n"
        )

        moonraker_dir = data / "home" / "mks" / "klipper_config"
        moonraker_dir.mkdir(parents=True)
        (moonraker_dir / "moonraker.conf").write_text("# stock moonraker config\n")

        # debian-binary
        (base / "debian-binary").write_text("2.0\n")

        # --- Create overlay ---
        overlay_moonraker = overlay / "home" / "mks" / "klipper_config"
        overlay_moonraker.mkdir(parents=True)
        (overlay_moonraker / "moonraker.conf").write_text(
            "# q1libre patched moonraker config\n"
        )

        # --- Build ---
        patches = tmp / "patches"
        patches.mkdir()

        build_firmware(
            base_dir=base,
            overlay_dir=overlay,
            patches_dir=patches,
            output_path=output,
            q1libre_version="0.1.0",
        )

        # --- Verify output ---
        assert output.exists()
        assert output.stat().st_size > 0

        # Parse the ar archive
        raw = output.read_bytes()
        members = parse_ar_archive(raw)
        names = [m.name for m in members]
        assert "debian-binary" in names
        assert "control.tar.xz" in names
        assert "data.tar.xz" in names

        # Extract data.tar.xz and check overlay was applied
        data_member = next(m for m in members if m.name == "data.tar.xz")
        data_bytes = lzma.decompress(data_member.data)
        with tarfile.open(fileobj=io.BytesIO(data_bytes), mode="r") as tf:
            member_names = tf.getnames()

            # Check overlayed moonraker.conf
            moonraker_path = "./home/mks/klipper_config/moonraker.conf"
            assert moonraker_path in member_names
            f = tf.extractfile(moonraker_path)
            assert f is not None
            content = f.read().decode()
            assert "q1libre patched" in content

            # Check version file has q1libre marker
            version_path = "./root/xindi/version"
            assert version_path in member_names
            f = tf.extractfile(version_path)
            assert f is not None
            version_content = f.read().decode()
            assert "q1libre" in version_content

            # Check q1libre_version.txt marker exists
            marker_path = "./root/q1libre_version.txt"
            assert marker_path in member_names


def test_control_overlay_applied():
    """Files in overlay/control/ must override base/control/ files in built deb."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        base = tmp / "base"
        overlay = tmp / "overlay"
        output = tmp / "dist" / "QD_Q1_SOC"

        # Minimal base
        ctrl = base / "control"
        ctrl.mkdir(parents=True)
        (ctrl / "control").write_text("Package: qd-q1-soc\nVersion: 4.4.24\n")
        (ctrl / "postinst").write_text("#!/bin/sh\n# STOCK postinst\nexit 0\n")

        data = base / "data"
        version_dir = data / "root" / "xindi"
        version_dir.mkdir(parents=True)
        (version_dir / "version").write_text(
            "[version]\nmcu = V0.10.0\nui = V4.4.24\nsoc = V4.4.24\n"
        )
        (base / "debian-binary").write_text("2.0\n")

        # Control overlay — patched postinst
        ctrl_overlay = overlay / "control"
        ctrl_overlay.mkdir(parents=True)
        (ctrl_overlay / "postinst").write_text("#!/bin/sh\n# Q1LIBRE patched postinst\nexit 0\n")

        output.parent.mkdir(parents=True)
        build_firmware(base, overlay, tmp / "patches", output, q1libre_version="0.1.0")

        assert output.exists()

        # Extract and inspect the built deb's postinst
        from tools.deb import parse_deb
        parts = parse_deb(output.read_bytes())
        with lzma.open(io.BytesIO(parts["control.tar.xz"].data)) as lz:
            with tarfile.open(fileobj=io.BytesIO(lz.read())) as tf:
                postinst_member = tf.getmember("./postinst")
                content = tf.extractfile(postinst_member).read().decode()
        assert "Q1LIBRE patched postinst" in content
        assert "STOCK postinst" not in content


def test_control_overlay_not_in_data():
    """Files in overlay/control/ must NOT appear in the data.tar.xz of the built deb."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        base = tmp / "base"
        overlay = tmp / "overlay"
        output = tmp / "dist" / "QD_Q1_SOC"

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

        (overlay / "control").mkdir(parents=True)
        (overlay / "control" / "postinst").write_text("#!/bin/sh\n# PATCHED\nexit 0\n")

        output.parent.mkdir(parents=True)
        build_firmware(base, overlay, tmp / "patches", output, q1libre_version="0.1.0")

        from tools.deb import parse_deb
        parts = parse_deb(output.read_bytes())
        with lzma.open(io.BytesIO(parts["data.tar.xz"].data)) as lz:
            with tarfile.open(fileobj=io.BytesIO(lz.read())) as tf:
                names = tf.getnames()

        assert not any("control/postinst" in n for n in names), \
            f"control/postinst must not appear in data.tar.xz, but found in: {names}"


def test_control_overlay_empty_dir_does_not_pollute_data():
    """An empty overlay/control/ dir must not affect data.tar.xz or cause errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        base = tmp / "base"
        overlay = tmp / "overlay"
        output = tmp / "dist" / "QD_Q1_SOC"

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

        # Empty overlay/control/ directory — no files
        (overlay / "control").mkdir(parents=True)

        # One data overlay file
        data_overlay = overlay / "home" / "mks"
        data_overlay.mkdir(parents=True)
        (data_overlay / "test.txt").write_text("hello\n")

        output.parent.mkdir(parents=True)
        build_firmware(base, overlay, tmp / "patches", output, q1libre_version="0.1.0")

        from tools.deb import parse_deb
        parts = parse_deb(output.read_bytes())

        # data.tar.xz must contain the data overlay file
        with lzma.open(io.BytesIO(parts["data.tar.xz"].data)) as lz:
            with tarfile.open(fileobj=io.BytesIO(lz.read())) as tf:
                names = tf.getnames()

        assert any("test.txt" in n for n in names), "data overlay file missing"
        assert not any("control" in n for n in names), \
            f"control directory must not appear in data.tar.xz, got: {names}"

        # postinst must still be the STOCK one (nothing in overlay/control/)
        with lzma.open(io.BytesIO(parts["control.tar.xz"].data)) as lz:
            with tarfile.open(fileobj=io.BytesIO(lz.read())) as tf:
                postinst = tf.extractfile("./postinst").read().decode()
        assert "STOCK" in postinst


def test_moonraker_has_mainsail_update_manager():
    """overlay moonraker.conf must include an [update_manager mainsail] section."""
    moonraker = Path(__file__).resolve().parent.parent / "overlay" / "home" / "mks" / "klipper_config" / "moonraker.conf"
    assert moonraker.exists()
    content = moonraker.read_text()
    assert "[update_manager mainsail]" in content
    assert "mainsail-crew/mainsail" in content


def test_patched_postinst_content():
    """The real overlay/control/postinst must not contain chmod 777, resolv.conf override, or IPv6 disable."""
    postinst = Path(__file__).resolve().parent.parent / "overlay" / "control" / "postinst"
    assert postinst.exists(), "overlay/control/postinst must exist"
    content = postinst.read_text(encoding="utf-8")
    assert "chmod 777" not in content, "chmod 777 must be removed"
    assert "resolv.conf" not in content, "hardcoded DNS override must be removed"
    assert "sysctl.conf" not in content, "IPv6 disable must be removed"
    assert "chmod 755" in content or "chmod 644" in content, "proper permissions must be set"
    assert "chmod 0440 /etc/sudoers.d/q1libre" in content, "sudoers perm guard must be present"
    assert "q1libre_version.txt" in content, "Q1Libre version marker logging must be present"


def test_mks_bashrc_has_aliases():
    """overlay .bashrc must define klog, mlog, and krestart aliases."""
    bashrc = Path(__file__).resolve().parent.parent / "overlay" / "home" / "mks" / ".bashrc"
    assert bashrc.exists(), "overlay/home/mks/.bashrc must exist"
    content = bashrc.read_text()
    assert "alias klog=" in content
    assert "alias mlog=" in content
    assert "alias krestart=" in content
    assert "klippy.log" in content
    assert "moonraker.log" in content


def test_sudoers_override_exists():
    """overlay sudoers.d/q1libre must allow klipper/moonraker restarts without blanket sudo."""
    sudoers = Path(__file__).resolve().parent.parent / "overlay" / "etc" / "sudoers.d" / "q1libre"
    assert sudoers.exists(), "overlay/etc/sudoers.d/q1libre must exist"
    content = sudoers.read_text()
    assert "klipper.service" in content
    assert "moonraker.service" in content
    assert "NOPASSWD" in content
    # Must NOT grant blanket sudo
    assert "ALL=(ALL) ALL" not in content


def test_phase2b_version_string():
    """Default build version must reflect Phase 2B."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "build", Path(__file__).parent.parent / "tools" / "build.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "DEFAULT_VERSION"), "build.py must have DEFAULT_VERSION constant"
    assert "0.2.1" in mod.DEFAULT_VERSION, f"Expected 0.2.1 in version, got: {mod.DEFAULT_VERSION!r}"
