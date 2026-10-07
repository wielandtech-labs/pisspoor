"""Health endpoints.

Two endpoints on purpose, because they answer different questions:

- ``/healthz`` is liveness — the process is up and can serve a request. It must
  not touch the database, or a brief Postgres blip would make Kubernetes kill
  otherwise-healthy pods.
- ``/readyz`` is readiness — this pod can serve *traffic*, which does require
  the database. A failure here pulls the pod out of the Service endpoints
  without restarting it.
"""

from django.db import connection
from django.http import HttpRequest, JsonResponse


def healthz(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


def readyz(_request: HttpRequest) -> JsonResponse:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # noqa: BLE001 - report any backend failure as not-ready
        return JsonResponse({"status": "unavailable", "database": str(exc)}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})


class HealthCheckMiddleware:
    """Serve the health endpoints before anything inspects the Host header.

    Kubernetes probes reach a pod by its IP, so ``HTTP_HOST`` is something like
    ``10.42.0.202:8080``. That is never in ``ALLOWED_HOSTS``, so Django raises
    ``DisallowedHost`` and returns 400 — which fails the liveness probe and
    crashloops a pod that is otherwise perfectly healthy.

    Widening ``ALLOWED_HOSTS`` to cover pod IPs would weaken a real security
    control, and per-environment probe ``Host`` headers would have to be kept in
    sync in three places (dev, prod, and the review-app registry). Health
    endpoints are infrastructure rather than tenant-routed content, so they
    answer regardless of Host. This middleware must stay **first** in
    ``MIDDLEWARE`` so it runs before anything calls ``request.get_host()``.
    """

    PATHS = {"/healthz": healthz, "/readyz": readyz}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        view = self.PATHS.get(request.path)
        if view is not None:
            return view(request)
        return self.get_response(request)
