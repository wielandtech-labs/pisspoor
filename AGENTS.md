# AGENTS.md — wielandtech-labs app repo conventions

This repository builds a container image that deploys to the K3s homelab via
GitOps. The deployment manifests do NOT live here — they live in
`wielandtech-labs/w_homelab` under `clusters/{dev,qa,prod}/apps/<app>/`.

## Image tags drive deployments

`.github/workflows/docker.yaml` publishes to `ghcr.io/wielandtech-labs/<repo>`:

| Event | Tag | Effect |
|---|---|---|
| Push to `main` | `YYYYMMDD-HHMMSS-<shortsha>` | Flux Image Automation deploys it to **prod** (via a fast-forwarded PR on `flux/image-updates/prod`) |
| Push to any other branch | `dev-YYYYMMDD-HHMMSS-<shortsha>` | Flux Image Automation deploys it to **dev** (via `flux/image-updates/dev`) |
| Same-repo pull request | `pr-<number>-<shortsha>` | A per-PR **review app** at `https://pr-<number>-<app>.review.wielandtech.com` |

Never change these tag formats — Flux ImagePolicies and the review-app
automation in w_homelab parse them.

**A push to `main` is a production deploy.** Treat `main` accordingly: merge
only after the change was validated on a review app or in dev/qa.

## Promotion ladder

1. Open a PR → review app deploys automatically (merge the generated
   `chore(review): deploy ...` PR in w_homelab).
2. Merge or push a branch → dev environment tracks the newest `dev-*` tag.
3. Promote dev → QA with the w_homelab promotion workflow:
   `gh workflow run promote.yaml -R wielandtech-labs/w_homelab -f app=<app> -f to_env=qa`
4. Merge to `main` → prod tag published → Flux deploys; post-merge
   verification in w_homelab gates the result.

Rollback = revert the environment's HelmRelease image tag in w_homelab via PR.

## Build infrastructure

- Jobs run on the shared org runner pool: `runs-on: homelab-dind`.
- Docker builds use buildx `driver: remote` against the in-cluster buildkitd
  (mTLS certs are mounted at `/etc/buildkit/certs`); there is no local Docker
  daemon, so `docker run`/service containers do NOT work on this pool.
- Registry layer cache lives at `<image>:buildcache`.

## Requirements for a new repo

1. Copy `docker.yaml`, set `APP_NAME` and `IMAGE` in its `env` block.
2. Add a `Dockerfile` at the repo root (or set `context`/`file` in the build step).
3. App repos are **public** by convention, so the org-level
   `HOMELAB_REVIEW_APP_TOKEN` secret is visible to their workflows. If a
   repo must stay private, set the token per-repo instead
   (`gh secret set HOMELAB_REVIEW_APP_TOKEN --repo wielandtech-labs/<repo>`)
   — the Free plan hides org secrets from private repos.
4. Onboard the app in w_homelab with the `new-app` skill (or
   `.github/scripts/scaffold_app.py`) so dev/prod manifests, Flux image
   automation, and the review-app registry entry exist.

---

# This app: `pisspoor`

The restroom QR ad network behind **pisspooridea.com** (the agency: venues and
advertisers) and **pisspooridea.lol** (the playful guerrilla front door). One
app, two faces chosen by Host (`marketing.sites.is_fun_site`, `FUN_HOSTS`);
short codes resolve on both. Homelab slug `pisspoor`;
image `ghcr.io/wielandtech-labs/pisspoor`; manifests in `w_homelab` under
`clusters/{dev,prod}/apps/pisspoor/`.

## Shape

One Django service. Apps: `venues/` (Venue, Placement = one physical sticker,
print artwork), `scans/` (short links, landing page, Scan, RevenuePeriod,
payout math), `feedback/` (ratings, maintenance requests, venue board),
`ads/` (sponsor campaigns, clicks), `marketing/` (homepage, leads, privacy).
Back office is Django admin.

## Rules that are not negotiable

- **No contract, no stickers.** Print views and the admin print action refuse
  any venue without `agreement_signed_on`. Do not add a bypass.
- **A short code is permanent.** It is printed on a sticker on a wall. Codes are
  generated once (`editable=False`) and never reused; deactivate a placement
  instead of deleting or re-coding it. `PUBLIC_BASE_URL` is baked into every
  printed QR the same way: prod points at `https://pisspooridea.com` and must
  not change once stickers are out. (It moved from `.lol` to `.com` on
  2026-10-07, before any venue sticker was printed. `.lol` must keep resolving
  short codes regardless.)
- **Short codes share the URL root** (`/<code>`). `scans.urls` is included
  last, and any fixed route whose path could match the code pattern
  (`[2-9a-z minus confusables]{6}`) must be added to `RESERVED_CODES`.
- **The back office is tailnet-only in prod.** `/admin` and `/print/` 404 on
  every host but `ADMIN_HOSTS` (prod: the Tailscale ingress hostname
  `pisspoor-admin.iguanodon-alioth.ts.net`). Never point `ADMIN_HOSTS` at
  `pisspoor.k8s.local`: public Traefik routes by Host header, so that LAN name
  is reachable from the internet (tested 2026-10-07), and prod's secure-only
  cookies break login over plain HTTP anyway.
- **Never use `<meta name="referrer" content="no-referrer">`.** Browsers then
  send `Origin: null` on the page's own POSTs and Django's CSRF check 403s
  them; the test client sends no Origin, so only a real browser catches it
  (shipped broken on the venue board, 2026-10-08). Use `same-origin`, which
  still keeps secret-token URLs out of referrers to other sites. Guarded by
  `core/tests/test_referrer_policy.py`.
- **Never store a raw IP.** Visitor identity is `scans.visitors.visitor_hash`
  (HMAC of date + client IP + UA + a random one-day `ppv` cookie). It is per
  day by design; don't widen it. The cookie is load-bearing: public HTTPS
  arrives through the DO droplet's raw TCP passthrough with no PROXY
  protocol, so **every public visitor has the same source IP** (the tunnel).
  `client_ip` reads the *rightmost* X-Forwarded-For entry (the one our proxy
  appended); never the leftmost, which the client controls. Until real client
  IPs reach the cluster, a script that drops cookies counts as a new visitor
  per request, so payout fraud resistance is weak; check the admin's scan
  list for implausible spikes before paying out.
- **Payouts reconcile exactly.** `scans.payouts.split_revenue` rounds venue
  shares down and gives the remainder to the house; it is pure and
  table-tested. A unique scan is a distinct (placement, visitor, day), bots
  excluded. Any query that uses `.distinct()` on Scan must call `.order_by()`
  first, because `Scan.Meta.ordering` would otherwise add `created_at` to the
  DISTINCT and make every scan unique (a real bug caught by tests).
- **Every sticker must decode.** The Bullseye punches a target out of the
  middle of a level-H QR code; `venues/tests/test_qr_decodes.py` rasterises
  each design and decodes it with ZXing. Measured limit on the prod URL:
  hole width 0.38 decodes, 0.40 does not; `BULLSEYE_DIAMETER` is 0.32 for
  headroom. Changing artwork, the hole size or `PUBLIC_BASE_URL` length means
  re-running it, and a test print scanned on a real phone before a batch.
- **No ad runs without human approval, and approval is pinned to the link.**
  `Campaign.objects.live()` only returns `status=approved`; status changes
  only via `approve()`/`reject()` (admin actions), and saving an approved
  campaign with a different `target_url` drops it back to pending. Banned and
  launch-restricted categories (drugs, sexual services, weapons, alcohol,
  cannabis, tobacco, gambling) are intentionally absent from
  `Campaign.Category`; adding one is a policy decision, not a code tweak.
  The public rules are `ads/templates/ads/policy.html`; keep them in sync.
- **Political ads:** `approve()` refuses without `paid_for_by` (shown
  verbatim) and `sponsor_contact`; they carry a "Political ad" label, the AI
  disclosure when `ai_generated`, and appear in the public `/political-ads`
  archive with impressions (`Scan.campaign`). They only run at venues with
  `allow_political_ads` (default off). The app checks a disclaimer exists;
  whether its wording satisfies the race's rules is the reviewer's call.
- **The homepage product art is drawn by the print renderers**
  (`venues.printing.preview_sticker`), so marketing never shows a sticker the
  makerspace can't print.

## Configuration

All config is environment variables; see README.md. `ALLOW_DEMO_SEED=1` (set
only by the review-app registry) lets `seed_demo` create demo data and print a
one-time admin password to the pod log.

## Health endpoints

`/healthz` is liveness and **must not touch the database**. `/readyz` is
readiness and does check it. Both are served by `core.views.HealthCheckMiddleware`
before the ALLOWED_HOSTS check, because probes arrive with the pod IP as Host.
There is a test asserting liveness stays database-free; keep it.
