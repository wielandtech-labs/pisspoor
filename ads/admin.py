from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q

from .models import AdClick, Campaign


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = [
        "advertiser",
        "headline",
        "category",
        "status",
        "starts_on",
        "ends_on",
        "active",
        "impression_count",
        "clicks",
    ]
    list_filter = ["status", "category", "active"]
    readonly_fields = ["status", "approved_target_url"]
    actions = ["approve", "reject"]
    fieldsets = [
        (
            None,
            {"fields": ["advertiser", "category", "headline", "body", "cta_label", "target_url"]},
        ),
        ("Schedule", {"fields": ["starts_on", "ends_on", "weight", "active"]}),
        (
            "Review",
            {
                "fields": ["status", "approved_target_url", "review_notes"],
                "description": "Approve or reject from the campaign list (Actions). "
                "Changing the target URL sends an approved campaign back to pending.",
            },
        ),
        (
            "Political ads",
            {
                "fields": ["paid_for_by", "sponsor_contact", "ai_generated"],
                "description": "Required for the Political category. The disclaimer is shown "
                "word for word: check it matches the rules for that race before approving.",
            },
        ),
    ]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                click_total=Count("clicks", distinct=True),
                impression_total=Count(
                    "impressions", filter=Q(impressions__is_bot=False), distinct=True
                ),
            )
        )

    @admin.display(description="Impressions", ordering="impression_total")
    def impression_count(self, obj):
        return obj.impression_total

    @admin.display(description="Clicks", ordering="click_total")
    def clicks(self, obj):
        return obj.click_total

    @admin.action(description="Approve selected campaigns")
    def approve(self, request, queryset):
        approved = 0
        for campaign in queryset:
            try:
                campaign.approve()
            except ValidationError as exc:
                self.message_user(request, f"{campaign}: {exc.messages}", messages.ERROR)
            else:
                approved += 1
        if approved:
            self.message_user(request, f"Approved {approved} campaign(s).")

    @admin.action(description="Reject selected campaigns")
    def reject(self, request, queryset):
        for campaign in queryset:
            campaign.reject()
        self.message_user(request, f"Rejected {queryset.count()} campaign(s).")


@admin.register(AdClick)
class AdClickAdmin(admin.ModelAdmin):
    list_display = ["created_at", "campaign", "placement"]
    list_filter = ["campaign"]

    def has_add_permission(self, request):
        return False
