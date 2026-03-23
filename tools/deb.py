"""Pure-Python ar archive parser and .deb builder.

Handles the ar(5) archive format used by Debian packages without
requiring dpkg or any platform-specific binaries.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

AR_MAGIC = b"!<arch>\n"
HEADER_SIZE = 60


@dataclass
class ArMember:
    """A single member within an ar archive."""

    name: str
    timestamp: int
    owner_id: int
    group_id: int
    mode: int
    data: bytes


def parse_ar_archive(raw: bytes) -> list[ArMember]:
    """Parse an ar archive and return its members.

    Args:
        raw: Raw bytes of the ar archive.

    Returns:
        List of ArMember entries in archive order.

    Raises:
        ValueError: If the archive magic is invalid or the archive is
            malformed.
    """
    if not raw.startswith(AR_MAGIC):
        raise ValueError(
            f"Not an ar archive: bad magic "
            f"(got {raw[:8]!r}, expected {AR_MAGIC!r})"
        )

    members: list[ArMember] = []
    offset = len(AR_MAGIC)

    while offset < len(raw):
        if offset + HEADER_SIZE > len(raw):
            raise ValueError(
                f"Truncated ar header at offset {offset} "
                f"(need {HEADER_SIZE} bytes, have {len(raw) - offset})"
            )

        header = raw[offset : offset + HEADER_SIZE]

        # Parse the 60-byte ar header fields
        name_raw = header[0:16].decode("ascii").strip()
        timestamp = int(header[16:28].strip())
        owner_id = int(header[28:34].strip())
        group_id = int(header[34:40].strip())
        mode = int(header[40:48].strip(), 8)
        size = int(header[48:58].strip())
        magic = header[58:60]

        if magic != b"`\n":
            raise ValueError(
                f"Bad ar member header magic at offset {offset}: {magic!r}"
            )

        # Strip trailing '/' from name (ar convention)
        name = name_raw.rstrip("/")

        data_start = offset + HEADER_SIZE
        data_end = data_start + size
        if data_end > len(raw):
            raise ValueError(
                f"Truncated ar member {name!r}: need {size} bytes at "
                f"offset {data_start}, but archive is only {len(raw)} bytes"
            )

        data = raw[data_start:data_end]

        members.append(
            ArMember(
                name=name,
                timestamp=timestamp,
                owner_id=owner_id,
                group_id=group_id,
                mode=mode,
                data=data,
            )
        )

        # Advance past data + optional padding byte for even alignment
        offset = data_end
        if offset % 2 != 0:
            offset += 1

    return members


def build_ar_archive(members: list[ArMember]) -> bytes:
    """Build an ar archive from a list of members.

    Args:
        members: List of ArMember entries to pack.

    Returns:
        Raw bytes of the ar archive.
    """
    buf = bytearray(AR_MAGIC)

    for member in members:
        name_field = (member.name + "/").ljust(16)
        header = (
            name_field.encode("ascii")
            + str(member.timestamp).ljust(12).encode("ascii")
            + str(member.owner_id).ljust(6).encode("ascii")
            + str(member.group_id).ljust(6).encode("ascii")
            + format(member.mode, "o").ljust(8).encode("ascii")
            + str(len(member.data)).ljust(10).encode("ascii")
            + b"`\n"
        )
        assert len(header) == HEADER_SIZE, f"Header is {len(header)} bytes"

        buf += header
        buf += member.data

        # Pad to even byte boundary
        if len(member.data) % 2 != 0:
            buf += b"\n"

    return bytes(buf)


def parse_deb(raw: bytes) -> dict[str, ArMember]:
    """Parse a .deb file and return members keyed by name.

    Args:
        raw: Raw bytes of the .deb package.

    Returns:
        Dict mapping member names to ArMember instances.
    """
    members = parse_ar_archive(raw)
    return {m.name: m for m in members}


def build_deb(
    debian_binary: bytes,
    control_tar: bytes,
    data_tar: bytes,
    timestamp: int | None = None,
) -> bytes:
    """Build a .deb package from its three components.

    Args:
        debian_binary: Contents of the debian-binary member (e.g. b"2.0\\n").
        control_tar: Raw bytes of control.tar.xz.
        data_tar: Raw bytes of data.tar.xz.
        timestamp: Unix timestamp for all members. Defaults to current time.

    Returns:
        Raw bytes of the .deb package.
    """
    ts = timestamp if timestamp is not None else int(time.time())

    members = [
        ArMember(
            name="debian-binary",
            timestamp=ts,
            owner_id=0,
            group_id=0,
            mode=0o100644,
            data=debian_binary,
        ),
        ArMember(
            name="control.tar.xz",
            timestamp=ts,
            owner_id=0,
            group_id=0,
            mode=0o100644,
            data=control_tar,
        ),
        ArMember(
            name="data.tar.xz",
            timestamp=ts,
            owner_id=0,
            group_id=0,
            mode=0o100644,
            data=data_tar,
        ),
    ]
    return build_ar_archive(members)
