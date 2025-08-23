from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Spiegelven"

    def ready(self):
        from . import admin_member_patch
        from . import nl_labels  # noqa
