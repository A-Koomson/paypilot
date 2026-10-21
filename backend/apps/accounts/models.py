from __future__ import annotations

import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower


class Role(models.TextChoices):
    MERCHANT = "merchant", "Merchant"
    SUPER_ADMIN = "super_admin", "Super administrator"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email: str, password: str | None, **extra):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra):
        extra.setdefault("role", Role.MERCHANT)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra):
        from django.utils import timezone

        extra["role"] = Role.SUPER_ADMIN
        extra["is_superuser"] = True
        extra.setdefault("email_verified_at", timezone.now())
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=254, unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MERCHANT)
    is_active = models.BooleanField(default=True)
    # Email *ownership* verification. This is not a second authentication factor.
    email_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
            models.CheckConstraint(
                condition=models.Q(role__in=[r.value for r in Role]), name="accounts_user_role_valid"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        return self.email

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def is_super_admin(self) -> bool:
        return self.role == Role.SUPER_ADMIN

    @property
    def is_staff(self) -> bool:  # Django admin is not installed; kept for library compatibility.
        return False


class OneTimeCodePurpose(models.TextChoices):
    LOGIN = "login", "Passwordless sign-in"
    SECOND_FACTOR = "second_factor", "Second authentication factor"


class OneTimeCode(models.Model):
    """A short-lived emailed code. Only a hash is stored; the plaintext is never persisted or logged."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="one_time_codes")
    purpose = models.CharField(max_length=20, choices=OneTimeCodePurpose.choices)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "purpose", "-created_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(purpose__in=[p.value for p in OneTimeCodePurpose]),
                name="accounts_otp_purpose_valid",
            )
        ]

    def __str__(self) -> str:
        return f"{self.purpose} for {self.user_id}"


class SecurityPolicy(models.Model):
    """Single-row, super-administrator controlled authentication policy."""

    SINGLETON_ID = 1

    id = models.PositiveSmallIntegerField(primary_key=True, default=SINGLETON_ID, editable=False)
    # When True, merchants must complete an emailed one-time code after each password/Google sign-in
    # and before any protected merchant endpoint will respond.
    require_second_factor = models.BooleanField(default=False)
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="accounts_securitypolicy_singleton")]

    def __str__(self) -> str:
        return "SecurityPolicy"

    @classmethod
    def load(cls) -> SecurityPolicy:
        policy, _ = cls.objects.get_or_create(id=cls.SINGLETON_ID)
        return policy
