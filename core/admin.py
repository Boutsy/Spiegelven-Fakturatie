from django.contrib import admin
from django.apps import apps

# Registreer alle modellen van de app "core" met de default ModelAdmin
core_app = apps.get_app_config("core")
for model in core_app.get_models():
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
