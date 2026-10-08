"""Tell a venue's staff when a guest reports a problem."""

from __future__ import annotations

from django.conf import settings
from django.urls import reverse

from core.notify import send_email, send_push

from .models import MaintenanceRequest


def board_url(venue) -> str:
    return settings.PUBLIC_BASE_URL + reverse("feedback:board", args=[venue.board_token])


def alert_venue(maintenance: MaintenanceRequest) -> None:
    placement = maintenance.placement
    venue = placement.venue
    title = f"{maintenance.get_issue_display()} · {placement.label}"
    link = board_url(venue)
    note = f"Guest's note: “{maintenance.note}”\n\n" if maintenance.note else ""
    if venue.email_alerts:
        send_email(
            venue.alert_email,
            f"[{venue.name}] {title}",
            f"A guest just reported a problem in your restroom.\n\n{title}\n{note}"
            f"Mark it handled on your board: {link}\n\n"
            "You're getting this because alerts are on for your venue. "
            "Turn them off on the board.",
        )
    if venue.push_alerts:
        send_push(venue.ntfy_topic, title, maintenance.note or "Tap to open your board.", link)


def send_test_alert(venue) -> None:
    link = board_url(venue)
    if venue.email_alerts:
        send_email(
            venue.alert_email,
            f"[{venue.name}] Test alert",
            f"Alerts are working. Real ones look like this.\n\nYour board: {link}",
        )
    if venue.push_alerts:
        send_push(venue.ntfy_topic, "Test alert", "Alerts are working.", link)
