from django.urls import path

from apps.accounts import views as v

urlpatterns = [
    path("auth/csrf/", v.CsrfView.as_view(), name="auth-csrf"),
    path("auth/config/", v.AuthConfigView.as_view(), name="auth-config"),
    path("auth/register/", v.RegisterView.as_view(), name="auth-register"),
    path("auth/login/", v.LoginView.as_view(), name="auth-login"),
    path("auth/logout/", v.LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", v.MeView.as_view(), name="auth-me"),
    path("auth/password/change/", v.PasswordChangeView.as_view(), name="auth-password-change"),
    path("auth/password/forgot/", v.PasswordForgotView.as_view(), name="auth-password-forgot"),
    path("auth/password/reset/", v.PasswordResetView.as_view(), name="auth-password-reset"),
    path("auth/verify-email/request/", v.EmailVerificationRequestView.as_view(), name="auth-verify-email-request"),
    path("auth/verify-email/", v.EmailVerificationConfirmView.as_view(), name="auth-verify-email"),
    path("auth/otp/request/", v.OtpRequestView.as_view(), name="auth-otp-request"),
    path("auth/otp/verify/", v.OtpVerifyView.as_view(), name="auth-otp-verify"),
    path("auth/second-factor/request/", v.SecondFactorRequestView.as_view(), name="auth-2fa-request"),
    path("auth/second-factor/verify/", v.SecondFactorVerifyView.as_view(), name="auth-2fa-verify"),
    path("auth/google/start/", v.GoogleStartView.as_view(), name="auth-google-start"),
    path("auth/google/callback/", v.GoogleCallbackView.as_view(), name="auth-google-callback"),
    path("admin/security-policy/", v.SecurityPolicyView.as_view(), name="admin-security-policy"),
    path("admin/users/", v.AdminUsersView.as_view(), name="admin-users"),
    path("admin/audit/", v.AdminAuditView.as_view(), name="admin-audit"),
]
