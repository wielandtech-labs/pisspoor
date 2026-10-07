"""Staff-only print views: one SVG per sticker, or a sheet of them."""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from .models import Placement
from .printing import AgreementMissing, render_sticker


@staff_member_required
def sticker_svg(request: HttpRequest, code: str) -> HttpResponse:
    placement = get_object_or_404(Placement.objects.select_related("venue"), code=code)
    try:
        sticker = render_sticker(placement)
    except AgreementMissing as exc:
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
    unsigned = sorted({str(p.venue) for p in placements if not p.venue.has_agreement})
    if unsigned:
        return HttpResponseForbidden(
            "No signed placement agreement for: "
            + ", ".join(unsigned)
            + ". No contract, no stickers."
        )
    stickers = [(p, render_sticker(p)) for p in placements]
    return render(request, "venues/print_sheet.html", {"stickers": stickers})
