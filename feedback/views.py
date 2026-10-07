"""The venue's private maintenance board, reached by a secret link."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Avg
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from scans.payouts import unique_scans_by_venue
from venues.models import Venue

from .models import MaintenanceRequest, Rating

NEXT_STATUS = {
    "ack": MaintenanceRequest.Status.ACK,
    "resolve": MaintenanceRequest.Status.RESOLVED,
    "reopen": MaintenanceRequest.Status.OPEN,
}


def _venue(token: str) -> Venue:
    return get_object_or_404(Venue, board_token=token, active=True)


def board(request: HttpRequest, token: str) -> HttpResponse:
    venue = _venue(token)
    now = timezone.now()
    since = now - timedelta(days=30)
    requests = MaintenanceRequest.objects.filter(placement__venue=venue).select_related("placement")
    ratings = Rating.objects.filter(placement__venue=venue, created_at__gte=since)
    response = render(
        request,
        "feedback/board.html",
        {
            "venue": venue,
            "open_requests": requests.exclude(status=MaintenanceRequest.Status.RESOLVED),
            "resolved_requests": requests.filter(status=MaintenanceRequest.Status.RESOLVED)[:20],
            "avg_rating": ratings.aggregate(avg=Avg("stars"))["avg"],
            "rating_count": ratings.count(),
            "recent_comments": ratings.exclude(comment="").select_related("placement")[:10],
            "unique_scans": unique_scans_by_venue(since, now, venue.pk)[venue.pk],
            "placements": venue.placements.filter(active=True),
        },
    )
    response["X-Robots-Tag"] = "noindex"
    return response


@require_POST
def update_request(request: HttpRequest, token: str, pk: int) -> HttpResponse:
    venue = _venue(token)
    item = get_object_or_404(MaintenanceRequest, pk=pk, placement__venue=venue)
    status = NEXT_STATUS.get(request.POST.get("action", ""))
    if status is not None:
        item.status = status
        item.resolved_at = timezone.now() if status == MaintenanceRequest.Status.RESOLVED else None
        item.save(update_fields=["status", "resolved_at"])
    return redirect("feedback:board", token=token)
