from django.contrib import admin
from django.urls import path, include
from core.adminapi import product_defaults

urlpatterns = [
    # JSON voor product defaults (alleen staff)
    path('admin/core/product_defaults/<int:pk>/', product_defaults, name='product-defaults'),

    # Django admin en login
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
]
