import logging
from datetime import timedelta
from urllib.parse import urlsplit

from django import forms
from django.conf import settings
from django.db import connection, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from scans.visitors import client_ip_hash

from .models import Lead
from .scenes import homepage_scenes
from .sites import is_fun_site

log = logging.getLogger(__name__)


class LeadForm(forms.ModelForm):
    # Honeypot: hidden from people, irresistible to form-filling bots.
    website = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"})
    )

    class Meta:
        model = Lead
        fields = ["kind", "name", "business", "email", "phone", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 4})}


# Leads one client IP may send per hour. Until the droplet forwards real client
# IPs (see scans.visitors), every public visitor shares one IP, so this is
# also a site-wide cap.
LEADS_PER_IP_PER_HOUR = 5


def too_many_leads(client_hash: str) -> bool:
    since = timezone.now() - timedelta(hours=1)
    recent = Lead.objects.filter(client_hash=client_hash, created_at__gte=since)
    return recent.count() >= LEADS_PER_IP_PER_HOUR


def save_lead_unless_limited(form: LeadForm, client_hash: str) -> bool:
    """Save the lead unless its sender is over the limit; False if rejected.

    The count and the insert share one transaction holding a Postgres advisory
    lock on the client hash, so parallel POSTs from one sender queue up instead
    of all passing the count. The lock is released at commit.
    """
    with transaction.atomic():
        if connection.vendor == "postgresql":  # SQLite (local dev, tests) has no such lock
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))", [f"marketing.lead:{client_hash}"]
                )
        if too_many_leads(client_hash):
            return False
        form.instance.client_hash = client_hash
        form.save()
    return True


def home(request):
    if is_fun_site(request):
        return render(request, "marketing/fun.html", homepage_scenes(settings.PUBLIC_BASE_URL))
    form = LeadForm(request.POST or None)
    error = ""
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["website"]:  # honeypot: pretend it worked
            return redirect("/?thanks=1#contact")
        if save_lead_unless_limited(form, client_ip_hash(request)):
            return redirect("/?thanks=1#contact")
        log.warning("Lead rejected: over %s per IP per hour", LEADS_PER_IP_PER_HOUR)
        error = "We've had a lot of messages from your network. Try again in an hour."
    return render(
        request,
        "marketing/home.html",
        {
            "form": form,
            "error": error,
            "thanks": request.GET.get("thanks") == "1",
            **homepage_scenes(settings.PUBLIC_BASE_URL),
        },
        status=429 if error else 200,
    )


def privacy(request):
    return render(request, "marketing/privacy.html")


def terms(request):
    return render(request, "marketing/terms.html")


# Public pages worth indexing. Everything else is a short code, a secret-token
# venue board, or the tailnet-only back office, none of which belongs in search.
SITEMAP_PAGES = [
    "marketing:home",
    "venues:join",
    "feedback:cleanest",
    "ads:policy",
    "ads:political_archive",
    "ads:advertiser_terms",
    "venues:agreement",
    "marketing:privacy",
    "marketing:terms",
]


def _indexable(request) -> bool:
    # Only the real brand domains get indexed; dev and review hosts tell
    # crawlers to stay out so they never compete with prod in search.
    hosts = {urlsplit(url).hostname for url in (settings.PUBLIC_BASE_URL, settings.AGENCY_URL)}
    hosts.update(settings.FUN_HOSTS)
    host = request.get_host().split(":")[0].lower()
    return host in hosts or host.removeprefix("www.") in hosts


def robots_txt(request):
    if not _indexable(request):
        return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")
    lines = [
        "User-agent: *",
        # Venue boards are secret-token URLs; keep them out even if one leaks.
        "Disallow: /b/",
        "Disallow: /admin/",
        "Disallow: /print/",
        "Disallow: /venues/join/done/",
        "",
        f"Sitemap: {request.build_absolute_uri(reverse('marketing:sitemap'))}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def sitemap_xml(request):
    if not _indexable(request):
        raise Http404
    urls = [request.build_absolute_uri(reverse(name)) for name in SITEMAP_PAGES]
    return render(request, "marketing/sitemap.xml", {"urls": urls}, content_type="application/xml")
