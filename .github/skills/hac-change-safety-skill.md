# HaC Change Safety Skill

## Goal

Deliver infrastructure changes with low blast radius and predictable rollback.

## Trigger

Use this skill for any compose, workflow, service catalog, or operations-doc change.

## Fast Path

1. Identify service tier and host.
2. Check coupled files: compose, deploy workflow, catalog, docs.
3. Validate changed YAML and catalog integrity.
4. Summarize blast radius and rollback steps.

## Validation Order

1. YAML parse check for changed compose/workflow.
2. Service catalog validation when catalog changed.
3. Changed-file review via git status.

## Safety Rules

- Do not move services between tiers without explicit request.
- Keep secrets in Forgejo variables/secrets only.
- Prefer idempotent workflow behavior and explicit runner targeting.
- Escalate when rollback class implies stateful data risk.

## Completion Contract

- Risk level and rationale
- Blast radius
- Rollback path
- Verification evidence
- Issue linkage status
