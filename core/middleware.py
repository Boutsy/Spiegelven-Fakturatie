from django.utils.deprecation import MiddlewareMixin

BADGE_HTML = (
    '<div id="sv-version-badge" '
    'style="position:fixed;right:8px;top:6px;font:12px/1 system-ui;'
    'opacity:.65;color:#333;background:rgba(0,0,0,.05);padding:2px 6px;'
    'border-radius:6px;z-index:2147483647;pointer-events:none;">v{ver}</div>'
)

class VersionBadgeMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        # 1) debug header zodat we ZEKER weten dat middleware loopt
        try:
            from django.conf import settings
            ver = getattr(settings, 'APP_VERSION', 'dev')
            response['X-App-Version'] = ver
        except Exception:
            ver = 'dev'

        # 2) badge injectie (fouttolerant)
        try:
            ct = (response.get('Content-Type','') or '').lower()
            if 'text/html' not in ct:
                return response
            body = response.content.decode(getattr(response,'charset','utf-8') or 'utf-8', errors='ignore')
            if 'sv-version-badge' in body.lower():
                return response
            badge = BADGE_HTML.format(ver=ver)
            lower = body.lower()
            if '</body>' in lower:
                idx = lower.rfind('</body>')
                body = body[:idx] + badge + body[idx:]
            else:
                body = body + badge
            response.content = body.encode(getattr(response,'charset','utf-8') or 'utf-8', errors='ignore')
        except Exception:
            return response
        return response
