"""Which front door a request came through: the agency (.com) or the fun site (.lol)."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest


def _host(request: HttpRequest) -> str:
    return request.get_host().split(":")[0].lower()


def is_fun_site(request: HttpRequest) -> bool:
    return _host(request) in settings.FUN_HOSTS


def brand(request: HttpRequest) -> dict[str, object]:
    # The printed brand follows the domain actually in the address bar, not
    # the face being served: .lol can serve the agency site (prod does until
    # pisspooridea.com is registered). Dev and review hosts read as .com.
    return {
        "is_fun_site": is_fun_site(request),
        "brand_tld": "lol" if _host(request).endswith(".lol") else "com",
        "agency_url": settings.AGENCY_URL,
        "operator": settings.OPERATOR_LEGAL_NAME,
        "legal_email": settings.LEGAL_EMAIL,
    }
