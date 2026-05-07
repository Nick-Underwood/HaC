#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


def assert_condition(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def assert_file_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise RuntimeError(f"{label} not found: {path.as_posix()}")


def get_relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def extract_compose_matches(raw: str) -> list[str]:
    working_directory_match = re.search(r'working-directory:\s+"\./(Docker-(Critical|NonCritical)/[^\r\n"\']+)"', raw)
    compose_file_match = re.search(r"docker compose[^\r\n]+-f\s+([^\s\"'`]+\.ya?ml)", raw)

    compose_matches: list[str] = []

    if working_directory_match and compose_file_match:
        compose_matches = [f"{working_directory_match.group(1)}/{compose_file_match.group(1)}"]

    if not compose_matches:
        compose_matches = list(dict.fromkeys(re.findall(r"Docker-(?:Critical|NonCritical)/[^\r\n\"']+\.ya?ml", raw)))

    if not compose_matches and working_directory_match:
        compose_fallback = re.search(r"-f\s+([^\s\"'`]+\.ya?ml)", raw)
        if compose_fallback:
            compose_matches = [f"{working_directory_match.group(1)}/{compose_fallback.group(1)}"]

    return compose_matches


def get_deploy_workflow_entries(workflow_dir: Path, repo_root: Path) -> list[dict]:
    assert_file_exists(workflow_dir, "Workflow directory")

    entries: list[dict] = []
    deploy_workflows = sorted(workflow_dir.glob("deploy-*.yml"), key=lambda p: p.name)

    for workflow in deploy_workflows:
        raw = workflow.read_text(encoding="utf-8")
        compose_matches = extract_compose_matches(raw)

        rel_workflow = get_relative_path(workflow, repo_root)
        assert_condition(len(compose_matches) >= 1, f"Deploy workflow missing compose path reference: {rel_workflow}")
        assert_condition(len(compose_matches) == 1, f"Deploy workflow must reference exactly one compose file: {rel_workflow}")

        workflow_id = re.sub(r"[^a-zA-Z0-9-]", "-", re.sub(r"^deploy-", "", workflow.stem)).lower()
        entries.append(
            {
                "Id": workflow_id,
                "WorkflowPath": rel_workflow,
                "ComposePath": compose_matches[0],
            }
        )

    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate canonical service catalog against deploy workflows.")
    parser.add_argument("--catalog-path", default="development/service-catalog/data/services.catalog.json")
    parser.add_argument("--schema-path", default="development/service-catalog/schema/service-catalog.schema.json")
    parser.add_argument("--workflow-dir", default=".forgejo/workflows")
    args = parser.parse_args()

    repo_root = Path.cwd()
    catalog_path = (repo_root / args.catalog_path).resolve()
    schema_path = (repo_root / args.schema_path).resolve()
    workflow_dir = (repo_root / args.workflow_dir).resolve()

    assert_file_exists(catalog_path, "Catalog")
    assert_file_exists(schema_path, "Schema")
    assert_file_exists(workflow_dir, "Workflow directory")

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    workflow_entries = get_deploy_workflow_entries(workflow_dir, repo_root)

    assert_condition(schema.get("$id") is not None, "Schema must include $id.")
    assert_condition(schema.get("$defs", {}).get("service") is not None, "Schema must include $defs.service definition.")
    assert_condition(re.match(r"^1\.[0-9]+$", str(catalog.get("schemaVersion", ""))) is not None, "Catalog schemaVersion must match 1.x format.")

    services = catalog.get("services", [])
    assert_condition(len(services) == len(workflow_entries), f"Catalog must include exactly one entry for each deploy workflow. Catalog={len(services)} Workflows={len(workflow_entries)}.")

    service_ids: dict[str, bool] = {}
    workflow_paths: dict[str, str] = {}
    compose_paths: dict[str, str] = {}

    for service in services:
        service_id = service.get("id", "")
        assert_condition(re.match(r"^[a-z0-9-]+$", str(service_id)) is not None, f"Invalid service id: {service_id}")
        assert_condition(service_id not in service_ids, f"Duplicate service id: {service_id}")
        service_ids[service_id] = True

        workflow_path = service.get("workflowPath", "")
        compose_path = service.get("composePath", "")

        assert_condition(workflow_path not in workflow_paths, f"Duplicate workflowPath: {workflow_path}")
        workflow_paths[workflow_path] = service_id

        assert_condition(compose_path not in compose_paths, f"Duplicate composePath: {compose_path}")
        compose_paths[compose_path] = service_id

        assert_condition((repo_root / compose_path).exists(), f"composePath missing for {service_id}: {compose_path}")
        assert_condition((repo_root / workflow_path).exists(), f"workflowPath missing for {service_id}: {workflow_path}")

        change_window = service.get("changeWindow")
        notes = service.get("notes")
        assert_condition(isinstance(change_window, str) and change_window.strip() != "", f"changeWindow required for {service_id}")
        assert_condition(isinstance(notes, str) and notes.strip() != "", f"notes required for {service_id}")

        tier = service.get("tier")
        host = service.get("host")
        expected_host = "hac-critical" if tier == "critical" else "hac-noncritical"
        assert_condition(host == expected_host, f"Host/tier mismatch for {service_id}: tier={tier} host={host}")

        expected_tier = "critical" if str(compose_path).startswith("Docker-Critical/") else "noncritical"
        assert_condition(tier == expected_tier, f"composePath/tier mismatch for {service_id}: {compose_path}")

        expected_id = re.sub(r"[^a-zA-Z0-9-]", "-", re.sub(r"^deploy-", "", Path(workflow_path).stem)).lower()
        assert_condition(service_id == expected_id, f"Service id/workflow mismatch for {service_id}: expected {expected_id} from {workflow_path}")

        for dep in service.get("dependencies", []) or []:
            assert_condition(dep != service_id, f"Service {service_id} cannot depend on itself.")

    workflow_by_path: dict[str, dict] = {}
    workflow_by_id: dict[str, dict] = {}
    for entry in workflow_entries:
        workflow_path = entry["WorkflowPath"]
        workflow_id = entry["Id"]
        assert_condition(workflow_path not in workflow_by_path, f"Duplicate deploy workflow discovered: {workflow_path}")
        assert_condition(workflow_id not in workflow_by_id, f"Duplicate deploy workflow id discovered: {workflow_id}")
        workflow_by_path[workflow_path] = entry
        workflow_by_id[workflow_id] = entry

    for service in services:
        service_id = service["id"]
        for dep in service.get("dependencies", []) or []:
            assert_condition(dep in service_ids, f"Unknown dependency '{dep}' in service '{service_id}'.")

        workflow_path = service["workflowPath"]
        assert_condition(workflow_path in workflow_by_path, f"Catalog references unknown workflowPath for {service_id}: {workflow_path}")
        workflow_entry = workflow_by_path[workflow_path]
        assert_condition(workflow_entry["ComposePath"] == service["composePath"], f"Catalog composePath mismatch for {service_id}: expected {workflow_entry['ComposePath']}")

    for workflow_entry in workflow_entries:
        assert_condition(workflow_entry["Id"] in service_ids, f"Missing catalog entry for deploy workflow id '{workflow_entry['Id']}' ({workflow_entry['WorkflowPath']}).")

    print(f"Service catalog validation passed for {len(services)} services across {len(workflow_entries)} deploy workflows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
