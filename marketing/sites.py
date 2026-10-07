"""Which front door a request came through: the agency (.com) or the fun site (.lol)."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest


def is_fun_site(request: HttpRequest) -> bool:
    return request.get_host().split(":")[0].lower() in settings.FUN_HOSTS


def brand(request: HttpRequest) -> dict[str, object]:
    fun = is_fun_site(request)
    return {
        "is_fun_site": fun,
        "brand_tld": "lol" if fun else "com",
        "agency_url": settings.AGENCY_URL,
    }
