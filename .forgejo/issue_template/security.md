---
name: "Security Issue"
about: "A vulnerability, misconfiguration, or security risk that needs remediation"
title: "security: "
labels: ["security"]
---

## Summary

<!-- One sentence describing the security concern — avoid disclosing sensitive exploit details publicly -->

## Risk Classification

| Field | Value |
| --- | --- |
| **Severity** | <!-- Critical / High / Medium / Low --> |
| **Category** | <!-- e.g. Exposed service, weak auth, unpatched CVE, misconfiguration --> |
| **Affected Host** | <!-- hac-critical / hac-noncritical --> |
| **Affected Service** | <!-- e.g. Authentik, Vaultwarden, Traefik --> |
| **Exposure** | <!-- Internal-only / Cloudflare-exposed / Public internet --> |

## Description

<!-- Detail the vulnerability or misconfiguration. What is at risk, and under what conditions? -->

## Evidence

<!-- Logs, scan output, CVE reference, or reproducible steps. Redact credentials -->

```text
```

## Remediation Plan

- [ ]
- [ ]
- [ ]

## Acceptance Criteria

- [ ] Vulnerability is remediated and verified
- [ ] No new attack surface introduced by the fix
- [ ] Wazuh / CrowdSec alerts cleared or suppressed with justification
- [ ] Fix is deployed via CI/CD
