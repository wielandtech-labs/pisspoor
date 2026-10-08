from unittest import mock

import pytest
from django.core import mail

from conftest import PHONE
from core.models import NotificationLog
from core.notify import send_email, send_push
from feedback.models import MaintenanceRequest

pytestmark = pytest.mark.django_db


@pytest.fixture
def alerting(venue, settings):
    venue.contact_email = "owner@rustytap.example"
    venue.save()
    settings.NTFY_URL = "http://ntfy.test"
    settings.NTFY_TOKEN = "tk_test"
    return venue


def report(client, placement, issue="no_tp", note=""):
    return client.post(
        f"/{placement.code}/report",
        {"issue": issue, "note": note},
        HTTP_USER_AGENT=PHONE,
    )


@pytest.fixture
def urlopen():
    with mock.patch("core.notify.urllib.request.urlopen") as patched:
        patched.return_value.__enter__.return_value.read.return_value = b"{}"
        yield patched


def test_report_emails_and_pushes_the_venue(
    client, alerting, placement, urlopen, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        report(client, placement, note="stall 1, again")
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["owner@rustytap.example"]
    assert "Out of toilet paper · Stall 1" in message.subject
    assert "stall 1, again" in message.body
    assert f"/b/{alerting.board_token}" in message.body
    request = urlopen.call_args.args[0]
    assert request.full_url == "http://ntfy.test/"
    assert request.headers["Authorization"] == "Bearer tk_test"
    assert alerting.ntfy_topic.encode() in request.data
    assert NotificationLog.objects.filter(ok=True).count() == 2


def test_duplicate_open_report_does_not_alert_twice(
    client, alerting, placement, urlopen, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        report(client, placement)
        report(client, placement)  # same issue, still open
        report(client, placement, issue="clog")  # different issue: new alert
    assert MaintenanceRequest.objects.count() == 3
    assert len(mail.outbox) == 2


def test_resolved_issue_alerts_again_when_it_recurs(
    client, alerting, placement, urlopen, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        report(client, placement)
    MaintenanceRequest.objects.update(status=MaintenanceRequest.Status.RESOLVED)
    with django_capture_on_commit_callbacks(execute=True):
        report(client, placement)
    assert len(mail.outbox) == 2


def test_alerts_respect_the_venue_switches(
    client, alerting, placement, urlopen, django_capture_on_commit_callbacks
):
    alerting.email_alerts = False
    alerting.push_alerts = False
    alerting.save()
    with django_capture_on_commit_callbacks(execute=True):
        report(client, placement)
    assert not mail.outbox
    urlopen.assert_not_called()


def test_notify_email_overrides_contact_email(alerting):
    alerting.notify_email = "staff@rustytap.example"
    assert alerting.alert_email == "staff@rustytap.example"


def test_failures_are_logged_never_raised(alerting, settings):
    with mock.patch("core.notify.send_mail", side_effect=OSError("smtp down")):
        assert send_email("a@example.com", "Hi", "Body") is False
    with mock.patch("core.notify.urllib.request.urlopen", side_effect=OSError("ntfy down")):
        assert send_push("pp-x", "Hi", "Body") is False
    logs = NotificationLog.objects.order_by("channel")
    assert [(log.channel, log.ok) for log in logs] == [("email", False), ("push", False)]
    assert "smtp down" in logs[0].error


def test_push_is_skipped_without_ntfy_url(settings, urlopen):
    settings.NTFY_URL = ""
    assert send_push("pp-x", "Hi", "Body") is False
    urlopen.assert_not_called()
    assert not NotificationLog.objects.exists()


def test_every_venue_gets_its_own_topic(venue):
    from venues.models import Venue

    other = Venue.objects.create(name="Other", slug="other")
    assert venue.ntfy_topic.startswith("pp-")
    assert venue.ntfy_topic != other.ntfy_topic


def test_alert_settings_page_saves(client, alerting):
    url = f"/b/{alerting.board_token}/alerts"
    assert alerting.ntfy_topic in client.get(url).content.decode()
    response = client.post(url, {"notify_email": "staff@rustytap.example", "email_alerts": "on"})
    assert response.status_code == 302
    alerting.refresh_from_db()
    assert alerting.notify_email == "staff@rustytap.example"
    assert alerting.email_alerts and not alerting.push_alerts


def test_test_alert_sends_once_per_minute(client, alerting, urlopen):
    url = f"/b/{alerting.board_token}/alerts/test"
    assert client.post(url)["Location"].endswith("?tested=1")
    assert client.post(url)["Location"].endswith("?tested=wait")
    assert len(mail.outbox) == 1


def test_alert_settings_need_the_board_token(client, alerting):
    assert client.get("/b/wrong-token/alerts").status_code == 404
