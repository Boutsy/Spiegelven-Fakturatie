from django.contrib import admin
from django.urls import path, include
from core.print_views import invoice_preview
from core import views as core_views  # JSON endpoint voor admin-autofill

urlpatterns = [
    # JSON endpoint dat admin JS gebruikt (prijzen/btw bij productkeuze)
    path("admin/core/product_defaults/<int:pk>/", core_views.product_defaults, name="product-defaults"),

    # Admin
    path("admin/", admin.site.urls),

    # Auth
    path("accounts/", include("django.contrib.auth.urls")),

    # NIEUW: Factuur-preview
    path("facturen/<int:pk>/voorbeeld/", invoice_preview, name="invoice_preview"),
]