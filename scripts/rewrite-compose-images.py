#!/usr/bin/env python3
"""
Rewrite all HaC compose file `image:` fields so third-party images point at
the local Forgejo registry (git.u-acres.com/nicholas/...) instead of upstream
registries (Docker Hub, ghcr.io, gcr.io, lscr.io, etc.).

Images that are already local (git.u-acres.com/nicholas/*, git.${DOMAIN_NAME}/
nicholas/*) or are local builds (no registry prefix, or build: context) are
left untouched.

Usage:
  python rewrite-compose-images.py [--dry-run] [--registry git.u-acres.com]
"""

import argparse
import re
import sys
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent  # C:\Dev\HaC

# Compose files to skip (not image-based, or managed elsewhere)
SKIP_DIRS = {
    "provisioning",
    ".git",
    "dashboard-config",
    "indexer-config",
    "manager-config",
}

# Files that MUST NEVER be rewritten: the Forgejo registry host is the
# bootstrap pair — if its own compose points at the self-hosted registry,
# the registry can never start (chicken-and-egg, see commit 9680d2c).
SKIP_FILES = frozenset({
    "Docker-Critical/Management/Git - Forgejo/git.yml",
})

# Images that are ALREADY mirrored or self-maintained — skip rewriting
ALREADY_LOCAL = frozenset({
    "git.u-acres.com/nicholas/hermes-agent:main",
    "git.u-acres.com/nicholas/dockhand-ha-app:latest",
    "git.u-acres.com/nicholas/dockhand-ha-app:1.0.37",
    "git.u-acres.com/nicholas/dockhand-ha-app:1.0.38",
})


# ── Helpers ────────────────────────────────────────────────────────────────

def is_local_image(image: str, registry: str, namespace: str) -> bool:
    """Return True if the image is already local (already on Forgejo or a
    local build with no registry prefix)."""
    if image in ALREADY_LOCAL:
        return True
    # Already points at our Forgejo registry
    if image.startswith(f"{registry}/{namespace}/"):
        return True
    # git.${DOMAIN_NAME}/nicholas/* — variable-based local reference
    if image.startswith("git.") and "/nicholas/" in image:
        return True
    # No registry prefix at all — likely a local build or unqualified official
    # image. NOT "already local" — needs mirroring.
    return False


def extract_registry_and_repo(image: str) -> tuple[str | None, str]:
    """Split image into (registry, repo_and_tag).

    Returns (None, image) if no registry prefix is found.
    """
    m = re.match(r'^([a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}/)?(.+)$', image)
    if not m:
        return (None, image)
    registry = m.group(1)
    if registry:
        registry = registry.rstrip('/')
    return (registry, m.group(2))


def image_name_without_registry(image: str) -> str:
    """Strip the registry prefix, leaving just the repo:tag part."""
    _, repo_and_tag = extract_registry_and_repo(image)
    return repo_and_tag


def make_forgejo_target(image: str, registry: str, namespace: str) -> str:
    """Compute the Forgejo mirror target for a given upstream image.

    Drops 'library/' prefix for Docker Hub official images.
    Preserves namespace path for images with one (e.g. linuxserver/sonarr).
    """
    if is_local_image(image, registry, namespace):
        return image  # already local, no change

    repo_and_tag = image_name_without_registry(image)

    # Drop 'library/' prefix for Docker Hub official images
    if repo_and_tag.startswith("library/"):
        repo_and_tag = repo_and_tag[len("library/"):]

    return f"{registry}/{namespace}/{repo_and_tag}"


def rewrite_image_line(line: str, registry: str, namespace: str) -> str:
    """Rewrite a single compose file line if it contains an image: field
    pointing at an upstream registry. Returns the (possibly rewritten) line."""
    m = re.match(r'^(\s*image:\s+)(.+)$', line)
    if not m:
        return line

    indent_and_key = m.group(1)
    image_value = m.group(2).strip()
    image_value = image_value.strip('"\'')

    new_image = make_forgejo_target(image_value, registry, namespace)
    if new_image != image_value:
        # Preserve quote style
        if image_value.startswith('"') and image_value.endswith('"'):
            new_image = f'"{new_image}"'
        elif image_value.startswith("'") and image_value.endswith("'"):
            new_image = f"'{new_image}'"
        return f"{indent_and_key}{new_image}\n"
    return line


def process_compose_file(path: Path, dry_run: bool, registry: str, namespace: str) -> list[str]:
    """Process a single compose file. Returns a list of changed line descriptions."""
    changes = []
    try:
        content = path.read_text()
    except Exception as e:
        print(f"  ✗ Cannot read {path}: {e}", file=sys.stderr)
        return changes

    lines = content.splitlines(keepends=True)
    new_lines = []
    for i, line in enumerate(lines, 1):
        new_line = rewrite_image_line(line, registry, namespace)
        if new_line != line:
            old_img = line.split("image:", 1)[1].strip().strip('"\'')
            new_img = new_line.split("image:", 1)[1].strip().strip('"\'')
            changes.append(f"    Line {i}: {old_img} → {new_img}")
            new_lines.append(new_line)
        else:
            new_lines.append(line)

    if changes:
        if not dry_run:
            path.write_text("".join(new_lines))
        print(f"  {'[DRY-RUN] ' if dry_run else ''}Modified: {path.relative_to(REPO_ROOT)}")
        for c in changes:
            print(c)

    return changes


def find_compose_files(root: Path) -> list[Path]:
    """Find all compose files under the repo root, excluding skipped dirs."""
    compose_files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in (".yml", ".yaml"):
            continue
        # Skip workflow files
        if ".forgejo" in path.parts:
            continue
        # Skip provisioning/dashboard configs
        parts = set(path.parts)
        if SKIP_DIRS & parts:
            continue
        # Skip files that must never be rewritten (bootstrap infra)
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in SKIP_FILES:
            continue
        # Skip files that aren't compose files (no 'image:' or 'services:')
        try:
            content = path.read_text()
        except Exception:
            continue
        if "image:" not in content and "services:" not in content:
            continue
        compose_files.append(path)
    return sorted(compose_files)


def main():
    parser = argparse.ArgumentParser(
        description="Rewrite compose file image: fields to point at local Forgejo registry"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files",
    )
    parser.add_argument(
        "--registry",
        default="git.u-acres.com",
        help="Local registry hostname (default: git.u-acres.com)",
    )
    parser.add_argument(
        "--namespace",
        default="nicholas",
        help="Registry namespace (default: nicholas)",
    )
    args = parser.parse_args()

    registry = args.registry
    namespace = args.namespace

    compose_files = find_compose_files(REPO_ROOT)
    print(f"Found {len(compose_files)} compose files")
    print(f"{'[DRY-RUN] ' if args.dry_run else ''}Rewriting images to {registry}/{namespace}/...")
    print()

    total_changes = 0
    for cf in compose_files:
        changes = process_compose_file(cf, args.dry_run, registry, namespace)
        total_changes += len(changes)

    print()
    if args.dry_run:
        print(f"[DRY-RUN] {total_changes} lines would be rewritten across {len(compose_files)} files")
    else:
        print(f"Done. {total_changes} lines rewritten across {len(compose_files)} files")


if __name__ == "__main__":
    main()
