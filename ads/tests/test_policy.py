import pytest
from django.core.exceptions import ValidationError

from ads.models import Campaign, pick_campaign
from conftest import PHONE
from scans.models import Scan

pytestmark = pytest.mark.django_db


def make(**overrides):
    fields = {
        "advertiser": "Joe",
        "headline": "Fix it",
        "target_url": "https://example.com/joe",
    }
    return Campaign.objects.create(**{**fields, **overrides})


def political(**overrides):
    fields = {
        "advertiser": "Pat for Council",
        "category": Campaign.Category.POLITICAL,
        "headline": "Vote Pat",
        "paid_for_by": "Paid for by Pat for Council, 1 Main St",
        "sponsor_contact": "1 Main St",
    }
    return make(**{**fields, **overrides})


def test_new_campaigns_wait_for_review():
    campaign = make()
    assert campaign.status == Campaign.Status.PENDING
    assert not Campaign.objects.live().exists()
    campaign.approve()
    assert list(Campaign.objects.live()) == [campaign]


def test_changing_the_link_after_approval_sends_it_back_to_review():
    campaign = make()
    campaign.approve()
    campaign.target_url = "https://example.com/something-else"
    campaign.save()
    assert campaign.status == Campaign.Status.PENDING
    assert not Campaign.objects.live().exists()


def test_editing_copy_keeps_approval_when_link_is_unchanged():
    campaign = make()
    campaign.approve()
    campaign.weight = 3
    campaign.save()
    assert campaign.status == Campaign.Status.APPROVED


def test_rejected_campaigns_never_run():
    campaign = make()
    campaign.reject("Off-policy")
    assert campaign.status == Campaign.Status.REJECTED
    assert not Campaign.objects.live().exists()


@pytest.mark.parametrize("missing", ["paid_for_by", "sponsor_contact"])
def test_political_ads_cannot_be_approved_without_disclaimer(missing):
    campaign = political()
    setattr(campaign, missing, "  ")
    with pytest.raises(ValidationError) as exc:
        campaign.approve()
    assert missing in exc.value.message_dict
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.PENDING


def test_banned_categories_cannot_even_be_filed():
    values = set(Campaign.Category.values)
    for banned in ("alcohol", "cannabis", "tobacco", "gambling", "weapons", "adult", "drugs"):
        assert banned not in values


def test_political_ads_only_reach_venues_that_opted_in(venue):
    political().approve()
    assert pick_campaign(venue) is None
    venue.allow_political_ads = True
    venue.save()
    assert pick_campaign(venue).is_political


def test_landing_shows_political_label_disclaimer_and_ai_notice(client, venue, placement):
    venue.allow_political_ads = True
    venue.save()
    political(ai_generated=True).approve()
    body = client.get(f"/{placement.code}", HTTP_USER_AGENT=PHONE).content.decode()
    assert "Political ad · Pat for Council" in body
    assert "Paid for by Pat for Council, 1 Main St" in body
    assert "generated in whole or substantially by artificial intelligence" in body
    assert "/political-ads" in body


def test_scans_record_the_ad_they_showed(client, placement):
    campaign = make()
    campaign.approve()
    client.get(f"/{placement.code}", HTTP_USER_AGENT=PHONE)
    assert Scan.objects.get().campaign == campaign


def test_archive_lists_approved_political_ads_with_impressions(client, venue, placement):
    venue.allow_political_ads = True
    venue.save()
    shown = political()
    shown.approve()
    political(headline="Never approved")
    client.get(f"/{placement.code}", HTTP_USER_AGENT=PHONE)  # the only live ad: one impression
    make().approve()  # not political: never in the archive
    body = client.get("/political-ads").content.decode()
    assert "Vote Pat" in body and "Paid for by Pat for Council" in body
    assert "1 impression" in body
    assert "Never approved" not in body and "Fix it" not in body


def test_archive_keeps_political_ads_that_ran_then_left_review(client):
    ran = political()
    ran.approve()
    ran.target_url = "https://example.com/new-link"
    ran.save()  # back to pending
    body = client.get("/political-ads").content.decode()
    assert "Vote Pat" in body and "No longer running (pending review)" in body


def test_political_click_rejected_at_venue_that_did_not_opt_in(client, placement):
    from ads.models import AdClick

    campaign = political()
    campaign.approve()
    response = client.get(f"/{placement.code}/ad/{campaign.pk}", HTTP_USER_AGENT=PHONE)
    assert response.status_code == 404
    assert not AdClick.objects.exists()


def test_policy_page_lists_rules(client):
    body = client.get("/advertising-policy").content.decode()
    assert "Political" in body and "Sexual services" in body and "pending" in body


def test_admin_approve_action_reports_missing_disclaimer(admin_client):
    campaign = political(paid_for_by="")
    response = admin_client.post(
        "/admin/ads/campaign/",
        {"action": "approve", "_selected_action": [campaign.pk]},
        follow=True,
    )
    assert response.status_code == 200
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.PENDING
