# Multi-stage build, following the w_tech pattern:
# - builder: compiles wheels (build-essential, libpq-dev) into an isolated venv
# - runtime: slim image with only libpq5, no build toolchain
#
# Builds run on the shared homelab-dind runner pool against the in-cluster
# buildkitd, so the pip and apt cache mounts persist on the buildkitd PVC.

# --- stage 1: dependencies ---
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && pip install -r requirements.txt


# --- stage 2: runtime ---
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY . .

# Collect static at build time so the runtime filesystem can stay read-only and
# so a slow first request never blocks the readiness probe.
RUN SECRET_KEY=build-time-only python manage.py collectstatic --noinput

RUN useradd --system --uid 10001 --no-create-home app \
    && chown -R app:app /app
USER 10001

EXPOSE 8080

# --preload shares parsed app code across workers; the SIGTERM default in
# gunicorn 23 already drains gracefully within terminationGracePeriodSeconds.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "2", \
     "--preload", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
