from django.urls import path

from apps.recovery import views

urlpatterns = [
    path("recovery/", views.RecoveryQueueView.as_view(), name="recovery-queue"),
    path("recovery/cases/<uuid:pk>/", views.RecoveryCaseDetailView.as_view(), name="recovery-case"),
    path("recovery/cases/<uuid:pk>/priority/", views.RecoveryPriorityView.as_view(), name="recovery-priority"),
    path("recovery/cases/<uuid:pk>/draft/", views.RecoveryDraftView.as_view(), name="recovery-draft"),
    path("recovery/actions/<uuid:pk>/submit/", views.RecoverySubmitView.as_view(), name="recovery-submit"),
    path("recovery/actions/<uuid:pk>/approve/", views.RecoveryApproveView.as_view(), name="recovery-approve"),
    path("recovery/actions/<uuid:pk>/reject/", views.RecoveryRejectView.as_view(), name="recovery-reject"),
    path("recovery/actions/<uuid:pk>/execute/", views.RecoveryExecuteView.as_view(), name="recovery-execute"),
]
