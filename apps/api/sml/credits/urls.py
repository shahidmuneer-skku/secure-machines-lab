from django.urls import path

from . import views

urlpatterns = [
    path("credits/balance", views.BalanceView.as_view(), name="credits-balance"),
    path("credits/ledger", views.LedgerView.as_view(), name="credits-ledger"),
    path("credits/ledger.csv", views.LedgerExportView.as_view(), name="credits-ledger-csv"),
    path("credits/prices", views.PriceListView.as_view(), name="credits-prices"),
]
