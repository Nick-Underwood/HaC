# Local Mail Stack — docker-mailserver + Roundcube (SHTF-proof)

Self-contained LAN mail server for **authentik password-reset / invite /
verification** emails. Delivers to REAL IMAP inboxes users open in any mail
client or in the Roundcube webmail UI. Uses **no internet relay** and **no
external DNS/MX/SPF**, so it keeps working when the WAN is down.

> This is SEPARATE from `Postfix.yml` (the peacetime internet relay to Mailtrap).
> Postfix dies at SHTF; this stack doesn't. Keep Postfix for outbound
> notifications that need to reach the internet; use this stack for authentik's
> local user mail.

## Topology

```
authentik (docker-critical .51, authnet)
    │  SMTP port 25, no auth (PERMIT_DOCKER=connected-networks)
    ▼
mailserver (docker-mailserver, authnet)  ──►  IMAP/IMAPS inboxes
    │                                            │
    │                                            ▼
    └──────────────────────────────►  Roundcube webmail (authnet + traefik_proxy)
                                          • LAN raw:  http://<host>:8082
                                          • Peacetime: https://mail.<DOMAIN_NAME>
```

Both stacks run on **docker-critical (.51)** so a password reset works even
with the WAN cut (single-host resilience). authentik reaches the MTA at the
Docker DNS name `mailserver:25`.

## Files

| File | Purpose |
|------|---------|
| `mailserver.yml` | Compose: docker-mailserver + MariaDB + Roundcube |
| `.gitignore` | Keeps `./secrets/*` and `/docker-data/` out of git |
| `.forgejo/workflows/deploy-mailserver.yml` | Builds secrets, deploys, provisions `admin@uacres.local`, verifies endpoints |

## Required Forgejo repo secrets (set once)

| Secret | Value |
|--------|-------|
| `MAILSERVER_ADMIN_PASSWORD` | App password for `admin@uacres.local` (used by the deploy workflow's `setup email add`) |
| `ROUNDCUBE_DB_PASSWORD` | MariaDB user `roundcube` password |
| `ROUNDCUBE_DB_ROOT_PASSWORD` | MariaDB root password |
| `ROUNDCUBE_DES_KEY` | **exactly 24 chars** (Roundcube session/cookie crypto) |

Generate the DES key once, e.g. `openssl rand -hex 12` (12 bytes = 24 hex chars).

## Deploy

Push to `main` (or run `deploy-mailserver` manually in Forgejo Actions). The
workflow writes secrets, prepares `/docker-data/dms/*` and `/docker-data/roundcube/db`,
deploys, then idempotently creates `admin@uacres.local` and checks SMTP/IMAP/HTTP.

## Authentik follow-up (GUI, not in git)

The SMTP connection is wired in `Authentik.yml` (host `mailserver`, port 25,
no TLS, from `noreply@uacres.local`). After the mail stack is up:

1. **System → Settings → Email** and confirm the values match (they're
   pre-set via env, but verify):
   - Host: `mailserver`, Port: `25`, no auth, no TLS/SSL
   - From: `noreply@uacres.local`
2. Click **Send Test Email** → read it in Roundcube (`admin@uacres.local`) or any
   IMAP client pointed at the mailserver.
3. **Recovery keys (true offline fallback):** create a recovery-key stage and
   attach it to your login flow so users can regain access with a printed PDF
   even if mail is unavailable. This is the only path that needs *zero*
   infrastructure.

## Create user mailboxes

```sh
docker exec -it mailserver setup email add user@uacres.local '<password>'
docker exec -it mailserver setup email list
```

## Notes / gotchas

- **Cert:** `SSL_TYPE=self-signed` (no public DNS for this host). Mail clients
  must trust the self-signed cert explicitly or use the LAN port 143/587 with
  "accept invalid certs".
- **Spam/AV off** (`ENABLE_SPAMD=0`, `ENABLE_CLAMAV=0`) — local trusted LAN only.
- **fail2ban off** — avoids the `NET_ADMIN` capability requirement on a trusted LAN.
- **Domain `uacres.local`** is internal-only; nothing here is routable externally.
- If you later want peacetime outbound too, leave Postfix as the relay and keep
  this stack purely for authentik local delivery.
