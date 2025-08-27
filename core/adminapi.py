from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, Http404
from .models import Product

@staff_member_required
def product_defaults(request, pk: int):
    try:
        p = Product.objects.get(pk=pk)
    except Product.DoesNotExist:
        raise Http404("Product niet gevonden")
    return JsonResponse({
        "name": p.name or "",
        "default_price_excl": float(p.default_price_excl or 0),
        "default_vat_rate": float(p.default_vat_rate or 0),
    })
