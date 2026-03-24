---
name: q1libre-release
description: Build, test, commit, push, and create a GitHub release for Q1Libre firmware. Use this skill whenever the user says "release", "build and release", "new version", "cut a release", "ship it", "publish", or asks to create a new firmware build for distribution. Also use when bumping versions or updating the GitHub release.
---

# Q1Libre Release Pipeline

This skill automates the full release cycle for Q1Libre firmware. Every step must happen in order — skipping steps leads to broken releases (we've learned this the hard way with CRLF issues, version mismatches, and missing wheel bundles).

## The Release Sequence

### 1. Determine the new version

Read `DEFAULT_VERSION` from `tools/build.py`. Bump according to what changed:
- **Patch** (0.5.x → 0.5.y): bug fixes, minor tweaks
- **Minor** (0.x.0 → 0.y.0): new features, dependency upgrades
- **Major** (x.0.0 → y.0.0): breaking changes (unlikely given our overlay approach)

### 2. Update version references

Three files need the version string updated:
1. `tools/build.py` — `DEFAULT_VERSION = "x.y.z"`
2. `tests/test_build.py` — the `test_phase2b_version_string` assertion
3. Commit message

Search for the old version string in both files to find the exact lines.

### 3. Build the .deb

```bash
cd E:/Projects/q1libre
python -m tools.build --version <NEW_VERSION>
```

Output goes to `dist/q1libre-v<VERSION>.deb`. Verify the file exists and is reasonable size (should be ~67-70MB with all wheels bundled).

### 4. Run tests

```bash
cd E:/Projects/q1libre
python -m pytest tests/ -q
```

All tests must pass. The version string test will fail if step 2 was missed. Fix and re-run — do NOT skip failing tests.

### 5. Commit and push

Stage only the relevant files (never `git add .`):
```bash
git add tools/build.py tests/test_build.py overlay/... <any other changed files>
```

Commit message format:
```
<type>: v<VERSION> — <one-line summary>

<optional body explaining what changed>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Push to `origin main`.

### 6. Create GitHub release

Delete the previous release first (we maintain a single latest release):
```bash
gh release delete v<PREV_VERSION> --yes
```

Create the new release with the .deb attached:
```bash
gh release create v<VERSION> dist/q1libre-v<VERSION>.deb \
  --title "Q1Libre v<VERSION>" \
  --notes "$(cat <<'EOF'
## Q1Libre v<VERSION>
... release notes ...
EOF
)"
```

Release notes should include:
- Changes since last version (bullet points)
- Full feature list (can be abbreviated)
- Install instructions (download → USB → plug in)
- Rollback link to Qidi stock firmware
- Link to install guide and roadmap

### Common Pitfalls

- **Forgetting to update the version test** — causes 1 test failure every time
- **CRLF in control scripts** — build.py strips CRLF from known text extensions + control scripts (postinst, etc.)
- **Sudoers permissions** — the postinst must chmod 0440 sudoers files before any sudo calls
- **Klipper SHA mismatch** — if klipper fork was updated, the SHA in postinst must match
