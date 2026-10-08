"""The venue's private maintenance board, reached by a secret link."""

from __future__ import annotations

from datetime import timedelta

from django import forms
from django.conf import settings
from django.db.models import Avg, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import NotificationLog
from scans.payouts import unique_scans_by_venue
from venues.models import Venue

from .alerts import send_test_alert
from .leaderboard import MIN_RATINGS, TOP_N, WINDOW_DAYS, standings, venue_standing
from .models import MaintenanceRequest, Rating

NEXT_STATUS = {
    "ack": MaintenanceRequest.Status.ACK,
    "resolve": MaintenanceRequest.Status.RESOLVED,
    "reopen": MaintenanceRequest.Status.OPEN,
}


def _venue(token: str) -> Venue:
    # Inactive venues keep their board: a new venue gets its link at signup,
    # before verification, and a paused venue can still read its history.
    return get_object_or_404(Venue, board_token=token)


def board(request: HttpRequest, token: str) -> HttpResponse:
    venue = _venue(token)
    now = timezone.now()
    since = now - timedelta(days=30)
    requests = MaintenanceRequest.objects.filter(placement__venue=venue).select_related("placement")
    ratings = Rating.objects.filter(placement__venue=venue, created_at__gte=since)
    standing, ratings_needed = venue_standing(venue)
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
            "standing": standing,
            "ratings_needed": ratings_needed,
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


class AlertSettingsForm(forms.ModelForm):
    class Meta:
        model = Venue
        fields = ["notify_email", "email_alerts", "push_alerts"]
        labels = {
            "notify_email": "Send alerts to",
            "email_alerts": "Email me when something needs attention",
            "push_alerts": "Push to phones subscribed in the ntfy app",
        }


def alerts(request: HttpRequest, token: str) -> HttpResponse:
    """Alert settings live off the board: the board auto-refreshes, which would
    wipe a half-typed email address."""
    venue = _venue(token)
    form = AlertSettingsForm(request.POST or None, instance=venue)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(f"{request.path}?saved=1")
    host = settings.NTFY_PUBLIC_URL.split("://", 1)[-1]
    response = render(
        request,
        "feedback/alerts.html",
        {
            "venue": venue,
            "form": form,
            "saved": request.GET.get("saved") == "1",
            "tested": request.GET.get("tested", ""),
            "ntfy_web": f"{settings.NTFY_PUBLIC_URL}/{venue.ntfy_topic}",
            "ntfy_app": f"ntfy://{host}/{venue.ntfy_topic}",
            "ntfy_server": settings.NTFY_PUBLIC_URL,
        },
    )
    response["X-Robots-Tag"] = "noindex"
    return response


@require_POST
def test_alert(request: HttpRequest, token: str) -> HttpResponse:
    venue = _venue(token)
    settings_url = reverse("feedback:alerts", args=[token])
    recent = NotificationLog.objects.filter(
        Q(target=venue.alert_email) | Q(target=venue.ntfy_topic),
        subject__endswith="Test alert",
        created_at__gte=timezone.now() - timedelta(minutes=1),
    ).exists()
    if recent:
        return redirect(f"{settings_url}?tested=wait")
    send_test_alert(venue)
    return redirect(f"{settings_url}?tested=1")


@require_POST
def toggle_leaderboard(request: HttpRequest, token: str) -> HttpResponse:
    venue = _venue(token)
    venue.show_on_leaderboard = request.POST.get("show") == "1"
    venue.save(update_fields=["show_on_leaderboard"])
    return redirect("feedback:board", token=token)


def cleanest(request: HttpRequest) -> HttpResponse:
    top = standings()[:TOP_N]
    venues = {v.pk: v for v in Venue.objects.filter(pk__in=[s.key for s in top])}
    return render(
        request,
        "feedback/cleanest.html",
        {
            "rows": [(s, venues[s.key]) for s in top],
            "min_ratings": MIN_RATINGS,
            "window_days": WINDOW_DAYS,
        },
    )
