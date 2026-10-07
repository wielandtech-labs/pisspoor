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

The restroom QR ad network behind **pisspooridea.lol**. Homelab slug `pisspoor`;
image `ghcr.io/wielandtech-labs/pisspoor`; manifests in `w_homelab` under
`clusters/{dev,prod}/apps/pisspoor/`.

## Configuration

All config is environment variables; see README.md.

## Health endpoints

`/healthz` is liveness and **must not touch the database**. `/readyz` is
readiness and does check it. Both are served by `core.views.HealthCheckMiddleware`
before the ALLOWED_HOSTS check, because probes arrive with the pod IP as Host.
There is a test asserting liveness stays database-free; keep it.
