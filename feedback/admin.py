from django.contrib import admin

from .models import MaintenanceRequest, Rating


@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = ["created_at", "placement", "issue", "status"]
    list_filter = ["status", "issue", "placement__venue"]
    list_select_related = ["placement__venue"]
    readonly_fields = ["visitor_hash", "created_at"]


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ["created_at", "placement", "stars", "comment"]
    list_filter = ["stars", "placement__venue"]
    list_select_related = ["placement__venue"]
    readonly_fields = ["visitor_hash", "created_at"]
