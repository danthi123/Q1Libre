# Q1Libre .bashrc for mks user
# Sourced for interactive shells

# Source system bashrc if it exists
if [ -f /etc/bash.bashrc ]; then
    . /etc/bash.bashrc
fi

# Source system profile
if [ -f /etc/profile ]; then
    . /etc/profile
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

# ── Prompt ───────────────────────────────────────────────────────────────────
PS1='\[\e[1;32m\]\u@\h\[\e[0m\]:\[\e[1;34m\]\w\[\e[0m\]\$ '

export PATH="$PATH:/home/mks/.local/bin"
