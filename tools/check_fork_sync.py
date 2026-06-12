"""Guard against Klipper overlay / fork drift.

The install-time postinst runs ``git reset --hard $KLIPPER_SHA`` against the
vendored Klipper repo on the printer. That means whatever Klipper Python the
.deb ships in the overlay is **reverted to fork@KLIPPER_SHA on install** — so
if we edit a vendored Klipper file in the overlay but forget to push it to the
``danthi123/klipper`` q1-pro fork and bump ``KLIPPER_SHA``, the change silently
never reaches the printer (this bit us in v0.5.12 and again in v0.5.15).

This module enforces the invariant: every ``klippy/**/*.py`` file in the
overlay must byte-match (modulo line endings) the same file in
``fork@KLIPPER_SHA``. Any mismatch or overlay-only file means the install's
``git reset --hard`` would change or delete it on the printer — i.e. drift.

Run as part of the build (``tools.build``); raises ``ForkSyncError`` on drift.
Network failures are non-fatal by default (offline builds warn and skip).
"""

from __future__ import annotations

import io
import re
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

FORK_TARBALL = "https://github.com/danthi123/klipper/archive/{sha}.tar.gz"
_SHA_RE = re.compile(r'KLIPPER_SHA="([0-9a-f]{40})"')


class ForkSyncError(RuntimeError):
    """Raised when the Klipper overlay has drifted from fork@KLIPPER_SHA."""


def read_klipper_sha(postinst_path: Path) -> str:
    """Extract the pinned Klipper fork SHA from the postinst script."""
    text = Path(postinst_path).read_text(encoding="utf-8")
    match = _SHA_RE.search(text)
    if not match:
        raise ForkSyncError(f"KLIPPER_SHA not found in {postinst_path}")
    return match.group(1)


def _fetch_fork_tree(sha: str, timeout: float = 30.0) -> dict[str, bytes]:
    """Download fork@sha as a tarball and return {relpath: bytes}.

    Tarball members look like ``klipper-<sha>/klippy/extras/probe.py``; the
    leading ``klipper-<sha>/`` prefix is stripped so keys are repo-relative.
    """
    url = FORK_TARBALL.format(sha=sha)
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
        raw = resp.read()
    tree: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            _, _, rel = member.name.partition("/")
            if rel:
                tree[rel] = tf.extractfile(member).read()
    return tree


def _normalize(data: bytes) -> bytes:
    """Normalize line endings so a CRLF working-copy matches an LF fork blob."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def verify_klipper_fork_sync(
    overlay_dir: Path,
    postinst_path: Path,
    *,
    subtree: str = "klippy",
    offline_ok: bool = True,
) -> None:
    """Verify overlay Klipper .py files match fork@KLIPPER_SHA.

    Args:
        overlay_dir: The overlay root (contains ``home/mks/klipper``).
        postinst_path: Path to the control postinst holding ``KLIPPER_SHA``.
        subtree: Only check files under this repo-relative subtree
            (``klippy`` by default — the host Python that git reset reverts).
        offline_ok: If True, a network failure prints a warning and returns
            instead of raising (so offline builds aren't blocked).

    Raises:
        ForkSyncError: If any overlay .py differs from / is missing in the fork.
    """
    overlay_klipper = Path(overlay_dir) / "home" / "mks" / "klipper"
    if not overlay_klipper.is_dir():
        raise ForkSyncError(f"overlay Klipper dir not found: {overlay_klipper}")

    sha = read_klipper_sha(postinst_path)
    try:
        tree = _fetch_fork_tree(sha)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        message = f"WARNING: fork-sync check skipped (network error: {exc})"
        if offline_ok:
            print(message)
            return
        raise ForkSyncError(message) from exc

    prefix = f"{subtree}/"
    differs: list[str] = []
    missing: list[str] = []
    checked = 0
    for path in overlay_klipper.rglob("*.py"):
        rel = path.relative_to(overlay_klipper).as_posix()
        if not rel.startswith(prefix):
            continue
        checked += 1
        fork_bytes = tree.get(rel)
        if fork_bytes is None:
            missing.append(rel)
        elif _normalize(path.read_bytes()) != _normalize(fork_bytes):
            differs.append(rel)

    if differs or missing:
        lines = [
            f"Klipper overlay is out of sync with fork@{sha[:10]}.",
            "The install runs `git reset --hard $KLIPPER_SHA`, so these overlay",
            "files would be REVERTED or DELETED on the printer (the change never",
            "reaches it):",
            "",
        ]
        lines += [f"  DIFFERS:     {r}" for r in sorted(differs)]
        lines += [f"  NOT IN FORK: {r}" for r in sorted(missing)]
        lines += [
            "",
            "Fix: push these overlay changes to danthi123/klipper (q1-pro),",
            "then bump KLIPPER_SHA in overlay/control/postinst to the new commit.",
            "See the q1libre-klipper-patch skill for the exact workflow.",
        ]
        raise ForkSyncError("\n".join(lines))

    print(f"Fork-sync OK: {checked} {subtree}/*.py files match fork@{sha[:10]}")
