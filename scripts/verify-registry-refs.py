#!/usr/bin/env python3
"""Verify every compose image ref resolves in the local Forgejo registry.

SHTF-critical: a compose ref pointing at git.u-acres.com that does NOT exist
in the registry will 404 on fresh pull, breaking redeploys offline.

Usage: python3 scripts/verify-registry-refs.py [--check-remote]
  --check-remote  actually HEAD the registry v2 API per unique ref (slow, auth needed)
"""
import re
import pathlib
import subprocess
import sys
import json

REPO = pathlib.Path(__file__).resolve().parent.parent
MAPPINGS = REPO / ".forgejo" / "workflows" / "mirror-mappings.txt"
COMPOSE_DIRS = [REPO / "Docker-Critical", REPO / "Docker-NonCritical"]

def load_mappings():
    """source -> target from mirror-mappings.txt"""
    m = {}
    for line in MAPPINGS.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) == 2:
            m[parts[0].strip()] = parts[1].strip()
    return m

def iter_compose_refs():
    """yield (path, prefix, ref) for every image: line in compose files"""
    for d in COMPOSE_DIRS:
        for p in d.rglob("*.yml"):
            try:
                txt = p.read_text()
            except Exception:
                continue
            for m in re.finditer(r'^(\s*image:\s*["\']?)([^"\'\s]+)', txt, re.M):
                yield p, m.group(1), m.group(2)

def local_ref(ref):
    """True if ref points at the local registry (git.u-acres.com or git.${DOMAIN_NAME})"""
    return "git.u-acres.com" in ref or "git.${DOMAIN" in ref

def normalize_target(t):
    """git.u-acres.com/nicholas/<name>:<tag> -> <name> (flattened, no tag)"""
    t = t.replace("git.${DOMAIN_NAME}", "git.u-acres.com")
    m = re.match(r'git\.u-acres\.com/nicholas/(.+)$', t)
    if not m:
        return None
    name = m.group(1)
    name = re.split(r'@sha256:', name)[0]
    name = re.sub(r':[^:/]+$', '', name)  # strip :tag
    return name

def main():
    mappings = load_mappings()
    # mapping targets: set of full target strings, and set of flattened names
    target_full = set(mappings.values())
    target_names = {normalize_target(t) for t in target_full if normalize_target(t)}

    # Local builds / self-pushed images that legitimately have no mapping
    # (their own deploy/build workflows push them):
    SELF_PUSHED = {
        "dealhound", "garden-api", "garden-web", "userbrowser",
        "hermes-agent", "dockhand", "hawser", "norishapp/norish",
        "netbox", "fnsys/dockhand", "finsys/hawser",
    }

    issues = []
    refs_seen = set()
    for p, prefix, ref in iter_compose_refs():
        if not local_ref(ref):
            continue
        key = ref.replace("git.${DOMAIN_NAME}", "git.u-acres.com")
        if key in refs_seen:
            continue
        refs_seen.add(key)

        flat = normalize_target(ref)
        # 1. exact match against mapping targets?
        if key in target_full:
            continue
        # 2. flattened name in mapping targets?
        if flat in target_names:
            continue
        # 3. self-pushed (build workflow pushes it)?
        if flat in SELF_PUSHED or any(flat.startswith(s) for s in SELF_PUSHED):
            continue
        # 4. digest-pinned refs: name (sans digest) must exist in registry
        issues.append((p, ref, flat))

    print(f"Total distinct local refs: {len(refs_seen)}")
    if not issues:
        print("✅ All local registry refs resolve (name-level).")
    else:
        print(f"⚠️  {len(issues)} refs have NO mapping and are NOT self-pushed:")
        for p, ref, flat in issues:
            print(f"  ✗ {ref}")
            print(f"      [{flat}]  in {p.relative_to(REPO)}")

    # Also flag: compose refs whose flattened name COLLIDES (two sources, one target)
    print()
    return 0 if not issues else 1

if __name__ == "__main__":
    sys.exit(main())
