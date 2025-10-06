from .invoice_views import invoice_preview
from django.urls import path
from . import print_views, views

urlpatterns = [
    path("admin/products-catalog.json", products_catalog_json, name="products-catalog-json"),

    path('admin/invoice/preview/<int:member_id>/<int:year>/', invoice_preview, name='invoice_preview'),
    path('admin/invoice/preview/<int:member_id>/', invoice_preview, name='invoice_preview_current'),
    # Voorbeeld/print van een factuur
    path("facturen/<int:pk>/voorbeeld/", print_views.invoice_preview, name="invoice_preview"),

    # Gezin → jaar kiezen → conceptfactuur maken
    path("gezinnen/<int:pk>/genereer/", views.household_generate_invoice, name="household_generate_invoice"),

    # Jaarplan → prognose inkomsten (HTML + CSV)
#     path("jaarplan/<int:year>/prognose/", views.yearplan_forecast, name="yearplan_forecast"),
#     path("jaarplan/<int:year>/prognose.csv", views.yearplan_forecast_csv, name="yearplan_forecast_csv"),

]