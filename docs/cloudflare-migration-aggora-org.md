# Cloudflare Migration for aggora.org

This runbook prepares Agora for a clean move from `aggora.kolibri-kollektiv.eu` to `aggora.org` behind Cloudflare.

## Target state

- Canonical public domain: `https://aggora.org`
- Optional alias: `https://www.aggora.org`
- Cloudflare proxy enabled for public traffic
- Django accepts both domains during the transition
- `www.aggora.org` redirects permanently to `aggora.org`

## Repo changes already prepared

- `docker-compose.stack.yml` now includes `aggora.org` and `www.aggora.org` in host and CSRF defaults.
- `CanonicalHostMiddleware` redirects `www.aggora.org` to the apex domain when `APP_PUBLIC_URL=https://aggora.org`.
- `README.md` now documents `aggora.org` as the primary production domain.

## Cloudflare checklist

1. Add `aggora.org` to Cloudflare and switch the registrar nameservers to the pair Cloudflare assigns.
2. In `Zero Trust -> Networks -> Tunnels -> <your tunnel> -> Public hostnames`, create:
   - `aggora.org` -> `http://host.docker.internal:18080`
   - `www.aggora.org` -> `http://host.docker.internal:18080`
3. Let Cloudflare create the corresponding proxied DNS records automatically. Avoid keeping competing manual `CNAME` entries for `aggora.org` or `www`.
4. In `SSL/TLS`, use `Full (strict)` once the origin certificate is installed on the server.
5. Create a Cloudflare Origin Certificate for `aggora.org` and `*.aggora.org`.
6. Install that certificate and private key on the reverse proxy serving Agora.
7. Enable `Always Use HTTPS`.
8. Keep `Automatic HTTPS Rewrites` enabled.
9. Optional after the move is stable: add a redirect rule from `aggora.kolibri-kollektiv.eu/*` to `https://aggora.org/$1`.

## Server env cutover

When DNS is ready, update the production env:

```env
APP_PUBLIC_URL="https://aggora.org"
DJANGO_ALLOWED_HOSTS="aggora.org,www.aggora.org,aggora.kolibri-kollektiv.eu,localhost,127.0.0.1"
DJANGO_CSRF_TRUSTED_ORIGINS="https://aggora.org,https://www.aggora.org,https://aggora.kolibri-kollektiv.eu,http://127.0.0.1:18080"
DJANGO_SECURE_SSL_REDIRECT="true"
DJANGO_SESSION_COOKIE_SECURE="true"
DJANGO_CSRF_COOKIE_SECURE="true"
```

Then rebuild and redeploy the web container so the live image includes the canonical-host middleware and the new domain defaults.

## Post-cutover verification

1. `https://aggora.org/healthz/` returns `200`
2. `https://www.aggora.org/` returns `301` to `https://aggora.org/`
3. canonical tags point to `https://aggora.org/...`
4. login, signup, search, community pages, and share links all use the new domain
5. service worker and `manifest.webmanifest` load on the new host

## Official references

- Cloudflare DNS records: https://developers.cloudflare.com/dns/manage-dns-records/how-to/create-dns-records/
- Cloudflare nameservers setup: https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/
- Cloudflare Origin CA certificates: https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/
- Cloudflare encryption modes: https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/
