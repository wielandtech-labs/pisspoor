from django.contrib import admin
from django.db.models import Count

from .models import AdClick, Campaign


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ["advertiser", "headline", "starts_on", "ends_on", "weight", "active", "clicks"]
    list_filter = ["active"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(click_total=Count("clicks"))

    @admin.display(description="Clicks", ordering="click_total")
    def clicks(self, obj):
        return obj.click_total


@admin.register(AdClick)
class AdClickAdmin(admin.ModelAdmin):
    list_display = ["created_at", "campaign", "placement"]
    list_filter = ["campaign"]

    def has_add_permission(self, request):
        return False
