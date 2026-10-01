from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("admin/users", views.UserViewSet, basename="admin-users")
router.register("admin/packs", views.CreditPackAdminViewSet, basename="admin-packs")
router.register("admin/plans", views.PlanAdminViewSet, basename="admin-plans")

urlpatterns = [
    path("admin/overview", views.OverviewView.as_view(), name="admin-overview"),
    path("admin/roles", views.RoleListView.as_view(), name="admin-roles"),
    path("admin/roles/<int:pk>", views.RoleDetailView.as_view(), name="admin-role-detail"),
    path("admin/jobs", views.AdminJobListView.as_view(), name="admin-jobs"),
    path("admin/jobs/<uuid:pk>", views.AdminJobDetailView.as_view(), name="admin-job-detail"),
    path("admin/jobs/<uuid:pk>/tasks/<uuid:task_id>/log", views.AdminTaskLogView.as_view(), name="admin-task-log"),
    path("admin/tasks/<uuid:pk>/retry", views.FailedTaskRetryView.as_view(), name="admin-task-retry"),
    path("admin/queues", views.QueueView.as_view(), name="admin-queues"),
    path("admin/workers", views.WorkerView.as_view(), name="admin-workers"),
    path("admin/system", views.SystemView.as_view(), name="admin-system"),
    path("admin/models", views.ModelAdminView.as_view(), name="admin-models"),
    path("admin/models/setup", views.DetectionSetupView.as_view(), name="admin-detection-setup"),
    path("admin/pricing", views.PricingView.as_view(), name="admin-pricing"),
    path("admin/settings", views.PlatformSettingsView.as_view(), name="admin-settings"),
    path("admin/payments", views.AdminPaymentListView.as_view(), name="admin-payments"),
    path("admin/payments/<uuid:pk>/refund", views.AdminRefundView.as_view(), name="admin-refund"),
    path("admin/webhooks", views.WebhookLogView.as_view(), name="admin-webhooks"),
    path("admin/audit-log", views.AuditLogView.as_view(), name="admin-audit-log"),
    path("admin/api-usage", views.ApiUsageView.as_view(), name="admin-api-usage"),
    path("", include(router.urls)),
]
