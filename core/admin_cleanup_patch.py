from django.contrib import admin
from django.apps import apps

def _unregister(model_label):
    try:
        model = apps.get_model("core", model_label)
        if model in admin.site._registry:
            admin.site.unregister(model)
    except Exception:
        pass

_unregister("Household")

admin.site.site_header = "Spiegelven Facturatie"
admin.site.site_title = "Spiegelven Facturatie"
admin.site.index_title = "Beheer"
