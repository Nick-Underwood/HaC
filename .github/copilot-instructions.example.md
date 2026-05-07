# Copilot Instructions Template (Sanitized)

Use this as a version-controlled baseline for local Copilot/agent instruction files.

## Mission

- Keep infrastructure changes safe, reversible, and automatable.
- Favor small, reviewable edits.
- Preserve reliability, especially for critical services.

## Repository Rules

- Respect critical and non-critical service boundaries.
- Do not relocate services between criticality tiers unless explicitly requested.
- Never hardcode secrets, tokens, API keys, or credentials.

## Coupled-File Rule

When changing service behavior, review related artifacts in the same change:

- Compose file for the service
- Matching deploy workflow in `.forgejo/workflows/`
- Service catalog records under `development/service-catalog/data/` when topology changes
- Reference docs under `docs/reference/` when operations or ownership change

## Compose and Workflow Standards

- Preserve existing service label patterns and reverse-proxy conventions.
- Reuse existing external networks when possible.
- Keep deployment workflows idempotent and explicit about required vars/secrets.

## Safety and Validation

- Avoid destructive git actions unless explicitly requested.
- Prefer verification-first sequences for risky changes.
- Include validation commands in results (YAML checks, catalog validation, and changed-file summary).

## Sensitive Data Policy

- Keep private instruction variants in ignored or encrypted files.
- Commit sanitized templates only.
