#!/usr/bin/env python3
"""Add registry-login step to every deploy workflow that lacks it.

The SHTF mirror moved all images into the private git.u-acres.com registry,
so every deploy must `docker login` before pulling. Only 5/58 workflows had
the step; the rest fail with `unauthorized` on registry pulls (as outline did).

Idempotent: skips workflows that already have a login step.
"""
import pathlib
import re

REPO = pathlib.Path("C:/Dev/HaC")
WORKFLOWS = sorted((REPO / ".forgejo" / "workflows").glob("deploy-*.yml"))

LOGIN_STEP = """      - name: Authenticate to local registry
        env:
          FORGEJO_TOKEN: ${{ secrets.FORGEJO_TOKEN }}
        run: |
          echo "$FORGEJO_TOKEN" | docker login git.u-acres.com -u nicholas --password-stdin
"""

patched = []
skipped = []
errors = []

for wf in WORKFLOWS:
    txt = wf.read_text()
    if "docker login" in txt:
        skipped.append(wf.name)
        continue

    # Insert after the Checkout step block. Anchor: the checkout step ends at the
    # first blank line + next "- name:" line after "uses: actions/checkout".
    m = re.search(
        r"(?ms)(^      - name: Checkout repository\n(?:.*\n)*?        uses: actions/checkout@v4\n)(.*?)(\n      - name:|\Z)",
        txt,
    )
    if not m:
        # No checkout step — insert after the first step (or at start of steps)
        m2 = re.search(r"(?ms)(^    steps:\n)", txt)
        if m2:
            insert_at = m2.end()
            txt = txt[:insert_at] + "\n" + LOGIN_STEP + txt[insert_at:]
            patched.append((wf.name, "after-steps-header"))
        else:
            errors.append((wf.name, "no-steps-anchor"))
            continue
    else:
        # Insert between checkout block and the next step
        anchor_end = m.end(1)
        # Find the blank line after checkout (end of checkout block)
        nl = txt.find("\n\n", anchor_end)
        if nl == -1:
            errors.append((wf.name, "no-blank-after-checkout"))
            continue
        txt = txt[: nl + 2] + LOGIN_STEP + txt[nl + 2 :]
        patched.append((wf.name, "after-checkout"))

    wf.write_text(txt)

print(f"Patched: {len(patched)}")
for name, where in patched:
    print(f"  ✓ {name} ({where})")
print(f"Skipped (already had login): {len(skipped)}")
for name in skipped:
    print(f"  - {name}")
if errors:
    print(f"ERRORS: {len(errors)}")
    for name, why in errors:
        print(f"  ✗ {name}: {why}")
