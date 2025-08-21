from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("import/upload/", views.import_upload, name="import_upload"),
    path("import/map/", views.import_map, name="import_map"),
    path("import/confirm/", views.import_confirm, name="import_confirm"),
    path("import/run/", views.import_run, name="import_run"),
]
