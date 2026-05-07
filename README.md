# Homelab-as-Code (HaC)

> **GitHub Mirror:** [github.com/Nick-Underwood/HaC](https://github.com/Nick-Underwood/HaC) — automatically synced from Forgejo via `mirror-to-github.yml`

Complete infrastructure-as-code for a self-hosted home automation and media center, organized into critical and non-critical services with automated deployment via Forgejo CI/CD. HaC stands for "Homelab-as-Code."

## Documentation

Full documentation lives in **[Outline](https://docs.u-acres.com)** — the homelab wiki. This repo contains only compose files, workflows, and scripts; all setup guides, configuration references, and integration notes are in Outline.

**Homelab collection:** [docs.u-acres.com](https://docs.u-acres.com)

Key docs:
- [Overview & Architecture](https://docs.u-acres.com/doc/overview-architecture-cNdSRv2VKa)
- [Service Creation Guide](https://docs.u-acres.com/doc/service-creation-guide-4UODNqOvPN)
- [Forgejo Variables Reference](https://docs.u-acres.com/doc/forgejo-variables-reference-nvgshbtzQK)
- [Quick Setup Checklist](https://docs.u-acres.com/doc/quick-setup-checklist-6Rfg1ZYWuy)
- [Docker Container Monitoring](https://docs.u-acres.com/doc/docker-container-monitoring-LGL1OrDfm8)

Documentation planning artifacts in this repo:
- [Outline Coverage Matrix](docs/outline-doc-coverage-matrix.md)
- [Reference Stub Index](docs/reference/first-wave-core-service-guides.md)

---

## Architecture Overview

### Deployment Model

- **Git-based:** Configuration managed through Forgejo (self-hosted Git server)
- **Infrastructure as Code:** All services defined via Docker Compose
- **Automated Deployments:** Forgejo workflows trigger on file changes
- **Multi-Host:** Two hosts — critical (home automation) and non-critical (media/tools)

### Network Structure

- **homeproxy:** Home services and automation (internal only)
- **mediaproxy:** Entertainment and media services
- **toolsproxy:** Backend utilities and infrastructure
- **torrentproxy:** Torrent/VPN services
- **aiproxy:** LLM and AI services
- **secproxy:** Security and monitoring
- **gitproxy:** Git infrastructure
- **authnet:** Privileged authentication services (LDAP, OAuth)

### Reverse Proxy

- **Traefik:** Two instances (critical and non-critical)
  - SSL termination via Let's Encrypt with Cloudflare DNS-01 challenge
  - Individual per-subdomain certificates
  - Automatic service discovery via Docker labels

---

## Repository Structure

```
HaC/
├── .forgejo/workflows/          # Deployment automation (Forgejo Actions)
├── Docker-Critical/             # Mission-critical services (hac-critical host)
├── Docker-NonCritical/          # Non-essential services (hac-noncritical host)
├── scripts/                     # Utility scripts
└── README.md                    # This file

> **Note:** Supplemental documentation (setup guides, variable reference, monitoring patterns) has moved to
> `Development/docs/` and will be migrated to Outline (`docs.${DOMAIN_NAME}`) on hac-critical.
```

---

## HaC-Critical Services

Services running on **hac-critical** (critical host).

**Storage layout on hac-critical:**

- `/srv` (NVMe #1) for critical configs and high-IO databases
- `/mnt/nvme-appdata` (NVMe #2) for appdata/search/AI tiers (NetBox, HomeBox, KaraKeep Meili, etc.)
- `/mnt/hdd` for backups/logs/archives (e.g., ZIM files, service logs)

### Authentication & Access Control

- **Authentik** (`Auth/Authentik.yml`) - Identity provider and SSO
  - OAuth2, OIDC, SAML, LDAP support
  - Built-in user directory (replaces LLDAP)
  - Traefik forward auth integration for protected services

- **Vaultwarden** (`Auth/vaultwarden.yml`) - Self-hosted Bitwarden-compatible password manager
  - WebSocket support for live sync
  - Registration and password hints disabled
  - PostgreSQL backend
  - Dashboard at `vault.${DOMAIN_NAME}`

### Networking & Proxy

- **Traefik** (`Networking/Proxy/proxy.yml`) - Reverse proxy and load balancer
  - HTTP/HTTPS with individual SSL certificates per domain
  - Dashboard at `hac-critical-traefik.${DOMAIN_NAME}`
  - Service discovery and routing

- **Omada Controller** (`Networking/Omada/omada.yml`) - TP-Link network management
  - WiFi and network device management
  - Dashboard at `omada.${DOMAIN_NAME}`

- **Postfix SMTP Relay** (`Networking/Mail/Postfix.yml`) - Email delivery
  - Relays outbound mail for internal services
  - Credentials via Forgejo secrets

- **Cloudflared** (`Networking/Cloudflared/cloudflared.yml`) - Cloudflare Tunnel
  - Secure external access without port forwarding
  - Automatic DNS and certificate management

### Home Automation Core

- **Home Assistant** (`Home/HomeAssistant/homeassistant.yml`) - Home automation hub
  - Core automation and smart home control
  - Dashboard at `ha.${DOMAIN_NAME}`

- **ESPHome** (`Home/HomeAssistant/homeassistant.yml`) - IoT device management
  - Firmware compilation for ESP8266/ESP32 devices
  - Dashboard at `esphome.${DOMAIN_NAME}`
  - Device-to-Home Assistant integration

- **RTL-SDR** (`Home/RTL-SDR/rtl-sdr.yml`) - Software-defined radio receiver
  - 433 MHz and 915 MHz frequency monitoring
  - MQTT integration with Home Assistant
  - Weather station and sensor data decoding
  - Config: `/srv/rtl-sdr/`

- **Govee2MQTT** (`Home/Govee2MQTT/govee2mqtt.yml`) - Govee device MQTT bridge
  - Integrates Govee lights and sensors with Home Assistant
  - MQTT-based control and monitoring

- **NUT (Network UPS Tools)** (`Home/NUT/nut.yml`) - UPS monitoring
  - Battery backup monitoring and management
  - Automatic shutdown coordination

- **Whisper** (`Home/Whisper/whisper.yml`) - Speech recognition
  - Local speech-to-text processing
  - Privacy-focused voice assistant integration

### Infrastructure Services

- **Forgejo** (`Management/Git - Forgejo/git.yml`) - Self-hosted Git server
  - Repository hosting and Git service
  - CI/CD Actions runners
  - Dashboard at `git.${DOMAIN_NAME}`
  - PostgreSQL backend

- **NetBox** (`Home/NetBox/netbox.yml`) - Network documentation
  - IP address management (IPAM)
  - Device and network inventory
  - Custom theming via sage-green theme
  - PostgreSQL + Redis backends
  - Dashboard at `netbox.${DOMAIN_NAME}`

### Data & Monitoring

- **InfluxDB** (`Tools/InfluxDB/influxdb.yml`) - Time-series database
  - Stores metrics and sensor data from Home Assistant
  - Historical data archival and analysis
  - Flux query language for complex aggregations
  - Dashboard at `influx.${DOMAIN_NAME}`

- **Docker Socket Proxy** (`Tools/DockerSocketProxy/docker-socket-proxy.yml`) - Secure Docker API access
  - Restricts Docker socket access for Traefik and monitoring
  - Security layer for Docker daemon

- **Dockhand** (`Tools/Dockhand/dockhand.yml`) - Docker compose stack management UI
  - Web interface for managing compose stacks
  - OIDC authentication via Authentik
  - Dashboard at `dockhand.${DOMAIN_NAME}`

- **Uptime Kuma** (`Management/UptimeKuma/uptime-kuma.yml`) - Uptime monitoring
  - Monitors all services across both hosts (HTTP, TCP, Docker)
  - Dashboard at `uptime.${DOMAIN_NAME}`

- **Outline** (`Tools/Outline/outline.yml`) - Team knowledge base / documentation wiki
  - OIDC authentication via Authentik
  - File attachments via bundled MinIO (S3-compatible)
  - Dashboard at `docs.${DOMAIN_NAME}` | MinIO console at `minio-outline-console.${DOMAIN_NAME}`

- **N8N** (`Tools/N8N/n8n.yml`) - Workflow automation
  - No-code automation platform
  - Integration with Vikunja, MS To Do, Ollama, Home Assistant
  - ADHD task management workflows (Vikunja ↔ MS To Do sync and service integrations)
  - Dashboard at `n8n.${DOMAIN_NAME}`

### Home Services

- **Norish** (`Home/Cooking/norish.yml`) - Recipe manager
  - Recipe collection and meal planning
  - Web page recipe clipping with headless Chrome
  - OIDC authentication via Authentik
  - PostgreSQL + Redis backends
  - Dashboard at `norish.${DOMAIN_NAME}`

- **KaraKeep** (`Home/KaraKeep/karakeep.yml`) - Bookmark manager
  - Save and organize bookmarks and links
  - Web page archiving and screenshots
  - Meilisearch integration for full-text search
  - Dashboard at `kara.${DOMAIN_NAME}`

- **Music Assistant** (`Home/MusicAssistant/musicassistant.yml`) - Music server and player management
  - Unified music library from multiple providers (Spotify, Plex, Jellyfin, local files)
  - Multi-player support (Sonos, AirPlay, Google Cast, DLNA, etc.)
  - Local audio file streaming with quality selection
  - Host network mode for mDNS/player discovery
  - Dashboard at `music.${DOMAIN_NAME}`

- **Vikunja** (`Home/Vikunja/vikunja.yml`) - Task management
  - Self-hosted task hub (Todoist/Trello alternative)
  - CalDAV support for iOS Reminders sync
  - PostgreSQL backend
  - MCP service integration available
  - Dashboard at `tasks.${DOMAIN_NAME}`

- **HomeBox** (`Management/HomeBox/homebox.yml`) - Home inventory management
  - Track household items and their locations
  - Asset management and organization
  - Dashboard at `homebox.${DOMAIN_NAME}`

- **Kiwix** (`Tools/Kiwix/kiwix.yml`) - Offline Wikipedia mirror
  - Wikipedia and documentation archives
  - Read-only ZIM file mount
  - Dashboard at `wikipedia.${DOMAIN_NAME}`

- **Doomsday Library** (`Home/Doomsday/library.yml`) - Offline content library
  - Additional offline content archives
  - Kiwix-serve for ZIM files
  - Dashboard at `library.${DOMAIN_NAME}`

---

## HaC-NonCritical Services

Services running on **hac-noncritical** (non-critical host). Can restart without affecting home automation.

**Storage layout on hac-noncritical:**

- Per-service persistent data directories (local to host)

### Networking, Proxy & VPN

- **Traefik** (`Networking/Proxy/proxy.yml`) - Non-critical reverse proxy
  - Dashboard at `hac-noncritical-traefik.${DOMAIN_NAME}`

- **Gluetun** (via `Networking/Torrent/torrent.yml`) - VPN/proxy container
  - Network namespace for torrent services
  - Supports multiple VPN providers

### Media Stack (Entertainment)

#### Request & Discovery

- **Overseerr** (`Media/overseerr/overseerr.yml`) - Media request platform
  - User-friendly movie/TV show requests
  - Integrates with Radarr/Sonarr

#### Indexing & Search

- **Prowlarr** (`Media/prowlarr/prowlarr.yml`) - Torrent indexer manager
  - Torrent site management and search
  - Unified interface for Radarr/Sonarr

- **Profilarr** (`Media/profilarr/profilarr.yml`) - Profile management
  - Radarr/Sonarr quality profile sync

#### Media Download & Organization

- **Radarr** (`Media/radarr/radarr.yml`) - Movie management
  - Automated movie downloads
  - Library organization and monitoring

- **Sonarr** (`Media/Sonarr/sonarr.yml`) - TV show management
  - Episode tracking and downloading
  - Season monitoring

- **Lidarr** (`Media/lidarr/lidarr.yml`) - Music management
  - Music library automation
  - Artist and album monitoring

- **Readarr** (`Media/readarr/readarr.yml`) - Book management
  - eBook and audiobook tracking

#### Download Clients

- **qBittorrent** (via `Networking/Torrent/torrent.yml`) - Torrent client
  - Download management
  - Behind Gluetun VPN tunnel

- **NZBGet** (via `Networking/Torrent/torrent.yml`) - Usenet client
  - Usenet download support

#### Utilities

- **FlareSolverr** (`Media/flaresolverr/flaresolverr.yml`) - CloudFlare bypass
  - Resolves CloudFlare-protected indexer sites
  - API for Radarr/Sonarr integration

- **Dispatcharr** (`Media/Dispatcharr/dispatcharr.yml`) - Notification router
  - Routes Radarr/Sonarr notifications

### Photos & Media

- **Immich** (`Media/Immich/immich.yml`) - Photo and video management
  - Self-hosted Google Photos alternative
  - Machine learning for facial recognition and search
  - PostgreSQL (with pgvecto.rs) + Valkey backends
  - Dashboard at `media.${DOMAIN_NAME}`

### Books & Audiobooks

- **Audiobookshelf** (`Media/Books/ebook.yml`) - Audiobook and podcast server
  - Self-hosted audiobook streaming
  - Podcast management
  - Dashboard at `audiobooks.${DOMAIN_NAME}`

- **Kavita** (`Media/Books/ebook.yml`) - eBook and comic reader
  - Digital library for books, comics, manga
  - Web-based reader interface
  - Dashboard at `kavita.${DOMAIN_NAME}`

### Media Center

- **Plex** (`Media/Plex/plex.yml`) - Media streaming server
  - Movies, TV shows, music streaming
  - Dashboard at `plex.${DOMAIN_NAME}`
  - Mounts media from `/mnt/Pool01/data/`

### Automation & AI

- **Open WebUI** (`Automation/AI/openwebui.yml`) - LLM interface
  - Chat interface for Ollama
  - Dashboard at `chat.${DOMAIN_NAME}`

- **Price Tracker** (`Automation/pricetracker.yml`) - eCommerce monitoring
  - Price tracking and alerts

### Tools

- **IT-Tools** (`Tools/IT-Tools/it-tools.yml`) - Developer utilities
  - Collection of handy developer tools
  - Dashboard at `it-tools.${DOMAIN_NAME}`

- **SearXNG** (`Tools/SearX/searx.yml`) - Privacy-focused metasearch
  - Self-hosted search engine
  - Aggregates results from multiple sources
  - Dashboard at `search.${DOMAIN_NAME}`

- **Stirling-PDF** (`Tools/Stirling-PDF/stirling-pdf.yml`) - PDF toolkit
  - PDF manipulation and conversion
  - Merge, split, compress, OCR
  - Dashboard at `pdf.${DOMAIN_NAME}`

- **Hawser** (`Tools/Hawser/hawser.yml`) - Docker agent for Dockhand
  - Remote Docker agent that exposes the Docker socket over HTTPS (port 2376)
  - Enables Dockhand (on hac-critical) to manage stacks on hac-noncritical

- **DocSight** (`Tools/DocSight/docsight.yml`) - Cable modem monitoring
  - Polls cable modem DOCSIS stats and publishes to MQTT
  - Home Assistant auto-discovery via MQTT
  - Dashboard at `docsight.${DOMAIN_NAME}`

- **Speedtest** (`Tools/Speedtest/speedtest.yml`) - LAN speed test server
  - In-network speed testing via OpenSpeedTest
  - Dashboard at `speedtest.${DOMAIN_NAME}`

- **MCP Gateway** (`Automation/AI/MCPGateway/mcpgateway.yml`) - Model Context Protocol hub
  - IBM ContextForge: central gateway for all MCP servers
  - PostgreSQL + Redis backends
  - Dashboard at `mcp.${DOMAIN_NAME}`

- **MCP Servers** (`Automation/AI/MCPGateway/mcpservers.yml`) - stdio-to-HTTP MCP bridges
  - Vikunja MCP (task management via `@democratize-technology/vikunja-mcp`)
  - HomeBox MCP (inventory management, custom build)
  - N8N MCP (workflow management via `ghcr.io/czlonkowski/n8n-mcp`)
  - Uses supergateway to expose stdio servers as Streamable HTTP
  - Home Assistant MCP served natively by HA at `/api/mcp`

- **Docker Socket Proxy** (`Tools/DockerSocketProxy/docker-socket-proxy.yml`) - Secure Docker API access
  - Non-critical instance for Traefik and monitoring

### Security

- **Crowdsec** (`Security/Crowdsec/crowdsec.yml`) - Threat detection
  - IDS/crowdsourced security
  - Log analysis and blocking

- **Wazuh** (`Security/security.yaml`) - SIEM and threat detection
  - Wazuh Manager, Indexer (OpenSearch), and Dashboard
  - Agent-based endpoint monitoring
  - Syslog ingestion and log analysis
  - 30-day index retention via ISM policy
  - Dashboard at `wazuh.${DOMAIN_NAME}`

---

## Deployment

### Deployment Hosts

All services deploy via Forgejo CI/CD workflows in `.forgejo/workflows/`. Workflows select the appropriate runner based on service location:

**Critical services** → `runs-on: docker-critical`
**Non-critical services** → `runs-on: docker-noncritical`

| Service | Workflow | Host | Trigger |
| --------- | ---------- | ------------- | ----------------------------------------- |
| Authentik | `deploy-authentik.yml` | hac-critical | Push to `Docker-Critical/Auth/**` |
| Vaultwarden | `deploy-vaultwarden.yml` | hac-critical | Push to `Docker-Critical/Auth/vaultwarden.yml` |
| Traefik (Critical) | `deploy-traefik-critical.yml` | hac-critical | Push to `Docker-Critical/Networking/Proxy/**` |
| Traefik (NonCritical) | `deploy-traefik-noncritical.yml` | hac-noncritical | Push to `Docker-NonCritical/Networking/Proxy/**` |
| Home Assistant | `deploy-homeassistant.yml` | hac-critical | Push to `Docker-Critical/Home/HomeAssistant/**` |
| ESPHome | (included in HA) | hac-critical | Push to `Docker-Critical/Home/HomeAssistant/**` |
| RTL-SDR | `deploy-rtl-sdr.yml` | hac-critical | Push to `Docker-Critical/Home/RTL-SDR/**` |
| Music Assistant | `deploy-musicassistant.yml` | hac-critical | Push to `Docker-Critical/Home/MusicAssistant/**` |
| Govee2MQTT | `deploy-govee2mqtt.yml` | hac-critical | Push to `Docker-Critical/Home/Govee2MQTT/**` |
| NUT | `deploy-nut.yml` | hac-critical | Push to `Docker-Critical/Home/NUT/**` |
| Whisper | `deploy-whisper.yml` | hac-critical | Push to `Docker-Critical/Home/Whisper/**` |
| InfluxDB | `deploy-influxdb.yml` | hac-critical | Push to `Docker-Critical/Tools/InfluxDB/**` |
| N8N | `deploy-n8n.yml` | hac-critical | Push to `Docker-Critical/Tools/N8N/**` |
| NetBox | `deploy-netbox.yml` | hac-critical | Push to `Docker-Critical/Home/NetBox/**` |
| Norish | `deploy-norish.yml` | hac-critical | Push to `Docker-Critical/Home/Cooking/**` |
| KaraKeep | `deploy-karakeep.yml` | hac-critical | Push to `Docker-Critical/Home/KaraKeep/**` |
| HomeBox | `deploy-homebox.yml` | hac-critical | Push to `Docker-Critical/Management/HomeBox/**` |
| Vikunja | `deploy-vikunja.yml` | hac-critical | Push to `Docker-Critical/Home/Vikunja/**` |
| Kiwix | `deploy-kiwix.yml` | hac-critical | Push to `Docker-Critical/Tools/Kiwix/**` |
| Forgejo | `deploy-forgejo.yml` | hac-critical | Push to `Docker-Critical/Management/Git*/**` |
| Omada | `deploy-omada.yml` | hac-critical | Push to `Docker-Critical/Networking/Omada/**` |
| SMTP Relay | `deploy-smtprelay.yml` | hac-critical | Push to `Docker-Critical/Networking/Mail/**` |
| Cloudflared | `deploy-cloudflared.yml` | hac-critical | Push to `Docker-Critical/Networking/Cloudflared/**` |
| Docker Socket Proxy (Critical) | `deploy-docker-socket-proxy-critical.yml` | hac-critical | Push to `Docker-Critical/Tools/DockerSocketProxy/**` |
| Dockhand | `deploy-dockhand.yml` | hac-critical | Push to `Docker-Critical/Tools/Dockhand/**` |
| Outline | `deploy-outline.yml` | hac-critical | Push to `Docker-Critical/Tools/Outline/**` |
| Uptime Kuma | `deploy-uptime-kuma.yml` | hac-critical | Push to `Docker-Critical/Management/UptimeKuma/**` |
| Plex | `deploy-plex.yml` | hac-noncritical | Push to `Docker-NonCritical/Media/Plex/**` |
| Immich | `deploy-immich.yml` | hac-noncritical | Push to `Docker-NonCritical/Media/Immich/**` |
| Radarr | `deploy-radarr.yml` | hac-noncritical | Push to `Docker-NonCritical/Media/radarr/**` |
| Sonarr | `deploy-sonarr.yml` | hac-noncritical | Push to `Docker-NonCritical/Media/Sonarr/**` |
| Lidarr | `deploy-lidarr.yml` | hac-noncritical | Push to `Docker-NonCritical/Media/lidarr/**` |
| Readarr | `deploy-readarr.yml` | hac-noncritical | Push to `Docker-NonCritical/Media/readarr/**` |
| Overseerr | `deploy-overseerr.yml` | hac-noncritical | Push to `Docker-NonCritical/Media/overseerr/**` |
| Prowlarr | `deploy-prowlarr.yml` | hac-noncritical | Push to `Docker-NonCritical/Media/prowlarr/**` |
| Profilarr | `deploy-profilarr.yml` | hac-noncritical | Push to `Docker-NonCritical/Media/profilarr/**` |
| Dispatcharr | `deploy-dispatcharr.yml` | hac-noncritical | Push to `Docker-NonCritical/Media/Dispatcharr/**` |
| FlareSolverr | `deploy-flaresolverr.yml` | hac-noncritical | Push to `Docker-NonCritical/Media/flaresolverr/**` |
| Books (ebook) | `deploy-ebook.yml` | hac-noncritical | Push to `Docker-NonCritical/Media/Books/**` |
| Torrent Stack | `deploy-torrent.yml` | hac-noncritical | Push to `Docker-NonCritical/Networking/Torrent/**` |
| Open WebUI | `deploy-openwebui-noncritical.yml` | hac-noncritical | Push to `Docker-NonCritical/Automation/AI/**` |
| IT-Tools | `deploy-it-tools.yml` | hac-noncritical | Push to `Docker-NonCritical/Tools/IT-Tools/**` |
| SearXNG | `deploy-searx.yml` | hac-noncritical | Push to `Docker-NonCritical/Tools/SearX/**` |
| Stirling-PDF | `deploy-stirling-pdf.yml` | hac-noncritical | Push to `Docker-NonCritical/Tools/Stirling-PDF/**` |
| MCP Gateway | `deploy-mcpgateway.yml` | hac-noncritical | Push to `Docker-NonCritical/Automation/AI/MCPGateway/mcpgateway.yml` |
| MCP Servers | `deploy-mcpservers.yml` | hac-noncritical | Push to `Docker-NonCritical/Automation/AI/MCPGateway/mcpservers.yml` or `mcp-servers/**` |
| Docker Socket Proxy (NC) | `deploy-docker-socket-proxy-noncritical.yml` | hac-noncritical | Push to `Docker-NonCritical/Tools/DockerSocketProxy/**` |
| Hawser | `deploy-hawser.yml` | hac-noncritical | Push to `Docker-NonCritical/Tools/Hawser/**` |
| DocSight | `deploy-docsight.yml` | hac-noncritical | Push to `Docker-NonCritical/Tools/DocSight/**` |
| Speedtest | `deploy-speedtest.yml` | hac-noncritical | Push to `Docker-NonCritical/Tools/Speedtest/speedtest.yml` |
| Wazuh | `deploy-wazuh.yml` | hac-noncritical | Push to `Docker-NonCritical/Security/**` |
| CrowdSec | `deploy-crowdsec.yml` | hac-noncritical | Push to `Docker-NonCritical/Security/Crowdsec/**` |

**Maintenance workflows:**

| Workflow | Purpose |
| ----------------------- | -------------------------------------------- |
| `check-updates-critical.yml` | Check for container image updates (critical) |
| `check-updates-noncritical.yml` | Check for container image updates (non-critical) |
| `apply-updates-critical.yml` | Apply container image updates (critical) |
| `apply-updates-noncritical.yml` | Apply container image updates (non-critical) |
| `mirror-to-github.yml` | Mirror repository to GitHub |

### Required Forgejo Variables

> See [Forgejo Variables Reference](https://docs.u-acres.com/doc/forgejo-variables-reference-nvgshbtzQK) in Outline for full details and troubleshooting.

Global variables (set in repository settings):

- `DOMAIN_NAME` - Primary domain (e.g., `example.com`)
- `CERTRESOLVER` - Certificate resolver (default: `cloudflare`)
- `PUID` / `PGID` - User/group IDs for linuxserver images (default: `568`)
- `TZ` - Timezone (default: `America/Chicago`)
- `MQTT_HOST`, `MQTT_PORT`, `MQTT_USER` - MQTT broker details
- `POSTGRES_USER`, `POSTGRES_DB` - PostgreSQL defaults
- `OLLAMA_BASE_URL` - Ollama LLM server URL
- `INFERENCE_*` - Model selection for KaraKeep AI features
- `INFLUXDB_ADMIN_USER` - InfluxDB admin username (default: `admin`)
- `VIKUNJA_URL` - Vikunja base URL (for MCP server)
- `N8N_URL` - N8N base URL (for n8n-mcp server)
- `HOMEBOX_URL` - HomeBox base URL (for MCP server)
- `DOCSIGHT_LOG_LEVEL` - DocSight log level (default: `INFO`)
- `DOCSIGHT_AUDIT_JSON` - DocSight JSON audit log (default: `1`)
- `DOCSIGHT_MQTT_TOPIC_PREFIX` - DocSight MQTT topic prefix (default: `docsight`)
- `DOCSIGHT_MQTT_DISCOVERY_PREFIX` - DocSight HA discovery prefix (default: `homeassistant`)

### Required Forgejo Secrets

Encrypted secrets (set in repository settings):

- `CLOUDFLARE_EMAIL`, `CLOUDFLARE_DNS_API_TOKEN` - Cloudflare DNS for ACME
- `CLOUDFLARE_ZONE_API_TOKEN` - Zone API token
- `LETS_ENCRYPT_EMAIL` - Let's Encrypt contact
- `AUTHENTIK_SECRET_KEY` - Authentik secret key
- `AUTHENTIK_DB_PASSWORD` - Authentik PostgreSQL password
- `GIT_DB_PASSWORD` - Forgejo PostgreSQL password
- `NETBOX_DB_PASSWORD`, `NETBOX_SECRET_KEY` - NetBox secrets
- `PLEX_CLAIM` - Plex initial setup token
- `MQTT_PASSWORD` - MQTT broker password
- `PROFILARR_PAT` - Profilarr API token
- `SMTP_*` - SMTP relay credentials
- `INFLUXDB_ADMIN_PASSWORD` - InfluxDB admin password
- `IMMICH_DB_PASSWORD` - Immich PostgreSQL password
- `WAZUH_INDEXER_PASSWORD` - Wazuh OpenSearch password
- `WAZUH_API_PASSWORD` - Wazuh API password
- `VIKUNJA_DB_PASSWORD` - Vikunja PostgreSQL password
- `VIKUNJA_JWT_SECRET` - Vikunja JWT signing secret
- `VIKUNJA_API_TOKEN` - Vikunja API token (for MCP + N8N integrations)
- `VAULTWARDEN_DB_PASSWORD` - Vaultwarden PostgreSQL password
- `VAULTWARDEN_ADMIN_TOKEN` - Vaultwarden admin panel token
- `MCP_DB_PASSWORD` - MCP Gateway PostgreSQL password
- `N8N_API_KEY` - N8N API key (for n8n-mcp server)
- `N8N_MCP_AUTH_TOKEN` - Auth token for n8n-mcp HTTP endpoint
- `HOMEBOX_EMAIL` - HomeBox login email (for MCP server)
- `HOMEBOX_PASSWORD` - HomeBox login password (for MCP server)
- `DOCKHAND_ENCRYPTION_KEY` - Dockhand encryption key for stored credentials
- `OUTLINE_SECRET_KEY` - Outline session encryption key (64-char hex: `openssl rand -hex 32`)
- `OUTLINE_UTILS_SECRET` - Outline utility secret (64-char hex: `openssl rand -hex 32`)
- `OUTLINE_DB_PASSWORD` - Outline PostgreSQL password
- `OUTLINE_MINIO_ACCESS_KEY` - MinIO root user (access key) for Outline storage
- `OUTLINE_MINIO_SECRET_KEY` - MinIO root password (secret key) for Outline storage
- `OUTLINE_OIDC_CLIENT_ID` - Authentik OAuth2 client ID for Outline
- `OUTLINE_OIDC_CLIENT_SECRET` - Authentik OAuth2 client secret for Outline

---

## Data Locations

### Critical Services

Persistent data on primary host (tiered):

```
/srv/                      # NVMe #1 (critical + high IO)
├── authentik/             # Authentik identity provider data and config
├── traefik/               # Reverse proxy config and ACME certs
├── homeassistant/         # HA config and automations
├── avahi/                 # mDNS reflection config
├── vaultwarden/           # Vaultwarden data + Postgres
├── dockhand/              # Dockhand stack data
├── outline/               # Outline wiki data
├── postgres-outline/      # Outline PostgreSQL
├── redis-outline/         # Outline Redis
├── minio-outline/         # Outline MinIO (file attachments)
├── esphome/               # ESPHome device configs
├── rtl-sdr/               # RTL-SDR config and decoded data
├── music-assistant/       # Music Assistant data
├── influxdb/              # Time-series database and config
├── norish/                # Recipe database (app + DB + redis)
├── smtp-relay/            # Postfix spool
├── omada/                 # Controller data
├── vikunja/               # Vikunja files + Postgres
└── git/                   # Forgejo repositories, data + Postgres

/mnt/nvme-appdata/         # NVMe #2 (appdata/search/AI)
├── netbox/                # IPAM app, Postgres, Redis, theme
├── homebox/               # HomeBox data/config
└── karakeep/              # KaraKeep data + Meilisearch

/mnt/hdd/                  # HDD (bulk/logs/archives)
├── logs/omada             # Omada logs
├── logs/smtp-relay        # Postfix logs
├── kiwix/zim              # Kiwix ZIM archives
└── backups/               # Cold backups/archives
```

### Non-Critical Services

Persistent data on docker-noncritical:

```
/srv/                      # High IO services
├── immich/                # Immich Postgres + ML model cache
├── openwebui_data/        # Open WebUI data
└── wazuh/                 # Wazuh indexer data + dashboard config

/mnt/data/                 # NFS/shared storage
├── family/upload/         # Immich photo uploads
├── family/external/       # Immich external libraries
└── wazuh/archives/        # Wazuh log archives

/var/lib/docker/volumes/   # Docker-managed volumes
[per-service mounts]       # Absolute paths per compose file
```

### Media (Shared Storage)

```
/mnt/Pool01/data/media/
├── movies/               # Radarr downloads
├── tv/                   # Sonarr downloads
├── music/                # Lidarr downloads
└── books/                # Readarr downloads
```

---

## Migration

See [MIGRATION.md](Docker-Critical/MIGRATION.md) for detailed instructions on migrating services from TrueNAS to Home Assistant.

**Quick start:**

```bash
# Run migration script
ssh user@homeassistant
chmod +x migrate-to-homeassistant.sh
sudo ./migrate-to-homeassistant.sh
```

---

## Development & Customization

### Adding a New Service

1. **Create compose file** in appropriate folder:

   ```yaml
   Docker-Critical/Home/MyService/myservice.yml
   ```

2. **Define service** with:
   - Network specification (homeproxy, mediaproxy, etc.)
   - Environment variables (use `${VAR}` placeholders)
   - Traefik labels for routing
   - Volume mounts with absolute paths
   - Health checks

3. **Create deployment workflow** in `.forgejo/workflows/`:

   ```yaml
   name: Deploy MyService
   on:
     push:
       paths:
         - "Docker-Critical/Home/MyService/**"
         - ".forgejo/workflows/deploy-myservice.yml"
   ```

4. **Test locally**:

   ```bash
   docker compose -p myservice -f myservice.yml up -d
   ```

5. **Commit and push** - workflow triggers automatically

### Modifying Existing Service

- Edit the `.yml` file
- Update workflow if paths change
- Commit to main branch
- Workflow automatically redeploys with checksum validation

### Configuration Best Practices

- Never hardcode secrets (use `${SECRET_NAME}`)
- Use external networks (no inline network creation)
- Set `restart: unless-stopped` policy
- Include health checks for critical services
- Traefik labels always for HTTP services
- HA monitoring labels (`ha.monitor`, `ha.category`, `ha.compose-file`, `ha.service-name`) for Home Assistant tracking — see [Docker Container Monitoring](https://docs.u-acres.com/doc/docker-container-monitoring-LGL1OrDfm8)
- Uptime Kuma at `uptime.${DOMAIN_NAME}` monitors all HTTP/TCP endpoints — configure monitors in the UI after adding a new service

---

## Service Dependencies

```
Traefik (Critical)
├── Authentik (identity provider)
├── Omada (network dashboard)
├── Home Assistant (home automation hub)
│   ├── ESPHome (device management)
│   ├── RTL-SDR (wireless sensors)
│   └── Govee2MQTT (Govee devices)
├── InfluxDB (metrics and historical data)
├── Music Assistant (music server and players)
├── NetBox (infrastructure docs)
├── Norish (recipes)
├── KaraKeep (bookmarks)
├── HomeBox (inventory)
├── Vikunja (task management)
└── Forgejo (git/CI)

Traefik (NonCritical)
├── Plex (media streaming)
├── Immich (photo management)
├── Radarr/Sonarr/etc (media management)
├── Overseerr (media requests)
├── Open WebUI (LLM chat)
├── Wazuh (SIEM)
├── MCP Gateway (MCP hub)
└── Tools (IT-Tools, SearXNG, Stirling-PDF)
```

---

## Security Notes

- **Split Horizon DNS:** Not needed - Unbound on OpnSense provides local DNS overrides
- **External Access:** Via Cloudflare Tunnel to avoid port forwarding
- **Authentication:** Authentik protects sensitive services
- **ACME:** Individual certificates per subdomain (no wildcard)
- **SSH:** Via Tailscale network for secure access
- **SIEM:** Wazuh for endpoint monitoring and log analysis

---

## Troubleshooting

### Service won't start

```bash
# Check logs
docker logs <container-name>

# Verify compose file
docker compose -f <service>.yml config

# Check network exists
docker network ls | grep proxy
```

### Traefik routing issues

```bash
# Check router config
docker logs traefik | grep router

# Verify service labels
docker inspect <service> | grep traefik
```

### Permissions errors

```bash
# Verify ownership
ls -la /srv/<service>/

# Fix permissions
sudo chown -R 568:568 /srv/<service>/
```

---

## License & Attribution

Personal home automation infrastructure. Configuration patterns based on best practices for self-hosted services.

---

**Last Updated:** March 19, 2026
**Maintainer:** Nicholas Underwood
