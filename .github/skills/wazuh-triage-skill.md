# Wazuh Triage Skill

## Goal

Classify and respond to Wazuh alerts quickly while preserving evidence and reducing noise.

## Trigger

Use this skill for alert review, incident triage, suppression decisions, and escalation handoff.

## Triage Steps

1. Intake key fields: rule id, level, host, user, src/dst, process, timestamp.
2. Validate recency, deduplicate, and map to active asset.
3. Enrich with nearby events and known maintenance context.
4. Assign severity and confidence.
5. Decide containment, remediation, or monitoring action.
6. Escalate if impact or confidence warrants.

## Severity Guidance

- Critical: active compromise indicators or high-confidence data exposure risk.
- High: strong malicious indicators with meaningful operational impact.
- Medium: suspicious behavior requiring timely investigation.
- Low: weak signal or expected noise with no immediate impact.

## Tuning Rules

- Prefer scoped suppression with owner and expiry.
- Never suppress globally from one sample.
- Revisit suppressions after topology or threat-surface changes.

## Completion Contract

- Severity and confidence
- Evidence summary
- Affected assets
- Containment/remediation recommendation
- Escalation status
- Tuning recommendation
