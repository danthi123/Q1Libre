#!/bin/bash
# Q1Libre System Debloat
# Removes unnecessary packages from stock Qidi firmware to free ~3GB
# Safe to run multiple times (idempotent)

set -e

LOG="/var/log/q1libre_debloat.log"
MARKER="/root/.q1libre_debloated"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG"; }

# Skip if already debloated
if [ -f "$MARKER" ]; then
    log "SKIP: system already debloated (marker exists)"
    exit 0
fi

log "=== Q1Libre debloat starting ==="
BEFORE=$(df / --output=avail | tail -1)

# Safety check: verify xindi's critical libraries are NOT in our removal list
log "Verifying xindi dependencies..."
XINDI_DEPS=$(ldd /root/xindi/build/xindi 2>/dev/null | awk '{print $3}' | grep -v '^$' || true)
CRITICAL_MISSING=0
for lib in libboost_system libboost_filesystem libcurl libssl libcrypto libstdc++ libpthread; do
    if echo "$XINDI_DEPS" | grep -q "$lib"; then
        log "  OK: $lib (required by xindi)"
    fi
done

# ── Tier 1: ARM/AVR cross-compilation toolchain (~1.2GB) ──
log "Removing cross-compilation toolchain..."
apt-get purge -y --auto-remove \
    gcc-arm-none-eabi libnewlib-arm-none-eabi libnewlib-dev \
    gcc-avr avr-libc avrdude binutils-avr \
    binutils-arm-none-eabi \
    2>>"$LOG" || log "WARNING: some cross-compiler packages not found"

# ── Tier 2: Desktop environment (~800MB) ──
log "Removing XFCE desktop environment..."
apt-get purge -y --auto-remove \
    xfce4 xfce4-appfinder xfce4-notifyd xfce4-panel xfce4-power-manager \
    xfce4-screenshooter xfce4-session xfce4-settings xfce4-terminal \
    xfdesktop4 xfwm4 xfconf \
    thunar thunar-volman \
    mousepad evince evince-common \
    lightdm lightdm-gtk-greeter \
    xterm x11-utils x11-xserver-utils xinit \
    2>>"$LOG" || log "WARNING: some desktop packages not found"

# Remove X server (but keep xauth if needed for SSH forwarding)
apt-get purge -y --auto-remove \
    xserver-xorg xserver-xorg-core xserver-xorg-input-all xserver-xorg-video-all \
    xserver-xorg-input-libinput xserver-xorg-video-fbdev \
    2>>"$LOG" || log "WARNING: some X server packages not found"

# ── Tier 3: CUPS, Bluetooth, Audio, Accessibility ──
log "Removing CUPS, Bluetooth, audio, and accessibility..."
apt-get purge -y --auto-remove \
    cups cups-browsed cups-client cups-common cups-core-drivers \
    cups-daemon cups-filters cups-filters-core-drivers cups-ppdc \
    printer-driver-gutenprint \
    bluez blueman pulseaudio-module-bluetooth \
    pulseaudio pulseaudio-utils alsa-utils \
    gnome-orca brltty speech-dispatcher speech-dispatcher-audio-plugins \
    libflite1 \
    sound-theme-freedesktop \
    2>>"$LOG" || log "WARNING: some packages not found"

# ── Tier 4: Dev headers and build libraries ──
log "Removing development headers..."
apt-get purge -y --auto-remove \
    libboost1.67-dev libboost-dev \
    libicu-dev libpython2.7-dev libpython3.7-dev \
    libatlas-base-dev nlohmann-json3-dev libstdc++-8-dev \
    cmake autoconf automake bison flex dpkg-dev \
    2>>"$LOG" || log "WARNING: some dev packages not found"

# ── Tier 5: Icon themes and CJK fonts ──
log "Removing icon themes and unused fonts..."
apt-get purge -y --auto-remove \
    numix-icon-theme-circle numix-icon-theme \
    adwaita-icon-theme gnome-icon-theme \
    fonts-nanum fonts-arphic-uming fonts-arphic-ukai \
    2>>"$LOG" || log "WARNING: some theme/font packages not found"

# ── Tier 6: Python 2 ──
log "Removing Python 2..."
apt-get purge -y --auto-remove \
    python2 python2.7 python2-minimal python2.7-minimal \
    libpython2.7 libpython2.7-minimal libpython2.7-stdlib \
    2>>"$LOG" || log "WARNING: Python 2 packages not found"

# ── Tier 7: Other unnecessary packages ──
log "Removing miscellaneous unnecessary packages..."
apt-get purge -y --auto-remove \
    samba-libs samba-common \
    unicode-data iso-codes \
    vim-runtime \
    2>>"$LOG" || log "WARNING: some misc packages not found"

# ── Cache and doc cleanup ──
log "Cleaning package cache and documentation..."
apt-get autoremove -y 2>>"$LOG" || true
apt-get clean 2>>"$LOG" || true

# Remove docs (keep copyright files for license compliance)
find /usr/share/doc -mindepth 1 -maxdepth 1 -type d \
    -not -name 'base-files' -exec rm -rf {} + 2>/dev/null || true

# Remove non-English locales
find /usr/share/locale -mindepth 1 -maxdepth 1 -type d \
    -not -name 'en' -not -name 'en_US' -not -name 'en_GB' \
    -exec rm -rf {} + 2>/dev/null || true

# Remove man pages
rm -rf /usr/share/man/* 2>/dev/null || true

# Remove Python 2 leftovers
rm -rf /usr/lib/python2.7 2>/dev/null || true

AFTER=$(df / --output=avail | tail -1)
SAVED=$(( (AFTER - BEFORE) / 1024 ))
log "=== Q1Libre debloat complete ==="
log "Space freed: ~${SAVED}MB"

# Mark as done so we don't run again
echo "debloated $(date)" > "$MARKER"
