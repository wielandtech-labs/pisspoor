"""Outbound notifications: email and ntfy push.

Both channels are best-effort by design. A maintenance report or a signup must
never fail because the mail server is slow or ntfy is down, so these functions
never raise: they return whether the send worked and record a NotificationLog
row either way (admin -> Notification logs shows failures).

Unconfigured is a normal state: without EMAIL_HOST, Django's console backend
prints emails to the pod log (dev, CI, review apps); without NTFY_URL, pushes
are skipped and logged.
"""

from __future__ import annotations

import json
import logging
import urllib.request

from django.conf import settings
from django.core.mail import send_mail

from .models import NotificationLog

log = logging.getLogger(__name__)
TIMEOUT_SECONDS = 5


def _record(channel: str, target: str, subject: str, error: str = "") -> bool:
    NotificationLog.objects.create(
        channel=channel, target=target[:254], subject=subject[:200], ok=not error, error=error
    )
    if error:
        log.warning("%s to %s failed: %s", channel, target, error)
    return not error


def send_email(to: str, subject: str, body: str) -> bool:
    if not to:
        return False
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
    except Exception as exc:  # noqa: BLE001 - any SMTP failure is logged, never raised
        return _record(NotificationLog.Channel.EMAIL, to, subject, str(exc)[:500] or repr(exc))
    return _record(NotificationLog.Channel.EMAIL, to, subject)


def send_push(topic: str, title: str, message: str, click_url: str = "") -> bool:
    if not topic:
        return False
    if not settings.NTFY_URL:
        log.info("Push to %s skipped: NTFY_URL not set (%s)", topic, title)
        return False
    # JSON publishing (POST to the server root) keeps non-ASCII titles intact;
    # the header-based API can't carry them.
    payload = {"topic": topic, "title": title, "message": message}
    if click_url:
        payload["click"] = click_url
    headers = {"Content-Type": "application/json"}
    if settings.NTFY_TOKEN:
        headers["Authorization"] = f"Bearer {settings.NTFY_TOKEN}"
    request = urllib.request.Request(
        settings.NTFY_URL.rstrip("/") + "/",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            response.read()
    except Exception as exc:  # noqa: BLE001 - network/HTTP errors are logged, never raised
        return _record(NotificationLog.Channel.PUSH, topic, title, str(exc)[:500] or repr(exc))
    return _record(NotificationLog.Channel.PUSH, topic, title)
