#!/bin/bash
# Q1Libre info script — shows system status
echo "============================="
echo " Q1Libre $(cat /root/q1libre_version.txt 2>/dev/null || echo 'unknown')"
echo " Qidi Q1 Pro Custom Firmware"
echo "============================="
echo " IP: $(hostname -I 2>/dev/null | awk '{print $1}')"
echo " Klipper: $(systemctl is-active klipper 2>/dev/null)"
echo " Moonraker: $(systemctl is-active moonraker 2>/dev/null)"
echo "============================="
