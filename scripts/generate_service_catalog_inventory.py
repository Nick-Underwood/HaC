#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def to_posix_relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def get_compose_path_from_workflow(raw: str) -> str | None:
    wd_match = re.search(r'working-directory:\s+"\./(Docker-(Critical|NonCritical)/[^\r\n"\']+)"', raw)
    compose_match = re.search(r"docker compose[^\r\n]+-f\s+([^\s\"'`]+\.ya?ml)", raw)

    working_directory = wd_match.group(1) if wd_match else None
    compose_file = compose_match.group(1) if compose_match else None

    if working_directory and compose_file:
        return f"{working_directory}/{compose_file}"

    compose_paths = list(dict.fromkeys(re.findall(r"Docker-(?:Critical|NonCritical)/[^\r\n\"']+\.ya?ml", raw)))
    if compose_paths:
        return compose_paths[0]

    if working_directory:
        compose_fallback = re.search(r"-f\s+([^\s\"'`]+\.ya?ml)", raw)
        if compose_fallback:
            return f"{working_directory}/{compose_fallback.group(1)}"

    return None


def get_domain_from_compose_path(compose_path: str) -> str:
    segments = compose_path.split("/")
    if len(segments) < 3:
        return "management"

    return {
        "Auth": "auth",
        "Networking": "networking",
        "Home": "home",
        "Management": "management",
        "Media": "media",
        "Tools": "tools",
        "Automation": "automation",
        "Security": "security",
        "Finance": "finance",
    }.get(segments[1], "management")


def get_display_name(service_id: str) -> str:
    return " ".join(part.capitalize() for part in service_id.split("-") if part)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate service catalog inventory from deploy workflows.")
    parser.add_argument("--workflow-dir", default=".forgejo/workflows")
    parser.add_argument("--output-path", default="development/service-catalog/data/services.inventory.json")
    args = parser.parse_args()

    repo_root = Path.cwd()
    workflow_dir = (repo_root / args.workflow_dir).resolve()
    output_path = (repo_root / args.output_path).resolve()

    deploy_workflows = sorted(workflow_dir.glob("deploy-*.yml"))
    services: list[dict] = []

    for workflow in deploy_workflows:
        raw = workflow.read_text(encoding="utf-8")
        compose_path = get_compose_path_from_workflow(raw)
        if not compose_path:
            continue

        tier = "critical" if compose_path.startswith("Docker-Critical/") else "noncritical"
        target_host = "hac-critical" if tier == "critical" else "hac-noncritical"
        domain = get_domain_from_compose_path(compose_path)

        base = workflow.stem
        service_id = re.sub(r"[^a-zA-Z0-9-]", "-", re.sub(r"^deploy-", "", base)).lower()

        services.append(
            {
                "id": service_id,
                "name": get_display_name(service_id),
                "tier": tier,
                "host": target_host,
                "domain": domain,
                "composePath": compose_path,
                "workflowPath": to_posix_relative(workflow, repo_root),
                "owner": "unassigned",
                "criticality": "tier-2" if tier == "critical" else "tier-3",
                "rollbackClass": "stateless",
                "dependencies": [],
                "changeWindow": "off-peak",
                "notes": "Generated from deploy workflow metadata; requires curation.",
            }
        )

    deduped: dict[str, dict] = {}
    for service in sorted(services, key=lambda x: x["id"]):
        deduped[service["id"]] = service

    doc = {
        "schemaVersion": "1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "services": list(deduped.values()),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Generated inventory at {args.output_path} with {len(deduped)} services.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
