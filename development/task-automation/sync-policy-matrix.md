# Sync Policy Matrix

This policy controls when tasks are referenced versus synchronized.

## Default Rule

- Reference-first for external systems.
- Opt-in sync for build and infra projects only.
- Personal ADHD task flow stays low-noise and primarily in Vikunja.

## Matrix

| Task Class | Microsoft To Do | Forgejo | Outline |
|---|---|---|---|
| Personal ADHD daily tasks | Bidirectional (selected lists only) | Reference only | Completion summary only |
| Infra/build execution tasks | Optional bidirectional | Bidirectional (opt-in project allowlist) | Build log + decision record |
| Incident and break/fix tasks | Optional one-way to capture | Create issue + selective status sync | Incident runbook required |
| Family household tasks | Optional bidirectional (shared lists) | Reference only | Weekly digest summary |

## Field Ownership

- Vikunja-owned fields: `project`, `labels`, `effortBucket`, `reviewBy`, `conflictState`.
- Shared mutable fields: `title`, `description`, `dueAt`, `status`.
- Forgejo-owned fields: `issueNumber`, `issueUrl`, repository context.
- Outline-owned fields: `docId`, `docUrl`, document template metadata.

## Conflict Strategy

- Low risk fields: last-write-wins.
- Protected Vikunja fields: never overwritten by external systems.
- Ambiguous changes: route to manual review queue in Vikunja.

## Guardrails

- Repo allowlist required for Forgejo issue sync.
- Project allowlist required for bidirectional issue status sync.
- Disable outbound lane first during rollback; keep inbound capture active.
