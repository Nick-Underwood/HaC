# SearXNG Secret Key Fix — Wazuh Companion Cluster Improvement

## Problem
`deploy-searx.yml` references `secrets.SEARX_SECRET_KEY` (line 32), but the Forgejo repo
only contains `SEARXNG_SECRET_KEY`. This means:
- `${SEARX_SECRET_KEY}` expands to empty → `SECRET_KEY=$(openssl rand -hex 32)` fires
- A **new random key is generated on EVERY deploy** → all SearXNG sessions invalidated
- `settings.yml` and `settings-direct.yml` both get `__SECRET_KEY__` replaced with a fresh
  random value each time

## Scope
- `Docker-NonCritical/Tools/SearX/settings.yml:30` — `secret_key: "__SECRET_KEY__"` (template)
- `Docker-NonCritical/Tools/SearX/settings-direct.yml:25` — `secret_key: "__SECRET_KEY__"` (template)
- `.forgejo/workflows/deploy-searx.yml:32` — references `secrets.SEARX_SECRET_KEY`
- `.forgejo/workflows/deploy-searx.yml:43` — `${SEARX_SECRET_KEY:-$(openssl rand -hex 32)}`

## Fix
1. Rename the workflow secret reference: `SEARX_SECRET_KEY` → `SEARXNG_SECRET_KEY`
2. The existing `SEARXNG_SECRET_KEY` secret (live in Forgejo) will be picked up
3. Fallback `$(openssl rand -hex 32)` only fires if the secret is genuinely absent
4. The existing deployed key (`db52504c...` 64-char hex) matches what `SEARXNG_SECRET_KEY`
   should contain — verify it aligns

## Risk
- Low: the workflow already generates a key if the secret is missing; we're just pointing it
  at the right secret so the key persists across deploys instead of rotating.
- No config structure change — `settings.yml` template is untouched.

## Verification
After fix lands, deploy-searx.yml run should report the EXISTING key (not a new random one),
and `settings.yml` on disk should match the value that was already in `SEARXNG_SECRET_KEY`.
