# Product Delivery Workflow Skill

## Goal

Run structured delivery for non-trivial work using this sequence:

Idea -> Research -> Prototype -> PRD -> Kanban -> Implementation -> QA and Code Review.

## Trigger

Use this skill when requests include one or more of these signals:

- "new feature"
- "project"
- "prototype"
- "prd"
- "kanban"
- "plan then implement"
- work expected to span multiple sessions

## Workflow

1. Idea
   Define problem, user, success metric, and non-goals in 6 to 12 lines.
2. Research
   Validate constraints, dependencies, risks, and alternatives using repository evidence.
3. Prototype
   Build the smallest end-to-end tracer bullet that exercises the critical path.
4. PRD
   Freeze scope with acceptance criteria, metrics, rollout plan, and rollback.
5. Kanban
   Convert PRD into small tasks with explicit done criteria and ownership.
6. Implementation
   Execute tasks in thin vertical slices with validation after each slice.
7. QA and Code Review
   Verify behavior, regressions, coupling, security posture, and documentation updates.

## Tracer Bullet Rules

- Must prove one risky assumption from end-to-end, not isolated unit logic.
- Must be reversible in one commit or one deploy workflow rollback.
- Must include observable evidence (log line, test assertion, or UI state).
- Must be disposable if approach fails.

## Stage Gates

- Do not start PRD until prototype evidence exists.
- Do not start implementation until PRD has acceptance criteria and rollback path.
- Do not mark done until QA includes both happy path and one failure path.

## HaC Coupling Requirements

For infrastructure-impacting work, preserve HaC safety rules:

- Check coupled files: compose, deploy workflow, service catalog, docs.
- Validate YAML before broad testing.
- Validate service catalog if metadata changed.
- Report blast radius and rollback in closure output.

## Output Contract

Return these sections in order:

1. Stage completed
2. Artifacts produced
3. Risks discovered
4. Next tracer bullet or next task
5. Go/no-go decision for next stage

## Anti-Patterns

- Writing a long PRD before proving feasibility.
- Creating a Kanban board with tasks larger than one reviewable change.
- Jumping to final implementation without a tracer bullet.
- Declaring done without explicit QA evidence.
