"""The public side of a sticker: short link, landing page, rate, report."""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models import Avg
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ads.models import AdClick, Campaign, pick_campaign
from feedback.alerts import alert_venue
from feedback.models import (
    MaintenanceRequest,
    Rating,
    already_rated_today,
    report_limit_reached,
)
from venues.models import Placement

from .models import Scan
from .visitors import is_bot, user_agent, visitor_hash


def _live_placement(code: str) -> Placement:
    return get_object_or_404(
        Placement.objects.select_related("venue"),
        code=code,
        active=True,
        venue__active=True,
    )


def _back(placement: Placement, thanks: str) -> HttpResponse:
    response = redirect("scans:landing", code=placement.code)
    response["Location"] += f"?thanks={thanks}"
    return response


def landing(request: HttpRequest, code: str) -> HttpResponse:
    placement = _live_placement(code)
    visitor = visitor_hash(request)
    # Only a fresh arrival counts; the redirect back after rating/reporting
    # carries ?thanks= and must not look like another scan.
    campaign = pick_campaign(placement.venue)
    if "thanks" not in request.GET:
        Scan.objects.create(
            placement=placement,
            visitor_hash=visitor,
            is_bot=is_bot(user_agent(request)),
            campaign=campaign,
        )
    since = timezone.now() - timedelta(days=30)
    venue_ratings = Rating.objects.filter(placement__venue=placement.venue, created_at__gte=since)
    summary = venue_ratings.aggregate(avg=Avg("stars"))
    response = render(
        request,
        "scans/landing.html",
        {
            "placement": placement,
            "venue": placement.venue,
            "campaign": campaign,
            "issues": MaintenanceRequest.Issue.choices,
            "avg_rating": summary["avg"],
            "rating_count": venue_ratings.count(),
            "thanks": request.GET.get("thanks", ""),
            "already_rated": already_rated_today(placement, visitor),
        },
    )
    # A sticker's page is per-venue noise to a search engine.
    response["X-Robots-Tag"] = "noindex"
    return response


@require_POST
def rate(request: HttpRequest, code: str) -> HttpResponse:
    placement = _live_placement(code)
    if request.POST.get("website"):  # honeypot
        return _back(placement, "rated")
    visitor = visitor_hash(request)
    try:
        stars = int(request.POST.get("stars", ""))
    except ValueError:
        stars = 0
    if not 1 <= stars <= 5:
        return _back(placement, "invalid")
    if already_rated_today(placement, visitor):
        return _back(placement, "dupe")
    Rating.objects.create(
        placement=placement,
        stars=stars,
        comment=request.POST.get("comment", "").strip()[:280],
        visitor_hash=visitor,
    )
    return _back(placement, "rated")


@require_POST
def report(request: HttpRequest, code: str) -> HttpResponse:
    placement = _live_placement(code)
    if request.POST.get("website"):  # honeypot
        return _back(placement, "reported")
    issue = request.POST.get("issue", "")
    if issue not in MaintenanceRequest.Issue.values:
        return _back(placement, "invalid")
    visitor = visitor_hash(request)
    if report_limit_reached(visitor):
        return _back(placement, "slowdown")
    already_open = MaintenanceRequest.objects.filter(
        placement=placement,
        issue=issue,
        status__in=[MaintenanceRequest.Status.OPEN, MaintenanceRequest.Status.ACK],
    ).exists()
    maintenance = MaintenanceRequest.objects.create(
        placement=placement,
        issue=issue,
        note=request.POST.get("note", "").strip()[:280],
        visitor_hash=visitor,
    )
    # Five people reporting "no TP" is one problem, so one alert.
    if not already_open:
        transaction.on_commit(lambda: alert_venue(maintenance))
    return _back(placement, "reported")


def ad_click(request: HttpRequest, code: str, campaign_id: int) -> HttpResponse:
    placement = _live_placement(code)
    campaign = Campaign.objects.live().filter(pk=campaign_id).first()
    # Same rule as pick_campaign: a venue that never opted in to political
    # ads must not have political clicks attributed to it.
    if campaign is not None and campaign.is_political and not placement.venue.allow_political_ads:
        campaign = None
    if campaign is None:
        raise Http404("No such campaign")
    if not is_bot(user_agent(request)):
        AdClick.objects.create(
            campaign=campaign, placement=placement, visitor_hash=visitor_hash(request)
        )
    # Target comes from the database, never the request: not an open redirect.
    return redirect(campaign.target_url)
