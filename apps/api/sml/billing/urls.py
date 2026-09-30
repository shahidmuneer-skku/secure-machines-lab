from django.urls import path

from . import views

urlpatterns = [
    path("billing/catalog", views.CatalogView.as_view(), name="billing-catalog"),
    path("billing/checkout", views.CheckoutView.as_view(), name="billing-checkout"),
    path("billing/toss/confirm", views.TossConfirmView.as_view(), name="billing-toss-confirm"),
    path("billing/toss/billing-confirm", views.TossBillingConfirmView.as_view(), name="billing-toss-billing"),
    path("billing/mock/complete", views.MockCompleteView.as_view(), name="billing-mock-complete"),
    path("billing/webhooks/<str:provider>", views.WebhookView.as_view(), name="billing-webhook"),
    path("billing/payments", views.PaymentListView.as_view(), name="billing-payments"),
    path("billing/payments/<str:order_id>", views.PaymentStatusView.as_view(), name="billing-payment-status"),
    path("billing/subscription", views.SubscriptionView.as_view(), name="billing-subscription"),
    path("billing/subscription/<str:action>", views.SubscriptionActionView.as_view(), name="billing-sub-action"),
    path("billing/portal", views.PortalView.as_view(), name="billing-portal"),
]
