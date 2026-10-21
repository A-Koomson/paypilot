from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import SecurityPolicy, User


class PasswordField(serializers.CharField):
    def __init__(self, **kwargs):
        kwargs.setdefault("write_only", True)
        kwargs.setdefault("trim_whitespace", False)
        kwargs.setdefault("max_length", 128)
        kwargs.setdefault("style", {"input_type": "password"})
        super().__init__(**kwargs)


def _run_password_validators(password: str, user=None) -> str:
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages))
    return password


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    full_name = serializers.CharField(max_length=150)
    password = PasswordField()

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate(self, attrs):
        probe = User(email=attrs["email"], full_name=attrs["full_name"])
        _run_password_validators(attrs["password"], probe)
        return attrs


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = PasswordField()


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class CodeSerializer(serializers.Serializer):
    code = serializers.RegexField(r"^\d{6}$", error_messages={"invalid": "Enter the 6-digit code."})


class OtpVerifySerializer(CodeSerializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class TokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512)


class PasswordResetSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=64)
    token = serializers.CharField(max_length=128)
    new_password = PasswordField()

    def validate_new_password(self, value: str) -> str:
        return _run_password_validators(value)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = PasswordField(required=False, allow_blank=True)
    new_password = PasswordField()

    def validate_new_password(self, value: str) -> str:
        return _run_password_validators(value, self.context["request"].user)


class UserSerializer(serializers.ModelSerializer):
    has_password = serializers.SerializerMethodField()
    email_verified = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role", "email_verified", "has_password", "created_at"]
        read_only_fields = ["id", "email", "role", "created_at"]

    def get_has_password(self, obj: User) -> bool:
        return obj.has_usable_password()

    def get_email_verified(self, obj: User) -> bool:
        return obj.is_email_verified


class SecurityPolicySerializer(serializers.ModelSerializer):
    updated_by_email = serializers.EmailField(source="updated_by.email", read_only=True, default=None)

    class Meta:
        model = SecurityPolicy
        fields = ["require_second_factor", "updated_at", "updated_by_email"]
        read_only_fields = ["updated_at", "updated_by_email"]


class AdminUserSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source="merchant.business_name", read_only=True, default="")

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "role",
            "is_active",
            "email_verified_at",
            "last_login",
            "created_at",
            "business_name",
        ]
