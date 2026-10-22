# Task Automation Bootstrap (ADHD-First)

This directory is the first implementation slice for the task automation strategy.

Goals of this phase:
- Lock the canonical task model before live workflow rollout.
- Provide n8n workflow templates for:
  - Microsoft To Do <-> Vikunja sync
  - Vikunja <-> Forgejo selective issue sync
  - Vikunja -> Outline auto-documentation
- Keep production-safe defaults: all templates are inactive and require credential wiring.

## Directory Layout

- `field-contract.json` - Canonical task fields, ownership, and defaults.
- `sync-policy-matrix.md` - Reference-vs-sync decisions by task class.
- `ms-todo-vikunja-diff.config.example.json` - Mapping template for list/project diff checks.
- `n8n/workflows/*.json` - Importable template workflows (inactive).
- `n8n/workflows/README.md` - Wiring and rollout checklist.

## Diff Check (MS To Do vs Vikunja)

Use the PowerShell diff tool to compare mapped MS To Do lists and Vikunja projects, including sub-items.

- Script: `scripts/diff_ms_todo_vikunja.ps1`
- Config template: `development/task-automation/ms-todo-vikunja-diff.config.example.json`

Example:

```powershell
$env:MS_GRAPH_TOKEN = "<graph-token>"
$env:VIKUNJA_API_TOKEN = "<vikunja-token>"

pwsh -NoProfile -File ./scripts/diff_ms_todo_vikunja.ps1 `
  -MsGraphToken $env:MS_GRAPH_TOKEN `
  -VikunjaToken $env:VIKUNJA_API_TOKEN `
  -VikunjaUrl "https://tasks.example.com" `
  -ConfigPath "./development/task-automation/ms-todo-vikunja-diff.config.example.json"
```

Output files are generated under `development/task-automation/reports/`.
Sub-items are compared as:
- MS To Do checklist items
- Vikunja child tasks (matched by parent task)

## Rollout Order

1. Import templates into n8n as inactive workflows.
2. Configure credentials and environment variables.
3. Run dry-run mode against test projects/lists.
4. Enable inbound capture lane first.
5. Enable outbound lanes one at a time (To Do, Forgejo, Outline).
6. Monitor dead-letter queue and conflict metrics for 2 weeks.

## Safety Defaults

- `Vikunja` remains source of truth.
- Forgejo integration is reference-first; sync is opt-in per project.
- Outline auto-doc generation is gated by required metadata.
- All workflows should support a `DRY_RUN=true` runtime option before full write mode.
