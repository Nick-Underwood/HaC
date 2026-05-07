---
name: "Bug Report"
about: "A service, workflow, or configuration is behaving incorrectly"
title: "bug: "
labels: ["bug"]
---

## Summary

<!-- One sentence describing the defect and which service is affected -->

## Environment

| Field | Value |
| --- | --- |
| **Host** | <!-- hac-critical / hac-noncritical --> |
| **Service** | <!-- e.g. Traefik, Sonarr, Home Assistant --> |
| **Compose File** | <!-- e.g. Docker-NonCritical/Media/Sonarr/sonarr.yml --> |
| **Image / Version** | <!-- e.g. linuxserver/sonarr:latest @ sha256:... --> |

## Expected Behavior

<!-- What should happen under normal conditions -->

## Actual Behavior

<!-- What is actually happening; be specific -->

## Steps to Reproduce

1.
2.
3.

## Logs / Evidence

<!-- Paste relevant container logs, error messages, or screenshots. Use `docker logs <container>` or attach a file -->

```text
```

## Root Cause Hypothesis

<!-- Optional: your hypothesis on what is causing this -->

## Acceptance Criteria

- [ ] Defect no longer occurs under the described conditions
- [ ] No regression introduced in dependent services
- [ ] Fix is deployed via CI/CD and checksum updated
