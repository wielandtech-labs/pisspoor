from django.contrib import admin, messages
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html

from .models import Placement, Venue


class PlacementInline(admin.TabularInline):
    model = Placement
    extra = 1
    fields = ["label", "product", "active", "code", "short_link"]
    readonly_fields = ["code", "short_link"]

    @admin.display(description="Short link")
    def short_link(self, obj):
        if not obj.pk:
            return "(assigned on save)"
        return format_html('<a href="{}" target="_blank">{}</a>', obj.short_url, obj.display_url)


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ["name", "agreement_signed_on", "active", "placement_count", "board_link"]
    list_filter = ["active"]
    search_fields = ["name", "address", "contact_name"]
    prepopulated_fields = {"slug": ["name"]}
    readonly_fields = ["board_link"]
    inlines = [PlacementInline]

    @admin.display(description="Placements")
    def placement_count(self, obj):
        return obj.placements.count()

    @admin.display(description="Maintenance board (send this link to the venue)")
    def board_link(self, obj):
        if not obj.pk:
            return "-"
        url = reverse("feedback:board", args=[obj.board_token])
        return format_html('<a href="{}" target="_blank">open board</a>', url)


@admin.register(Placement)
class PlacementAdmin(admin.ModelAdmin):
    list_display = ["code", "venue", "label", "product", "active", "scan_count", "svg_link"]
    list_filter = ["product", "active", "venue"]
    search_fields = ["code", "label", "venue__name"]
    readonly_fields = ["code", "svg_link"]
    actions = ["print_sheet"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("venue")
            .annotate(scan_total=Count("scans", filter=Q(scans__is_bot=False)))
        )

    @admin.display(description="Scans (all time)", ordering="scan_total")
    def scan_count(self, obj):
        return obj.scan_total

    @admin.display(description="Artwork")
    def svg_link(self, obj):
        if not obj.pk:
            return "-"
        url = reverse("venues:sticker_svg", args=[obj.code])
        return format_html('<a href="{}?download=1">download SVG</a>', url)

    @admin.action(description="Print sticker sheet for selected")
    def print_sheet(self, request, queryset):
        unsigned = sorted(
            {p.venue.name for p in queryset.select_related("venue") if not p.venue.has_agreement}
        )
        if unsigned:
            self.message_user(
                request,
                f"No signed placement agreement for: {', '.join(unsigned)}. "
                "No contract, no stickers.",
                messages.ERROR,
            )
            return None
        codes = ",".join(queryset.values_list("code", flat=True))
        return HttpResponseRedirect(reverse("venues:print_sheet") + f"?codes={codes}")
