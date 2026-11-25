"""Host-level gates: one canonical origin, and the back office off the public internet."""

from __future__ import annotations

from django.conf import settings
from django.http import Http404, HttpResponsePermanentRedirect

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


class WwwRedirectMiddleware:
    """Send www.<domain> to <domain> with path and query, so search sees one site.

    A 308, not a 301, so a form POSTed to www keeps its method and body. The
    target is the apex of the host that was asked for (get_host() has already
    checked it against ALLOWED_HOSTS), so this can't redirect off-site and works
    for .com once it's live without a config change. Printed QR codes use the
    apex PUBLIC_BASE_URL, so no sticker depends on this.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host()
        if host.lower().startswith("www."):
            response = HttpResponsePermanentRedirect(f"https://{host[4:]}{request.get_full_path()}")
            response.status_code = 308
            return response
        return self.get_response(request)


class ContentSecurityPolicyMiddleware:
    """Send settings.CONTENT_SECURITY_POLICY_REPORT_ONLY on every response.

    Report-Only: browsers log violations in the console and block nothing.
    A view that sets its own Report-Only header keeps that value.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        policy = settings.CONTENT_SECURITY_POLICY_REPORT_ONLY
        if policy:
            response.headers.setdefault("Content-Security-Policy-Report-Only", policy)
        return response
