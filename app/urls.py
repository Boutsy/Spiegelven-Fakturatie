from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView
from core.views import version_txt, force_logout
from core.admin_views import products_catalog_json
from core.invoice_views import daily_invoice_preview, daily_invoice_print  # bestaande generieke
from core.admin_views import (
    daily_invoice_preview_logo,
    daily_invoice_preview_preprinted,
    daily_invoice_print_logo,
    daily_invoice_print_preprinted,
    member_invoice_preview,
    member_invoice_preview_default,
    send_invoice_ubl,
    yearly_invoice_preview_logo,
    yearly_invoice_preview_preprinted,
    yearly_invoice_print_logo,
    yearly_invoice_print_preprinted,
    yearly_invoice_batch_preview_logo,
    yearly_invoice_batch_preview_preprinted,
    yearly_invoice_batch_print_logo,
    yearly_invoice_batch_print_preprinted,
    admin_yearly_totals,
)

urlpatterns = [
    # catalogus voor JS
    path("admin/products-catalog.json", products_catalog_json, name="products-catalog-json"),
    path(
        "admin/invoice/<int:pk>/send-ubl/",
        send_invoice_ubl,
        name="invoice-send-ubl",
    ),
    path(
        "admin/invoice/preview/<int:member_id>/<int:year>/",
        member_invoice_preview,
        name="admin-invoice-preview",
    ),
    path(
        "admin/invoice/preview/<int:member_id>/",
        member_invoice_preview_default,
        name="admin-invoice-preview-default",
    ),

    # jaarfacturen (preview/print per lid + batch)
    path(
        "admin/invoice/year/<int:member_id>/<int:year>/preview/logo/",
        yearly_invoice_preview_logo,
        name="yearly-invoice-preview-logo",
    ),
    path(
        "admin/invoice/year/<int:member_id>/<int:year>/preview/preprinted/",
        yearly_invoice_preview_preprinted,
        name="yearly-invoice-preview-preprinted",
    ),
    path(
        "admin/invoice/year/<int:member_id>/<int:year>/print/logo/",
        yearly_invoice_print_logo,
        name="yearly-invoice-print-logo",
    ),
    path(
        "admin/invoice/year/<int:member_id>/<int:year>/print/preprinted/",
        yearly_invoice_print_preprinted,
        name="yearly-invoice-print-preprinted",
    ),
    # batch
    path(
        "admin/invoice/year/<int:year>/batch/preview/logo/",
        yearly_invoice_batch_preview_logo,
        name="yearly-invoice-batch-preview-logo",
    ),
    path(
        "admin/invoice/year/<int:year>/batch/preview/preprinted/",
        yearly_invoice_batch_preview_preprinted,
        name="yearly-invoice-batch-preview-preprinted",
    ),
    path(
        "admin/invoice/year/<int:year>/batch/print/logo/",
        yearly_invoice_batch_print_logo,
        name="yearly-invoice-batch-print-logo",
    ),
    path(
        "admin/invoice/year/<int:year>/batch/print/preprinted/",
        yearly_invoice_batch_print_preprinted,
        name="yearly-invoice-batch-print-preprinted",
    ),
    # totaalpagina (overzicht + batch-links)
    path(
        "admin/invoice/year/totals/",
        admin_yearly_totals,
        name="admin-yearly-totals",
    ),

    # oud yearpricing-adres doorsturen naar de nieuwe annualpricing
    path("admin/core/yearpricing/", RedirectView.as_view(url="/admin/core/annualpricing/", permanent=True)),

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
