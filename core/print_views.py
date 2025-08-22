from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from .models import Invoice

@login_required
def invoice_preview(request, pk: int):
    inv = get_object_or_404(Invoice, pk=pk)

    # Veilig de gerelateerde lijnen ophalen (ondersteunt zowel related_name='lines' als default)
    lines_rel = getattr(inv, "lines", None) or getattr(inv, "invoiceline_set", None)
    lines = lines_rel.select_related("product").all() if lines_rel else []

    total_excl = sum((l.unit_price_excl or Decimal("0")) * (l.quantity or 1) for l in lines)
    total_vat = sum(((l.unit_price_excl or Decimal("0")) * (l.quantity or 1)) * (l.vat_rate or Decimal("0")) / 100 for l in lines)
    total_incl = total_excl + total_vat

    ctx = {
        "invoice": inv,
        "lines": lines,
        "total_excl": total_excl,
        "total_vat": total_vat,
        "total_incl": total_incl,
    }
    return render(request, "invoices/preview.html", ctx)