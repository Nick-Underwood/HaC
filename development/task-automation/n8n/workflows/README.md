# n8n Workflow Templates

These templates are intentionally inactive and require credential setup.

## Included Templates

- `ms-todo_vikunja_bidirectional.json`
- `vikunja_forgejo_selective_sync.json`
- `vikunja_outline_autodoc.json`

## Required Credentials (n8n)

- Microsoft Graph OAuth2
- Vikunja API token (HTTP header auth)
- Forgejo API token (HTTP header auth)
- Outline API token or session credential

## Required Variables

- `VIKUNJA_URL`
- `VIKUNJA_API_TOKEN`
- `VIKUNJA_ERROR_PROJECT_ID` (numeric project id of the "Sync Errors" project that receives dead-letter tasks)
- `N8N_BASE_URL`
- `MS_TODO_DELTA_URL`
- `MS_TODO_WRITE_URL`
- `FORGEJO_URL`
- `FORGEJO_OWNER`
- `FORGEJO_TOKEN`
- `FORGEJO_REPO_ALLOWLIST` (comma-separated, e.g. `hac,infra`)
- `FORGEJO_SYNC_REPO` (single repo the pull lane watches; defaults to `hac` in-template if unset)
- `OUTLINE_URL`
- `OUTLINE_API_TOKEN`
- `OUTLINE_COLLECTION_ID` (numeric/string id of the "Task Autodocs" collection)
- `DRY_RUN` (`true` in initial rollout)

## Dead-Letter Lane (added)
Every workflow now has an `Error Trigger` ("Catch Errors") node that, on any failure,
creates a task in the Vikunja project `VIKUNJA_ERROR_PROJECT_ID` titled
`[SYNC ERROR] <workflow>`. Check that project to see failed syncs — no silent drift.

## Import Checklist

1. Import all workflow JSON files.
2. Confirm each workflow remains inactive.
3. Set credentials and variables.
4. Execute each workflow in manual test mode.
5. Verify payload normalization and idempotency keys.
6. Enable one workflow at a time.
