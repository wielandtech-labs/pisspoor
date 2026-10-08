"""Public ad pages: the advertising policy and the political ad archive."""

from __future__ import annotations

from django.db.models import Count, Q
from django.shortcuts import render

from .legal import ADVERTISER_TERMS_TEMPLATE
from .models import Campaign


def policy(request):
    return render(
        request,
        "ads/policy.html",
        {"categories": [label for value, label in Campaign.Category.choices]},
    )


def political_archive(request):
    """Every political ad ever approved, with who paid and how often it ran.

    "Ever approved" means approved_target_url is set: an ad that ran and was
    later sent back to review (link changed) or rejected stays on the record.

    Kept public on purpose: some states require an archive like this, and it
    is what makes political ads in a captive space feel fair rather than shady.
    """
    ads = (
        Campaign.objects.filter(category=Campaign.Category.POLITICAL)
        .exclude(approved_target_url="")
        .annotate(
            impression_total=Count(
                "impressions", filter=Q(impressions__is_bot=False), distinct=True
            ),
            click_total=Count("clicks", distinct=True),
        )
        .order_by("-starts_on", "advertiser")
    )
    return render(request, "ads/political_archive.html", {"ads": ads})


def advertiser_terms(request):
    return render(
        request, "ads/advertiser_terms_page.html", {"terms_template": ADVERTISER_TERMS_TEMPLATE}
    )
