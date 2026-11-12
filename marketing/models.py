from django.db import models


class Lead(models.Model):
    class Kind(models.TextChoices):
        VENUE = "venue", "I run a venue"
        ADVERTISER = "advertiser", "I want to advertise"

    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.VENUE)
    name = models.CharField(max_length=120)
    business = models.CharField(max_length=120, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    message = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)
    # scans.visitors.client_ip_hash of the sender, for the per-IP limit.
    client_hash = models.CharField(max_length=64, blank=True, editable=False, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_kind_display()}: {self.name}"
