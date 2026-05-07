# HaC Outline Documentation Coverage Matrix

This matrix maps major HaC platform areas and services to expected Outline reference documentation.

Status values:

- Present: Explicit Outline page is already referenced in the repo.
- Missing or unverified: No explicit Outline reference in repo, or Outline existence cannot be verified from this session.

## Core Platform References

- Architecture
  - Expected doc: Overview and Architecture
  - Status: Present
  - Repo evidence: README key docs list
- Service onboarding
  - Expected doc: Service Creation Guide
  - Status: Present
  - Repo evidence: README and GETTING_STARTED
- Configuration governance
  - Expected doc: Forgejo Variables Reference
  - Status: Present
  - Repo evidence: README and GETTING_STARTED
- Initial bootstrap
  - Expected doc: Quick Setup Checklist
  - Status: Present
  - Repo evidence: README key docs list
- Observability labels
  - Expected doc: Docker Container Monitoring
  - Status: Present
  - Repo evidence: README key docs list

## Existing Service-Level Outline References

- InfluxDB
  - Expected doc: InfluxDB
  - Status: Present
  - Repo evidence: Docker-Critical/Tools/InfluxDB/README.md
- Omada
  - Expected doc: Omada Controller Quick Reference
  - Status: Present
  - Repo evidence: Docker-Critical/Networking/Omada/SETUP_QUICK_REFERENCE.md
- MCP Gateway
  - Expected doc: MCP Gateway Stack and MCP Gateway Forgejo Setup
  - Status: Present
  - Repo evidence: Docker-NonCritical/Automation/AI/MCPGateway/README.md and FORGEJO_SETUP.md
- NetBox
  - Expected doc: NetBox Configuration Guide, NetBox Quick Reference, NetBox Sync Scripts
  - Status: Present
  - Repo evidence: Docker-Critical/Home/NetBox docs
- RTL-SDR
  - Expected doc: RTL-SDR Setup
  - Status: Present
  - Repo evidence: Docker-Critical/Home/RTL-SDR/README.md
- Doomsday Library
  - Expected doc: Kiwix and Doomsday Library
  - Status: Present
  - Repo evidence: Docker-Critical/Home/Doomsday/README.md
- Music Assistant
  - Expected doc: Music Assistant
  - Status: Present
  - Repo evidence: Docker-Critical/Home/MusicAssistant/README.md
- Wazuh
  - Expected doc: Wazuh Setup Guide
  - Status: Present
  - Repo evidence: Docker-NonCritical/Security/WAZUH-SETUP.md

## Major Service Areas Without Explicit Repo-Linked Outline References

- Outline platform
  - Expected doc: Outline Platform Admin Guide
  - Status: Missing or unverified
- CI and CD operations
  - Expected doc: Deployment Workflow Reference
  - Status: Missing or unverified
- Networking model
  - Expected doc: Network Topology and External Networks
  - Status: Missing or unverified
- DNS and routing
  - Expected doc: DNS, Domain, and Proxy Routing
  - Status: Missing or unverified
- Secrets lifecycle
  - Expected doc: Secrets and Variable Governance
  - Status: Missing or unverified
- Backup and restore
  - Expected doc: Backup and Restore Runbooks
  - Status: Missing or unverified
- Host model
  - Expected doc: Host Inventory and Runner Responsibilities
  - Status: Missing or unverified
- Dependency map
  - Expected doc: Service Ownership and Dependency Map
  - Status: Missing or unverified
- Incident response
  - Expected doc: Break-Glass and Incident Recovery
  - Status: Missing or unverified
- Core control-plane services
  - Expected docs: Authentik Operations Guide, Traefik Operations Guide, Forgejo Platform Operations Guide, Home Assistant Platform Guide, Cloudflared Operations Guide, N8N Operations and Integrations, Vikunja Operations Guide
  - Status: Missing or unverified

## First-Wave Documentation Set to Create in Outline

1. Outline Platform Admin Guide
2. Deployment Workflow Reference
3. Network Topology and External Networks
4. DNS, Domain, and Proxy Routing
5. Secrets and Variable Governance
6. Backup and Restore Runbooks
7. Host Inventory and Runner Responsibilities
8. Service Ownership and Dependency Map
9. Break-Glass and Incident Recovery
10. Authentik Operations Guide
11. Traefik Operations Guide
12. Forgejo Platform Operations Guide
13. Home Assistant Platform Guide
14. Cloudflared Operations Guide
15. N8N Operations and Integrations
16. Vikunja Operations Guide

Tracking issue: [Issue 16](https://git.u-acres.com/nicholas/hac/issues/16)
