# tests/test_vendor_moonraker.py
import ast
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent

def test_vendor_tool_exists():
    """vendor_moonraker.py must exist."""
    assert (PROJECT_ROOT / "tools" / "vendor_moonraker.py").exists()

def test_pinned_sha_constant():
    """PINNED_SHA must be a 40-char hex string."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "vendor_moonraker",
        PROJECT_ROOT / "tools" / "vendor_moonraker.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sha = mod.PINNED_SHA
    assert isinstance(sha, str)
    assert len(sha) == 40, f"SHA must be 40 chars, got {len(sha)}: {sha!r}"
    assert all(c in "0123456789abcdef" for c in sha.lower()), f"SHA must be hex: {sha!r}"

def test_vendored_tree_has_expected_structure():
    """Vendored moonraker must have moonraker/ and scripts/ subdirectories."""
    moonraker_dir = PROJECT_ROOT / "overlay" / "home" / "mks" / "moonraker"
    if not moonraker_dir.exists():
        pytest.skip("Vendored tree not yet present — run vendor_moonraker.py first")
    assert (moonraker_dir / "moonraker").is_dir(), "Missing moonraker/ subdir"
    assert (moonraker_dir / "scripts").is_dir(), "Missing scripts/ subdir"
    assert (moonraker_dir / "moonraker" / "moonraker.py").exists(), "Missing moonraker.py"

def test_no_dot_git_in_vendored_tree():
    """Vendored tree must not contain .git directory."""
    moonraker_dir = PROJECT_ROOT / "overlay" / "home" / "mks" / "moonraker"
    if not moonraker_dir.exists():
        pytest.skip("Vendored tree not yet present")
    assert not (moonraker_dir / ".git").exists(), ".git must be stripped from vendored tree"

def test_vendored_moonraker_newer_than_stock():
    """Vendored moonraker must be newer than the stock July 2022 commit (bdd0222)."""
    moonraker_dir = PROJECT_ROOT / "overlay" / "home" / "mks" / "moonraker"
    if not moonraker_dir.exists():
        pytest.skip("Vendored tree not yet present")
    # The stock Moonraker (bdd0222, July 2022) did not have update_manager as a
    # standalone component with its own directory. Newer versions do.
    # Check that update_manager exists as a standalone component directory.
    um_dir = moonraker_dir / "moonraker" / "components" / "update_manager"
    assert um_dir.is_dir(), "Newer moonraker must have components/update_manager/ directory"
    # Also verify a main entry-point python file exists (app.py in old, server.py in new)
    entry_points = list((moonraker_dir / "moonraker").glob("*.py"))
    assert len(entry_points) > 0, "moonraker/ subdir must contain Python entry-point files"

def test_vendored_moonraker_has_requirements():
    """Vendored moonraker must have a requirements file for pip install."""
    moonraker_dir = PROJECT_ROOT / "overlay" / "home" / "mks" / "moonraker"
    if not moonraker_dir.exists():
        pytest.skip("Vendored tree not yet present")
    req_files = list((moonraker_dir / "scripts").glob("*requirements*.txt"))
    assert len(req_files) > 0, "scripts/ must contain at least one requirements*.txt"
