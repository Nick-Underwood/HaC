# Repo SME Profile Skill

## Goal

Operate like a repository SME by loading core context first and recording new operational knowledge after each substantial task.

## Startup Read Sequence

1. README and top-level architecture notes.
2. Agent-specific safety and coupled-file requirements.
3. Relevant service or workflow files for the requested change.
4. Existing learning journal entries in `.github/knowledge/sme-learning.md`.

## HaC Domain Focus

- Tier boundaries and host placement.
- Coupled-file rule across compose, workflow, catalog, and docs.
- Idempotent deployment behavior and rollback clarity.
- Secret governance and runner targeting.

## Expected Validation Habits

- Validate changed YAML early.
- Validate service catalog when topology metadata changes.
- Capture blast radius and rollback path before closure.

## Learning Loop

After each substantial task, append one short entry in `.github/knowledge/sme-learning.md` using this structure:

- Date
- What changed
- Impacted area
- Lesson
- New guardrail/checklist rule
- Confidence
- Recurrence
- Follow-up

## Curation Rule

- During weekly review, merge duplicate lessons and promote recurring guardrails into this skill file.
