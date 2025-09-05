from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Optionele (legacy) patches; nooit hard falen in admin-opstart
        try:
            from . import admin_member_patch  # kan ontbreken
        except Exception:
            pass
        try:
            from . import admin_cleanup_patch  # kan ontbreken
        except Exception:
            pass
