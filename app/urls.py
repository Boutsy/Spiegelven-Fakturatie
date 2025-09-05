from django.contrib import admin
from django.urls import path, include
from core import invoice_views

urlpatterns = [
    path("admin/invoice/preview/<int:member_id>/", admin.site.admin_view(invoice_views.invoice_preview_default_next_year), name="admin-invoice-preview-default"),
    path("admin/invoice/preview/<int:member_id>/<int:year>/", admin.site.admin_view(invoice_views.invoice_preview), name="admin-invoice-preview"),
    path("admin/", admin.site.urls),
    path("", include("core.urls")),            # frontend & helpers
    path("accounts/", include("django.contrib.auth.urls")),
]
