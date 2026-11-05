from django.db import models

from common.models import TimestampedMixin


class BookkeepingClient(TimestampedMixin, models.Model):
    """A client business belonging to exactly one bookkeeping firm (Tenant)."""

    tenant = models.ForeignKey(
        "multitenancy.Tenant",
        on_delete=models.CASCADE,
        related_name="bookkeeping_clients",
    )
    name = models.CharField(max_length=200)
    contact_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name", "id")
        indexes = [models.Index(fields=("tenant", "is_active"), name="bk_client_tenant_active")]

    def __str__(self):
        return self.name
