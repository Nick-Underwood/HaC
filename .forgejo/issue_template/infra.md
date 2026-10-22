---
name: "Infrastructure Change"
about: "A host, network, storage, or CI/CD configuration change"
title: "infra: "
labels: ["infrastructure"]
---

## Summary

<!-- One sentence describing the infrastructure change -->

## Affected Systems

| System | Details |
| --- | --- |
| **Host(s)** | <!-- hac-critical / hac-noncritical / both --> |
| **Component** | <!-- e.g. Traefik, OPNsense, Docker network, NFS mount --> |
| **Storage Path** | <!-- e.g. /srv/traefik, /mnt/hdd/backups --> |

## Change Description

<!-- Detailed description of what is changing and how -->

## Reason for Change

<!-- Why is this change necessary? Link to triggering bug or feature if applicable -->

## Implementation Steps

- [ ]
- [ ]
- [ ]

## Rollback Plan

<!-- How to revert this change if it causes issues -->

## Impact Assessment

| Area | Impact |
| --- | --- |
| **Downtime** | <!-- Expected downtime, if any --> |
| **Dependent Services** | <!-- Services that may be affected --> |
| **Data at Risk** | <!-- Any data that could be lost or corrupted --> |

## Acceptance Criteria

- [ ] Change is applied and verified on target host(s)
- [ ] Dependent services confirmed operational post-change
- [ ] CI/CD workflow updated if compose or env vars changed
- [ ] Uptime Kuma monitors verified green
