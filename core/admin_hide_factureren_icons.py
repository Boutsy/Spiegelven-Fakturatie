from django.contrib import admin
from django.apps import apps

def apply():
    M = apps.get_model("core","Member")
    ma = admin.site._registry.get(M)
    if not ma:
        return
    C = ma.__class__
    BaseMedia = getattr(C, "Media", object)
    class Media(BaseMedia):
        js = tuple(getattr(BaseMedia, "js", ())) + ("core/hide_factureren_icons.js",)
    C.Media = Media
