from __future__ import annotations

from rest_framework import serializers

from apps.merchants.models import BusinessType, Merchant, OnboardingStatus


class MerchantSerializer(serializers.ModelSerializer):
    profile_complete = serializers.BooleanField(read_only=True)
    business_type_options = serializers.SerializerMethodField()

    class Meta:
        model = Merchant
        fields = [
            "id",
            "business_name",
            "business_type",
            "country",
            "display_currency",
            "timezone",
            "onboarding_status",
            "profile_complete",
            "business_type_options",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "onboarding_status", "created_at", "updated_at"]

    def get_business_type_options(self, obj) -> list[dict]:
        return [{"value": v, "label": label} for v, label in BusinessType.choices]

    def validate_country(self, value: str) -> str:
        return value.strip().upper()

    def validate_display_currency(self, value: str) -> str:
        return value.strip().upper()

    def validate_business_name(self, value: str) -> str:
        return value.strip()

    def update(self, instance: Merchant, validated_data):
        instance = super().update(instance, validated_data)
        if instance.profile_complete:
            instance.advance_onboarding(OnboardingStatus.PROFILE_COMPLETE)
        return instance
