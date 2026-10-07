"""Keep the back office off the public internet."""

from __future__ import annotations

from django.conf import settings
from django.http import Http404

# Everything only staff use. Venue boards (/b/...) stay public on purpose:
# venue staff open them from a secret link, not from the tailnet.
PRIVATE_PREFIXES = ("/admin", "/print/")


class AdminHostMiddleware:
    """404 the back office on every host except ADMIN_HOSTS.

    Prod sets ADMIN_HOSTS to the Tailscale ingress hostname, whose traffic
    reaches the Service straight from the tailnet proxy and never through the
    public Traefik route; public Traefik has no router for that hostname, so a
    forged Host header from the internet goes nowhere. A 404 rather than a 403
    so the public site doesn't advertise that a login page exists.

    Unset (local dev, CI, review apps) means no restriction.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        allowed = settings.ADMIN_HOSTS
        if (
            allowed
            and request.path.startswith(PRIVATE_PREFIXES)
            and request.get_host().split(":")[0].lower() not in allowed
        ):
            raise Http404
        return self.get_response(request)
