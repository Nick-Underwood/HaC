# HaC SME Learning Log

Use this file as the repository memory layer for the HaC agents.

## Entry Template

- Date:
- Scope:
- Impacted area:
- Lesson:
- New guardrail:
- Confidence:
- Recurrence:
- Follow-up:

## Curation Notes

- Keep entries short and factual.
- Promote repeated lessons into `.github/skills/repo-sme-profile-skill.md`.
- Remove stale or duplicate guardrails during weekly curation.

## Entries

- Date: 2026-05-19
- Scope: Add Alexa companion service to Music Assistant stack
- Impacted area: Docker-Critical/Home/MusicAssistant and deploy workflow coupling
- Lesson: Multi-service compose stacks need image checks for every container, not just the first `image:` line.
- New guardrail: For compose files with 2+ services, deploy workflow must compare each service image and emit logs for each container after redeploy.
- Confidence: High
- Recurrence: Medium
- Follow-up: Audit existing multi-service deploy workflows for single-image comparison drift.

- Date: 2026-05-19
- Scope: Pivot Music Assistant stack to Home Assistant OS external endpoint
- Impacted area: Docker-Critical/Home/MusicAssistant compose/workflow assumptions
- Lesson: When an upstream service moves off Docker, bridge stacks must drop `depends_on` and use explicit external host vars.
- New guardrail: For bridge-only stacks, require one configurable `*_HOSTNAME` env var and no local-container health/dependency checks for external services.
- Confidence: High
- Recurrence: Medium
- Follow-up: Review other bridge services for accidental local-service assumptions.

- Date: 2026-06-04
- Scope: Vaultwarden deploy hardening before HAOS migration
- Impacted area: Vaultwarden deploy workflow secret handling
- Lesson: Vaultwarden warns on plaintext `ADMIN_TOKEN`; hashing it in the deploy path avoids the warning without changing the stored secret source.
- New guardrail: For Vaultwarden deploys, convert the admin token to Argon2 PHC before `docker compose up` and fail the deploy if the hash cannot be generated.
- Confidence: High
- Recurrence: Medium
- Follow-up: Verify the HAOS migration keeps the same hash-generation step or moves it into the add-on config path.

- Date: 2026-06-04
- Scope: Restore qBittorrent and NZBGet ingress access
- Impacted area: Docker-NonCritical/Networking/Torrent Traefik routing labels
- Lesson: Service outages can be caused by hostname drift (short-name vs full-name and common misspelling) even when container health and compose syntax are valid.
- New guardrail: For externally accessed services, include expected hostname aliases in Traefik rules (with matching TLS SANs) when users or dashboards commonly use alternate names.
- Confidence: Medium
- Recurrence: Medium
- Follow-up: Audit other user-facing service routers for alias gaps between documented and commonly used hostnames.

- Date: 2026-06-04
- Scope: Fix Open WebUI deploy gate on missing OLLAMA_BASE_URL
- Impacted area: Noncritical Open WebUI workflow and compose defaults
- Lesson: Treating optional integration endpoints as required deploy gates creates avoidable pipeline failures.
- New guardrail: Only enforce vars as required in workflows if the compose file has no safe default; otherwise set fallback in shell and compose.
- Confidence: High
- Recurrence: Medium
- Follow-up: Audit noncritical deploy workflows for required-var drift against compose defaults.

- Date: 2026-06-05
- Scope: Recover MCP Gateway startup from Alembic check-constraint failure
- Impacted area: Docker-NonCritical/Automation/AI/MCPGateway pre-start database compatibility
- Lesson: Upstream image migrations can assume columns that may be missing in long-lived databases with historical schema drift.
- New guardrail: For upstream services with auto-migrations and persistent databases, add an idempotent preflight SQL compatibility step in compose before app startup.
- Confidence: High
- Recurrence: Medium
- Follow-up: Pin MCP Gateway to a tested image tag after confirming which upstream release contains the migration ordering fix.
