# app/urls.py
from django.contrib import admin
from django.urls import path, include

# Optioneel bestaande extra admin-view (we proberen te importeren; zo niet, slaan we de route over)
_extra_patterns = []
try:
    from core.views import product_defaults
    _extra_patterns.append(
        path("admin/core/product_defaults/<int:pk>/", product_defaults, name="product-defaults")
    )
except Exception:
    pass

# Onze preview-view
from core.print_views import invoice_preview

urlpatterns = [
    *_extra_patterns,
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    # Voorbeeld/preview van factuur
    path("facturen/<int:pk>/voorbeeld/", invoice_preview, name="invoice_preview"),
]