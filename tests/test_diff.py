"""Tests for Klipper diff tool (tools/diff.py)."""

import tempfile
from pathlib import Path

from tools.diff import categorize_klipper_mods


def test_categorize_qidi_custom():
    """File in stock but not upstream is categorized as qidi_custom."""
    with tempfile.TemporaryDirectory() as tmpdir:
        stock = Path(tmpdir) / "stock"
        upstream = Path(tmpdir) / "upstream"

        # Create extras/qdprobe.py only in stock
        (stock / "extras").mkdir(parents=True)
        (stock / "extras" / "qdprobe.py").write_text("# Qidi probe\n")

        # Create upstream extras dir but without qdprobe.py
        (upstream / "extras").mkdir(parents=True)

        result = categorize_klipper_mods(stock, upstream)

        assert "extras/qdprobe.py" in result["qidi_custom"]
        assert "extras/qdprobe.py" not in result["modified"]
        assert "extras/qdprobe.py" not in result["identical"]


def test_categorize_modified():
    """File present in both dirs with different content is categorized as modified."""
    with tempfile.TemporaryDirectory() as tmpdir:
        stock = Path(tmpdir) / "stock"
        upstream = Path(tmpdir) / "upstream"

        stock.mkdir()
        upstream.mkdir()

        (stock / "toolhead.py").write_text("# stock version\nclass Tool: pass\n")
        (upstream / "toolhead.py").write_text("# upstream version\nclass Tool: pass\n")

        result = categorize_klipper_mods(stock, upstream)

        assert "toolhead.py" in result["modified"]
        assert "toolhead.py" not in result["qidi_custom"]
        assert "toolhead.py" not in result["identical"]


def test_categorize_identical():
    """File present in both dirs with identical content is categorized as identical."""
    with tempfile.TemporaryDirectory() as tmpdir:
        stock = Path(tmpdir) / "stock"
        upstream = Path(tmpdir) / "upstream"

        stock.mkdir()
        upstream.mkdir()

        content = "# shared module\ndef hello(): pass\n"
        (stock / "gcode.py").write_text(content)
        (upstream / "gcode.py").write_text(content)

        result = categorize_klipper_mods(stock, upstream)

        assert "gcode.py" in result["identical"]
        assert "gcode.py" not in result["modified"]
        assert "gcode.py" not in result["qidi_custom"]
