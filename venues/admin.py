from django.contrib import admin, messages
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import AgreementAcceptance, Placement, SamplePackRequest, Venue
from .printing import print_blocker


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
        blockers = sorted({print_blocker(p.venue) for p in queryset.select_related("venue")} - {""})
        if blockers:
            self.message_user(request, " ".join(blockers), messages.ERROR)
            return None
        codes = ",".join(queryset.values_list("code", flat=True))
        return HttpResponseRedirect(reverse("venues:print_sheet") + f"?codes={codes}")


@admin.register(SamplePackRequest)
class SamplePackRequestAdmin(admin.ModelAdmin):
    list_display = ["created_at", "venue", "status", "ship_to_name", "phone", "tracking_number"]
    list_filter = ["status"]
    list_select_related = ["venue"]
    readonly_fields = ["venue", "verified_at", "shipped_at", "signer"]
    actions = ["verify", "print_pack", "mark_printed", "mark_shipped"]

    @admin.display(description="Signed by")
    def signer(self, obj):
        acceptance = obj.venue.acceptances.first()
        if not acceptance:
            return "-"
        return (
            f"{acceptance.signer_name} ({acceptance.signer_title}), "
            f"{acceptance.signer_email}, {acceptance.version}"
        )

    @admin.action(description="Mark verified (activates the venue)")
    def verify(self, request, queryset):
        now = timezone.now()
        for pack in queryset.select_related("venue"):
            pack.status = SamplePackRequest.Status.VERIFIED
            pack.verified_at = pack.verified_at or now
            pack.save(update_fields=["status", "verified_at"])
            pack.venue.active = True
            pack.venue.save(update_fields=["active"])
        self.message_user(
            request, f"Verified {queryset.count()} venue(s); their stickers can print."
        )

    @admin.action(description="Print stickers for selected packs")
    def print_pack(self, request, queryset):
        venues = [pack.venue for pack in queryset.select_related("venue")]
        blockers = sorted({print_blocker(v) for v in venues} - {""})
        if blockers:
            self.message_user(request, " ".join(blockers), messages.ERROR)
            return None
        codes = Placement.objects.filter(venue__in=venues, active=True).values_list(
            "code", flat=True
        )
        return HttpResponseRedirect(reverse("venues:print_sheet") + "?codes=" + ",".join(codes))

    @admin.action(description="Mark printed")
    def mark_printed(self, request, queryset):
        queryset.update(status=SamplePackRequest.Status.PRINTED)

    @admin.action(description="Mark shipped")
    def mark_shipped(self, request, queryset):
        queryset.update(status=SamplePackRequest.Status.SHIPPED, shipped_at=timezone.now())


@admin.register(AgreementAcceptance)
class AgreementAcceptanceAdmin(admin.ModelAdmin):
    list_display = ["accepted_at", "venue", "version", "signer_name", "signer_title"]
    list_select_related = ["venue"]
    readonly_fields = [f.name for f in AgreementAcceptance._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
