import csv

from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html, format_html_join

from .models import RevenuePeriod, Scan
from .payouts import build_report


@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = ["created_at", "placement", "is_bot", "visitor_short"]
    list_filter = ["is_bot", "placement__venue"]
    date_hierarchy = "created_at"
    list_select_related = ["placement__venue"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Visitor")
    def visitor_short(self, obj):
        return obj.visitor_hash[:10]


@admin.register(RevenuePeriod)
class RevenuePeriodAdmin(admin.ModelAdmin):
    list_display = ["__str__", "gross_revenue", "house_cut", "closed"]
    readonly_fields = ["payout_table"]
    actions = ["export_csv"]

    @admin.display(description="Payouts (unique scans, bots excluded)")
    def payout_table(self, obj):
        if not obj.pk:
            return "Save the period to see the split."
        report = build_report(obj)
        rows = format_html_join(
            "",
            "<tr><td>{}</td><td>{}</td><td>${}</td></tr>",
            ((line.venue_name, line.unique_scans, line.amount) for line in report.lines),
        )
        return format_html(
            "<table><tr><th>Venue</th><th>Unique scans</th><th>Payout</th></tr>{}"
            "<tr><th>House</th><th>{}</th><th>${}</th></tr></table>",
            rows,
            report.total_scans,
            report.house,
        )

    @admin.action(description="Export payouts as CSV")
    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="payouts.csv"'
        writer = csv.writer(response)
        writer.writerow(["month", "venue", "unique_scans", "payout"])
        for period in queryset:
            report = build_report(period)
            month = period.month.strftime("%Y-%m")
            for line in report.lines:
                writer.writerow([month, line.venue_name, line.unique_scans, line.amount])
            writer.writerow([month, "HOUSE", report.total_scans, report.house])
        return response
