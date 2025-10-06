from django.contrib import admin
from django.urls import path
from core.views import version_txt, force_logout
from core.admin_views import products_catalog_json
from core.invoice_views import daily_invoice_preview, daily_invoice_print  # bestaande generieke
from core.admin_views import (
    daily_invoice_preview_logo,
    daily_invoice_preview_preprinted,
    daily_invoice_print_logo,
    daily_invoice_print_preprinted,
)

urlpatterns = [
    # catalogus voor JS
    path("admin/products-catalog.json", products_catalog_json, name="products-catalog-json"),

    # admin
    path("admin/", admin.site.urls),

    # dagfactuur: bestaande (fallback) preview/print
    path("facturen/<int:pk>/voorbeeld/", daily_invoice_preview, name="daily-invoice-preview"),
    path("facturen/<int:pk>/print/", daily_invoice_print, name="daily-invoice-print"),

    # dagfactuur: expliciete varianten
    path("facturen/<int:pk>/preview/logo/", daily_invoice_preview_logo, name="daily-invoice-preview-logo"),
    path("facturen/<int:pk>/preview/preprinted/", daily_invoice_preview_preprinted, name="daily-invoice-preview-preprinted"),
    path("facturen/<int:pk>/print/logo/", daily_invoice_print_logo, name="daily-invoice-print-logo"),
    path("facturen/<int:pk>/print/preprinted/", daily_invoice_print_preprinted, name="daily-invoice-print-preprinted"),

    # util
    path("version.txt", version_txt),
    path("force-logout/", force_logout),
]