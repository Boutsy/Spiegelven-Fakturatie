from django.http import HttpResponse
from django.conf import settings
from django.contrib.auth import logout

def version_txt(request):
    return HttpResponse(f"APP_VERSION={getattr(settings,'APP_VERSION','')}", content_type="text/plain")

def force_logout(request):
    logout(request)
    return HttpResponse("OK: logged out", content_type="text/plain")
