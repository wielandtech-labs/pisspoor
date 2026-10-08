"""Staff-only print views: one SVG per sticker, or a sheet of them."""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from scans.visitors import visitor_hash

from .models import Placement, Venue
from .onboarding import (
    AGREEMENT_TEMPLATE,
    AGREEMENT_VERSION,
    STARTER_PACK,
    VenueSignupForm,
    create_venue,
    recently_signed_up,
)
from .printing import NotPrintable, print_blocker, render_sticker


@staff_member_required
def sticker_svg(request: HttpRequest, code: str) -> HttpResponse:
    placement = get_object_or_404(Placement.objects.select_related("venue"), code=code)
    try:
        sticker = render_sticker(placement)
    except NotPrintable as exc:
        return HttpResponseForbidden(str(exc))
    response = HttpResponse(sticker.svg(), content_type="image/svg+xml")
    if request.GET.get("download"):
        filename = f"{placement.venue.slug}-{placement.code}-{placement.product}.svg"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@staff_member_required
def print_sheet(request: HttpRequest) -> HttpResponse:
    codes = [c for c in request.GET.get("codes", "").split(",") if c]
    placements = list(
        Placement.objects.select_related("venue").filter(code__in=codes).order_by("venue__name")
    )
    blockers = sorted({print_blocker(p.venue) for p in placements} - {""})
    if blockers:
        return HttpResponseForbidden(" ".join(blockers))
    stickers = [(p, render_sticker(p)) for p in placements]
    return render(request, "venues/print_sheet.html", {"stickers": stickers})


@require_http_methods(["GET", "POST"])
def join(request: HttpRequest) -> HttpResponse:
    form = VenueSignupForm(request.POST or None)
    error = ""
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["fax_number"]:  # honeypot: pretend it worked
            return redirect("marketing:home")
        visitor = visitor_hash(request)
        if recently_signed_up(visitor):
            error = "You just signed up a venue. Give us an hour before adding another."
        else:
            venue = create_venue(form, visitor)
            return redirect("venues:join_done", token=venue.board_token)
    return render(
        request,
        "venues/join.html",
        {
            "form": form,
            "error": error,
            "agreement_template": AGREEMENT_TEMPLATE,
            "agreement_version": AGREEMENT_VERSION,
            "starter": STARTER_PACK,
        },
    )


def join_done(request: HttpRequest, token: str) -> HttpResponse:
    venue = get_object_or_404(Venue, board_token=token)
    response = render(request, "venues/join_done.html", {"venue": venue})
    response["X-Robots-Tag"] = "noindex"
    return response


def agreement(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "venues/agreement_page.html",
        {"agreement_template": AGREEMENT_TEMPLATE, "agreement_version": AGREEMENT_VERSION},
    )
