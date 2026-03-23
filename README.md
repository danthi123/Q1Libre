# Q1Libre

Open firmware patches for the Qidi Q1 Pro 3D printer.

Q1Libre produces `.deb` packages compatible with the stock Qidi update mechanism.
No special hardware needed — just a USB stick.

## Quick Start

1. Place your stock `QD_Q1_SOC` firmware file in `stock/`
2. Run `python tools/extract.py stock/QD_Q1_SOC`
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
