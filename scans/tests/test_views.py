from datetime import timedelta

import pytest
from django.utils import timezone

from ads.models import AdClick, Campaign
from conftest import PHONE
from feedback.models import MaintenanceRequest, Rating
from scans.models import Scan

pytestmark = pytest.mark.django_db


def get(client, path, **extra):
    return client.get(path, HTTP_USER_AGENT=PHONE, REMOTE_ADDR="203.0.113.9", **extra)


def post(client, path, data):
    return client.post(path, data, HTTP_USER_AGENT=PHONE, REMOTE_ADDR="203.0.113.9")


def test_scan_logs_and_shows_venue(client, placement):
    response = get(client, f"/{placement.code}")
    assert response.status_code == 200
    assert b"The Rusty Tap" in response.content
    assert b"instagram.com/rusty" in response.content
    assert response["X-Robots-Tag"] == "noindex"
    scan = Scan.objects.get()
    assert scan.placement == placement and not scan.is_bot


def test_raw_ip_is_never_stored(client, placement):
    get(client, f"/{placement.code}")
    scan = Scan.objects.get()
    assert "203.0.113.9" not in scan.visitor_hash
    assert len(scan.visitor_hash) == 64


def test_uppercase_code_still_resolves(client, placement):
    assert get(client, f"/{placement.code.upper()}").status_code == 200


def test_unknown_or_inactive_code_404s(client, placement, venue):
    assert get(client, "/zzzzzz").status_code == 404
    placement.active = False
    placement.save()
    assert get(client, f"/{placement.code}").status_code == 404
    placement.active = True
    placement.save()
    venue.active = False
    venue.save()
    assert get(client, f"/{placement.code}").status_code == 404


def test_link_preview_bots_are_flagged(client, placement):
    client.get(f"/{placement.code}", HTTP_USER_AGENT="Slackbot-LinkExpanding 1.0")
    assert Scan.objects.get().is_bot


def test_thanks_redirect_does_not_count_as_a_scan(client, placement):
    get(client, f"/{placement.code}?thanks=rated")
    assert Scan.objects.count() == 0


def test_fixed_routes_are_not_swallowed_by_short_codes(client):
    assert client.get("/privacy").status_code == 200
    assert client.get("/healthz").status_code == 200


def test_rating_once_per_day(client, placement):
    response = post(client, f"/{placement.code}/rate", {"stars": "4", "comment": "fine"})
    assert response.status_code == 302 and response["Location"].endswith("?thanks=rated")
    response = post(client, f"/{placement.code}/rate", {"stars": "1"})
    assert response["Location"].endswith("?thanks=dupe")
    rating = Rating.objects.get()
    assert (rating.stars, rating.comment) == (4, "fine")


@pytest.mark.parametrize("stars", ["0", "6", "x", ""])
def test_rating_rejects_bad_stars(client, placement, stars):
    response = post(client, f"/{placement.code}/rate", {"stars": stars})
    assert response["Location"].endswith("?thanks=invalid")
    assert not Rating.objects.exists()


def test_honeypot_drops_rating_silently(client, placement):
    response = post(client, f"/{placement.code}/rate", {"stars": "5", "website": "spam"})
    assert response["Location"].endswith("?thanks=rated")
    assert not Rating.objects.exists()


def test_report_rate_limited(client, placement):
    for _ in range(3):
        response = post(client, f"/{placement.code}/report", {"issue": "no_tp"})
        assert response["Location"].endswith("?thanks=reported")
    response = post(client, f"/{placement.code}/report", {"issue": "clog"})
    assert response["Location"].endswith("?thanks=slowdown")
    assert MaintenanceRequest.objects.count() == 3


def test_report_rejects_unknown_issue(client, placement):
    response = post(client, f"/{placement.code}/report", {"issue": "dragons"})
    assert response["Location"].endswith("?thanks=invalid")


def test_landing_shows_live_sponsor_and_click_redirects(client, placement):
    campaign = Campaign.objects.create(
        advertiser="Joe", headline="Fix it", target_url="https://example.com/joe"
    )
    assert b"Fix it" in get(client, f"/{placement.code}").content
    response = get(client, f"/{placement.code}/ad/{campaign.pk}")
    assert response.status_code == 302
    assert response["Location"] == "https://example.com/joe"
    assert AdClick.objects.get().placement == placement


def test_expired_campaign_is_neither_shown_nor_clickable(client, placement):
    campaign = Campaign.objects.create(
        advertiser="Old",
        headline="Gone",
        target_url="https://example.com/old",
        ends_on=timezone.localdate() - timedelta(days=1),
    )
    assert b"Gone" not in get(client, f"/{placement.code}").content
    assert get(client, f"/{placement.code}/ad/{campaign.pk}").status_code == 404


def test_spoofed_forwarded_for_does_not_change_identity(rf, settings):
    from scans.visitors import COOKIE_NAME, visitor_hash

    def request(claimed):
        req = rf.get("/", HTTP_USER_AGENT=PHONE, HTTP_X_FORWARDED_FOR=f"{claimed}, 10.12.12.1")
        req.COOKIES[COOKIE_NAME] = "a" * 22
        return req

    assert visitor_hash(request("1.1.1.1")) == visitor_hash(request("2.2.2.2"))


def test_same_ip_and_ua_but_different_browsers_are_different_visitors(placement):
    from django.test import Client

    from scans.payouts import unique_scans_by_venue

    for _ in range(2):  # two phones behind the same tunnel IP, same OS
        get(Client(), f"/{placement.code}")
    now = timezone.now()
    counts = unique_scans_by_venue(now - timedelta(hours=1), now + timedelta(hours=1))
    assert counts[placement.venue_id] == 2


def test_rescanning_from_the_same_browser_counts_once(client, placement):
    from scans.payouts import unique_scans_by_venue

    get(client, f"/{placement.code}")
    get(client, f"/{placement.code}")
    now = timezone.now()
    counts = unique_scans_by_venue(now - timedelta(hours=1), now + timedelta(hours=1))
    assert counts[placement.venue_id] == 1
    assert client.cookies["ppv"]["httponly"]


def test_homepage_sets_no_visitor_cookie(client):
    response = client.get("/")
    assert "ppv" not in response.cookies
