def app_version(request):
    from django.conf import settings
    return {'APP_VERSION': getattr(settings, 'APP_VERSION', '')}
