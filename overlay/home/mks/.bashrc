# Q1Libre .bashrc for mks user
# Sourced for interactive shells

# Source system bashrc if it exists
if [ -f /etc/bash.bashrc ]; then
    . /etc/bash.bashrc
fi

# ── Q1Libre aliases ──────────────────────────────────────────────────────────

# Tail the Klipper log (last 50 lines, follow)
alias klog='tail -n 50 -f ~/klipper_logs/klippy.log'

# Tail the Moonraker log (last 50 lines, follow)
alias mlog='tail -n 50 -f ~/klipper_logs/moonraker.log'

# Restart Klipper service
alias krestart='sudo systemctl restart klipper.service && echo "Klipper restarted"'

# Restart Moonraker service
alias mrestart='sudo systemctl restart moonraker.service && echo "Moonraker restarted"'

# Restart both Klipper and Moonraker
alias kmrestart='sudo systemctl restart klipper.service moonraker.service && echo "Klipper + Moonraker restarted"'

# Show Q1Libre status
alias q1status='/root/scripts/q1libre_info.sh'

# Show printer config directory
alias cdcfg='cd ~/klipper_config && ls'

# ── Network & System ────────────────────────────────────────────────────────
# Show printer IP address
alias myip='hostname -I | awk "{print \$1}"'

# Show disk usage summary
alias diskfree='df -h / /home | tail -n +2'

# ── Versions ────────────────────────────────────────────────────────────────
# Show Klipper version
alias kversion='cd ~/klipper && git describe --tags --always 2>/dev/null; cd ~'

# Show Moonraker version
alias mversion='cd ~/moonraker && git describe --tags --always 2>/dev/null; cd ~'

# ── Additional Logs ─────────────────────────────────────────────────────────
# Tail xindi errors
alias xerr='sudo journalctl -u xindi -n 50 --no-pager'

# Last 30 dmesg lines
alias dtail='dmesg | tail -30'

# ── Navigation ──────────────────────────────────────────────────────────────
# Go to klipper logs directory
alias cdlog='cd ~/klipper_logs && ls'

# Go to gcode files directory
alias cdgcode='cd ~/gcode_files && ls'

# ── Prompt ───────────────────────────────────────────────────────────────────
PS1='\[\e[1;32m\]\u@\h\[\e[0m\]:\[\e[1;34m\]\w\[\e[0m\]\$ '

export PATH="$PATH:/home/mks/.local/bin"
