"""Tests for Avahi/mDNS overlay files."""
from pathlib import Path

OVERLAY = Path(__file__).resolve().parent.parent / "overlay"


def test_avahi_service_file_exists():
    """Avahi service definition must exist in overlay."""
    svc = OVERLAY / "etc" / "avahi" / "services" / "q1libre.service"
    assert svc.exists(), "overlay/etc/avahi/services/q1libre.service must exist"


def test_avahi_service_file_valid_xml():
    """Avahi service file must be parseable XML."""
    import xml.etree.ElementTree as ET
    svc = OVERLAY / "etc" / "avahi" / "services" / "q1libre.service"
    tree = ET.parse(svc)
    root = tree.getroot()
    assert root.tag == "service-group"


def test_avahi_service_advertises_http():
    """Avahi service must advertise HTTP on port 80."""
    content = (OVERLAY / "etc" / "avahi" / "services" / "q1libre.service").read_text()
    assert "_http._tcp" in content
    assert "<port>80</port>" in content


def test_avahi_service_advertises_moonraker():
    """Avahi service must advertise Moonraker on port 7125."""
    content = (OVERLAY / "etc" / "avahi" / "services" / "q1libre.service").read_text()
    assert "_moonraker._tcp" in content
    assert "<port>7125</port>" in content


def test_postinst_enables_avahi():
    """postinst must enable avahi-daemon if available."""
    postinst = OVERLAY / "control" / "postinst"
    content = postinst.read_text(encoding="utf-8")
    assert "avahi-daemon" in content
    assert "systemctl enable avahi-daemon" in content
