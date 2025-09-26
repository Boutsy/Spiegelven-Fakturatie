from django.utils.deprecation import MiddlewareMixin

class AdminHeaderMiddleware(MiddlewareMixin):
    def process_request(self, request):
        try:
            from django.contrib import admin
            admin.site.site_header = 'Spiegelven Facturatie.'
        except Exception:
            pass
        return None
