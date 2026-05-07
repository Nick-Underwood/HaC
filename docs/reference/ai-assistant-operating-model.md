# AI Assistant Operating Model (HaC)

This document captures the strategy used for AI assistants in this repository and complements the local workspace instruction file.

## Why this split

- Local instruction files can contain operational metadata and should remain protected.
- This tracked document is a sanitized policy reference that explains expected behavior.

## Core Strategy

- Optimize for safety first, speed second.
- Keep edits scoped and reversible.
- Treat compose, deployment workflow, and service catalog as a coupled system.

## Required Behavior for AI Assistants

1. Respect critical vs non-critical boundaries.
2. Never expose or hardcode secrets.
3. Preserve existing naming, labeling, and network conventions.
4. Update all coupled files when service topology changes.
5. Include verification commands with every infrastructure change.
6. Explain blast radius and rollback options for risky changes.

## MCP Usage Strategy

- Prefer a single gateway endpoint for AI clients:
  - `https://mcp.u-acres.com/mcp`
- Use bearer-token auth via client-side secure input prompts (not plaintext in config).
- Keep server registration and upstream routing in infra automation (`deploy-mcpservers.yml`).

## Operational Notes

- Current deployment model already includes dedicated workflows:
  - `.forgejo/workflows/deploy-mcpgateway.yml`
  - `.forgejo/workflows/deploy-mcpservers.yml`
- MCP service definitions live under:
  - `Docker-NonCritical/Automation/AI/MCPGateway/`

## Recommended Validation Sequence

1. Validate changed YAML files.
2. Run service-catalog validation when catalog data changed.
3. Confirm changed files with `git status --short`.
4. For MCP changes, confirm gateway health and tool discovery from VS Code MCP server actions.
