========================================================================
  Q1Libre - Open Firmware Patches for Qidi Q1 Pro
========================================================================

  Website: https://github.com/danthi123/Q1Libre


------------------------------------------------------------------------
  AVAILABLE ALIASES
------------------------------------------------------------------------

  klog          Tail Klipper log (last 50 lines, follow)
  mlog          Tail Moonraker log (last 50 lines, follow)
  krestart      Restart Klipper service
  mrestart      Restart Moonraker service
  kmrestart     Restart both Klipper and Moonraker
  q1status      Show Q1Libre system status
  cdcfg         Go to printer config directory
  myip          Show printer IP address
  diskfree      Show disk usage summary
  kversion      Show Klipper version
  mversion      Show Moonraker version
  xerr          Show recent xindi (touchscreen) log entries
  dtail         Show recent kernel messages (dmesg)
  cdlog         Go to log files directory
  cdgcode       Go to gcode files directory


------------------------------------------------------------------------
  SERVICE COMMANDS
------------------------------------------------------------------------

  sudo systemctl restart klipper.service
  sudo systemctl restart moonraker.service
  sudo systemctl status klipper.service
  sudo systemctl status moonraker.service
  sudo journalctl -u klipper -n 100 --no-pager
  sudo journalctl -u moonraker -n 100 --no-pager
  sudo reboot
  sudo shutdown -h now


------------------------------------------------------------------------
  KEY FILE LOCATIONS
------------------------------------------------------------------------

  Printer config:     ~/klipper_config/printer.cfg
  Moonraker config:   ~/klipper_config/moonraker.conf
  Klipper log:        ~/klipper_logs/klippy.log
  Moonraker log:      ~/klipper_logs/moonraker.log
  Gcode files:        ~/gcode_files/
  Fluidd web UI:      ~/fluidd/


------------------------------------------------------------------------
  WEB ACCESS
------------------------------------------------------------------------

  Fluidd UI:        http://<your-printer-ip> or http://mkspi.local
  Moonraker API:    http://<your-printer-ip>:7125


------------------------------------------------------------------------
  BACKUP
------------------------------------------------------------------------

  Full system image (from your computer, ~20 min):
    ssh root@<printer-ip> "dd if=/dev/mmcblk1 bs=4M status=progress" \
      > q1pro_backup.img

  Quick config backup (from your computer):
    scp -r root@<printer-ip>:~/klipper_config ./backup/
    scp -r root@<printer-ip>:~/gcode_files ./backup/


------------------------------------------------------------------------
  ROLLBACK TO STOCK FIRMWARE
------------------------------------------------------------------------

  1. Download official firmware from:
     https://github.com/QIDITECH/QIDI_Q1_Pro/releases

  2. Place QD_Q1_SOC file in QD_Update/ folder on FAT32 USB stick.

  3. Plug USB into printer -- stock firmware will be restored.

  4. Emergency recovery (full eMMC reflash):
     https://wiki.qidi3d.com/en/Memo/flash-emmc
     Use your q1pro_backup.img or the factory image.

========================================================================
