"""Demo data for review apps: a venue, stickers, sponsors, some traffic.

Refuses to run unless ALLOW_DEMO_SEED is set, which only the review-app
registry does. Idempotent: a second run (pod restart) changes nothing and
never prints the admin password again.
"""

from __future__ import annotations

import os
import secrets
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from ads.models import Campaign
from feedback.models import MaintenanceRequest, Rating
from scans.models import RevenuePeriod, Scan
from venues.models import Placement, Venue


class Command(BaseCommand):
    help = "Seed demo data (review apps only; needs ALLOW_DEMO_SEED=1)."

    def handle(self, *args, **options):
        if os.environ.get("ALLOW_DEMO_SEED") != "1":
            self.stdout.write("ALLOW_DEMO_SEED is not set; skipping demo seed.")
            return
        if Venue.objects.filter(slug="the-rusty-tap").exists():
            self.stdout.write("Demo data already present.")
            return

        User = get_user_model()
        password = secrets.token_urlsafe(12)
        User.objects.create_superuser("demo", "demo@example.invalid", password)
        self.stdout.write(self.style.WARNING(f"Demo admin login: demo / {password}"))

        today = timezone.localdate()
        rusty = Venue.objects.create(
            name="The Rusty Tap",
            slug="the-rusty-tap",
            address="123 Main St",
            instagram_url="https://instagram.com/",
            google_reviews_url="https://maps.google.com/",
            agreement_signed_on=today - timedelta(days=20),
            allow_political_ads=True,
        )
        tacos = Venue.objects.create(
            name="Taco Libre",
            slug="taco-libre",
            facebook_url="https://facebook.com/",
            agreement_signed_on=today - timedelta(days=10),
        )
        Venue.objects.create(name="Bowl-a-Rama (pending)", slug="bowl-a-rama")

        placements = [
            Placement.objects.create(venue=rusty, label="Men's stall 1", product="large"),
            Placement.objects.create(venue=rusty, label="Men's urinal 2", product="urinal_target"),
            Placement.objects.create(venue=rusty, label="Women's mirror", product="branded"),
            Placement.objects.create(venue=tacos, label="Unisex stall", product="large"),
        ]
        joe = Campaign.objects.create(
            advertiser="Joe's Plumbing",
            category=Campaign.Category.SERVICES,
            headline="We fix what you just broke.",
            body="24/7 emergency service. Mention this sticker for $20 off.",
            cta_label="Call Joe",
            target_url="https://example.com/joes-plumbing",
            weight=2,
        )
        rides = Campaign.objects.create(
            advertiser="Night Owl Rides",
            category=Campaign.Category.SERVICES,
            headline="Had a few? Get home safe.",
            cta_label="Book a ride",
            target_url="https://example.com/night-owl",
        )
        # Fictional candidate: shows the political label, disclaimer and archive.
        council = Campaign.objects.create(
            advertiser="Pat Example for City Council",
            category=Campaign.Category.POLITICAL,
            headline="Fix the potholes. Then the bathrooms.",
            cta_label="Meet Pat",
            target_url="https://example.com/pat-for-council",
            paid_for_by="Paid for by Pat Example for City Council, 100 Example Ave, Anytown MI",
            sponsor_contact="100 Example Ave, Anytown MI",
            ai_generated=True,
        )
        for campaign in (joe, rides, council):
            campaign.approve()
        # Left pending so the review queue isn't empty.
        Campaign.objects.create(
            advertiser="Brand New Gym",
            category=Campaign.Category.WELLNESS,
            headline="First month free.",
            target_url="https://example.com/gym",
        )

        now = timezone.now()
        for i, placement in enumerate(placements):
            for n in range(12 - 2 * i):
                Scan.objects.create(
                    placement=placement,
                    visitor_hash=f"demo-{i}-{n}",
                    created_at=now - timedelta(hours=n * 5),
                )
        Rating.objects.create(
            placement=placements[0], stars=4, comment="Surprisingly fine.", visitor_hash="demo-r1"
        )
        Rating.objects.create(
            placement=placements[2], stars=2, comment="Out of soap again", visitor_hash="demo-r2"
        )
        MaintenanceRequest.objects.create(
            placement=placements[1],
            issue="spill",
            note="Aim was not improved",
            visitor_hash="demo-m1",
        )
        RevenuePeriod.objects.create(
            month=date(today.year, today.month, 1), gross_revenue="1000.00"
        )
        self.stdout.write(self.style.SUCCESS("Seeded demo data."))
        self.stdout.write(f"Venue board: /b/{rusty.board_token}")
        self.stdout.write(f"Try a sticker: /{placements[0].code}")
