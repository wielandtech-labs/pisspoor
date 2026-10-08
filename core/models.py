from django.db import models


class NotificationLog(models.Model):
    """One attempted email or push, so failures are visible in admin."""

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        PUSH = "push", "Push (ntfy)"

    channel = models.CharField(max_length=10, choices=Channel.choices)
    target = models.CharField(max_length=254, help_text="Email address or ntfy topic.")
    subject = models.CharField(max_length=200)
    ok = models.BooleanField()
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_channel_display()} → {self.target}: {self.subject}"
