from django.contrib import admin
from django.urls import path
from core.views import version_txt, force_logout
from core.invoice_views import daily_invoice_preview, daily_invoice_print
from core.admin_views import member_invoice_preview_default

urlpatterns = [
    path("admin/invoices/preview/<int:pk>/", member_invoice_preview_default, name="admin-invoice-preview-default"),
    path("facturen/<int:pk>/voorbeeld/", daily_invoice_preview, name="daily-invoice-preview"),
    path("facturen/<int:pk>/print/", daily_invoice_print, name="daily-invoice-print"),
    path("version.txt", version_txt),
    path("force-logout/", force_logout),
    path("admin/", admin.site.urls),
]