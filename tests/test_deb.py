"""Tests for ar archive parsing and building (tools/deb.py)."""

import struct
from tools.deb import ArMember, parse_ar_archive, build_ar_archive, parse_deb, build_deb


def _make_ar_archive(*members: tuple[str, bytes]) -> bytes:
    """Build a synthetic ar archive from (name, data) pairs."""
    buf = b"!<arch>\n"
    for name, data in members:
        padded_name = (name + "/").ljust(16)
        header = (
            padded_name.encode()
            + b"0           "  # timestamp (12)
            + b"0     "  # owner (6)
            + b"0     "  # group (6)
            + b"100644  "  # mode (8)
            + str(len(data)).ljust(10).encode()  # size (10)
            + b"`\n"  # magic (2)
        )
        assert len(header) == 60
        buf += header + data
        if len(data) % 2 != 0:
            buf += b"\n"
    return buf


def test_parse_ar_archive_basic():
    raw = _make_ar_archive(
        ("debian-binary", b"2.0\n"),
        ("control.tar.xz", b"\xfd7zXZ\x00fake-control"),
        ("data.tar.xz", b"\xfd7zXZ\x00fake-data"),
    )
    members = parse_ar_archive(raw)
    assert len(members) == 3
    assert members[0].name == "debian-binary"
    assert members[0].data == b"2.0\n"
    assert members[1].name == "control.tar.xz"
    assert members[2].name == "data.tar.xz"


def test_parse_ar_archive_bad_magic():
    bad = b"NOT_AR_MAGIC\n" + b"\x00" * 100
    try:
        parse_ar_archive(bad)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_roundtrip_ar_archive():
    original_members = [
        ArMember(name="fileA", timestamp=1000, owner_id=0, group_id=0,
                 mode=0o100644, data=b"hello"),
        ArMember(name="fileB", timestamp=2000, owner_id=0, group_id=0,
                 mode=0o100644, data=b"world!"),  # even length
        ArMember(name="fileC", timestamp=3000, owner_id=0, group_id=0,
                 mode=0o100644, data=b"odd"),  # odd length, needs padding
    ]
    built = build_ar_archive(original_members)
    parsed = parse_ar_archive(built)

    assert len(parsed) == len(original_members)
    for orig, got in zip(original_members, parsed):
        assert orig.name == got.name
        assert orig.data == got.data
        assert orig.timestamp == got.timestamp
        assert orig.mode == got.mode

    # Rebuild from parsed and check byte-identical
    rebuilt = build_ar_archive(parsed)
    assert built == rebuilt


def test_parse_deb():
    raw = _make_ar_archive(
        ("debian-binary", b"2.0\n"),
        ("control.tar.xz", b"ctrl-data"),
        ("data.tar.xz", b"data-data"),
    )
    d = parse_deb(raw)
    assert "debian-binary" in d
    assert "control.tar.xz" in d
    assert "data.tar.xz" in d
    assert d["debian-binary"].data == b"2.0\n"


def test_build_deb():
    deb_bytes = build_deb(b"2.0\n", b"ctrl", b"data", timestamp=12345)
    members = parse_ar_archive(deb_bytes)
    assert len(members) == 3
    assert members[0].name == "debian-binary"
    assert members[0].data == b"2.0\n"
    assert members[1].name == "control.tar.xz"
    assert members[1].data == b"ctrl"
    assert members[2].name == "data.tar.xz"
    assert members[2].data == b"data"
    # All timestamps should match
    for m in members:
        assert m.timestamp == 12345
