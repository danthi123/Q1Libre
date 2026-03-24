---
name: q1libre-klipper-patch
description: Patch the Klipper fork (danthi123/klipper q1-pro branch) and update the vendored copy in Q1Libre. Use this skill whenever fixing a Klipper bug, applying a Klipper patch, modifying Klipper source code, or when the user mentions "klipper fix", "klipper patch", "klipper bug", "probe fix", "virtual_sdcard fix", or any change to Klipper Python files. The fork lives at github.com/danthi123/klipper on the q1-pro branch.
---

# Klipper Fork Patch Workflow

The Q1Libre project maintains a managed Klipper fork at `danthi123/klipper` (branch: `q1-pro`). This fork is upstream Klipper v0.13 + Qidi's hardware patches (30 modified files for Q1 Pro support). When we find bugs (usually Python 2→3 incompatibilities in Qidi's code), we fix them in the fork and then vendor the fixed files into the Q1Libre overlay.

## The Patch Sequence

### 1. Identify and test the fix

If possible, test the fix live on the printer first via SSH:
```bash
ssh root@192.168.0.248 "sed -i 's/old/new/' /home/mks/klipper/klippy/extras/<file>.py"
ssh root@192.168.0.248 "systemctl restart klipper"
```

Verify the fix works before committing to the fork.

### 2. Clone and patch the fork

```bash
cd /tmp && rm -rf klipper-fix
git clone --branch q1-pro --depth 20 https://github.com/danthi123/klipper.git klipper-fix
```

Apply the fix to the cloned repo. Verify with `git diff`.

### 3. Commit and push to the fork

```bash
cd /tmp/klipper-fix
git add <changed files>
git commit -m "fix: <description>

<explanation of root cause and fix>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
git push origin q1-pro
```

Note the new commit SHA from `git log --oneline -1`.

### 4. Update the vendored copy in Q1Libre

Copy the fixed file(s) into the overlay:
```bash
cp /tmp/klipper-fix/klippy/extras/<file>.py \
   E:/Projects/q1libre/overlay/home/mks/klipper/klippy/extras/<file>.py
```

### 5. Update the Klipper SHA in postinst

The postinst script uses a hardcoded SHA for `git reset --hard` during installation. Update it:

```bash
grep -n 'KLIPPER_SHA=' E:/Projects/q1libre/overlay/control/postinst
```

Replace the old SHA with the new commit SHA from step 3.

### 6. Build and release

Use the `q1libre-release` skill to build, test, and release.

## Important Context

- **MCU firmware stays at v0.10** — we only patch the host-side Python code, never the MCU firmware
- **Python 3.7 compatibility** — the printer runs Python 3.7.3 on Debian Buster. No f-strings in Klipper code (it uses `%` formatting), no walrus operator, no `typing` features from 3.8+
- **Qidi's modifications** — 30 files were modified by Qidi. Common issues: `buffering=0` (Python 2 only), `reload(sys)` calls, `print` statements instead of functions
- **The fork remote** — `origin` points to `https://github.com/danthi123/klipper.git`, branch is `q1-pro`
