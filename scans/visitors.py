"""Privacy-preserving visitor identity for dedup and rate limits.

Identity = HMAC(date, client IP, user agent, visitor cookie). Nothing in it is
stored raw, and the date makes it impossible to link visits across days.

Why a cookie and not just the IP: public HTTPS reaches the cluster through the
DigitalOcean droplet's raw TCP passthrough (no PROXY protocol), so every
public visitor arrives with the *same* tunnel source IP. IP + UA alone would
make every phone on the same OS version one "visitor", undercounting venues
and sharing one report rate limit across the whole network. The cookie is a
random, first-party, one-day token; it identifies a browser for a day and
nothing else.

Fraud resistance is limited by the same fact: a script that drops cookies is
a new visitor every request. Once the droplet forwards real client IPs, the
IP term starts doing real work with no change here.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import date

from django.conf import settings
from django.http import HttpRequest
from django.utils import timezone

COOKIE_NAME = "ppv"
COOKIE_MAX_AGE = 60 * 60 * 24
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{22}$")

# Link unfurlers (iMessage, Slack, social apps) fetch a URL the moment it is
# shared; counting those would pay venues for previews nobody saw.
BOT_MARKERS = (
    "bot",
    "crawl",
    "spider",
    "slurp",
    "preview",
    "facebookexternalhit",
    "curl",
    "wget",
    "python-requests",
    "headless",
)


def client_ip(request: HttpRequest) -> str:
    # The rightmost X-Forwarded-For entry is the one our own proxy (Traefik)
    # appended; anything left of it is whatever the client claimed.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


def user_agent(request: HttpRequest) -> str:
    return request.META.get("HTTP_USER_AGENT", "")[:512]


def visitor_token(request: HttpRequest) -> str:
    """The browser's one-day token, minting one (set by the middleware) if absent."""
    token = request.COOKIES.get(COOKIE_NAME, "")
    if _TOKEN_RE.match(token):
        return token
    if not getattr(request, "new_visitor_token", None):
        request.new_visitor_token = secrets.token_urlsafe(16)
    return request.new_visitor_token


def visitor_hash(request: HttpRequest, day: date | None = None) -> str:
    day = day or timezone.localdate()
    parts = (day.isoformat(), client_ip(request), user_agent(request), visitor_token(request))
    message = "|".join(parts).encode()
    return hmac.new(settings.SCAN_HASH_SECRET.encode(), message, hashlib.sha256).hexdigest()


def is_bot(ua: str) -> bool:
    ua = ua.lower()
    return not ua or any(marker in ua for marker in BOT_MARKERS)


class VisitorCookieMiddleware:
    """Sets the visitor cookie when a view minted a token for this request.

    Only pages that identify a visitor (sticker pages and their forms) ever
    mint one, so the homepage sets no cookie of ours.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        token = getattr(request, "new_visitor_token", None)
        if token:
            response.set_cookie(
                COOKIE_NAME,
                token,
                max_age=COOKIE_MAX_AGE,
                httponly=True,
                samesite="Lax",
                secure=request.is_secure(),
            )
        return response
