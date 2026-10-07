from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ["created_at", "kind", "name", "business", "email", "handled"]
    list_filter = ["kind", "handled"]
    list_editable = ["handled"]
