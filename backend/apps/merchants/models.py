from __future__ import annotations

import uuid
import zoneinfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


class BusinessType(models.TextChoices):
    SOLE_TRADER = "sole_trader", "Sole trader / freelancer"
    COMPANY = "company", "Registered company"
    NONPROFIT = "nonprofit", "Non-profit"
    OTHER = "other", "Other"


class OnboardingStatus(models.TextChoices):
    NEW = "new", "Account created"
    PROFILE_COMPLETE = "profile_complete", "Business profile complete"
    PAYPAL_CONNECTED = "paypal_connected", "PayPal verified"
    SYNCED = "synced", "Records synchronised"


def validate_timezone(value: str) -> None:
    if value not in zoneinfo.available_timezones():
        raise ValidationError("Unknown time zone.")


class Merchant(models.Model):
    """The tenant boundary. Every merchant-owned record carries a FK to this model and is
    always filtered by it on the server; a merchant id from the client is never trusted."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="merchant")
    business_name = models.CharField(max_length=120, blank=True)
    business_type = models.CharField(max_length=20, choices=BusinessType.choices, default=BusinessType.SOLE_TRADER)
    country = models.CharField(
        max_length=2, blank=True, validators=[RegexValidator(r"^[A-Z]{2}$", "Use a two-letter ISO country code.")]
    )
    # Display preference only. Source currencies on records are never converted or overridden.
    display_currency = models.CharField(
        max_length=3, default="USD", validators=[RegexValidator(r"^[A-Z]{3}$", "Use a three-letter ISO currency code.")]
    )
    timezone = models.CharField(max_length=64, default="UTC", validators=[validate_timezone])
    onboarding_status = models.CharField(max_length=20, choices=OnboardingStatus.choices, default=OnboardingStatus.NEW)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(business_type__in=[b.value for b in BusinessType]),
                name="merchants_merchant_business_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(onboarding_status__in=[s.value for s in OnboardingStatus]),
                name="merchants_merchant_onboarding_status_valid",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return self.business_name or self.user.email

    @property
    def profile_complete(self) -> bool:
        return bool(self.business_name and self.country)

    def advance_onboarding(self, status: str) -> None:
        """Onboarding only moves forward; never regresses on its own."""
        order = [s.value for s in OnboardingStatus]
        if order.index(status) > order.index(self.onboarding_status):
            self.onboarding_status = status
            self.save(update_fields=["onboarding_status", "updated_at"])
