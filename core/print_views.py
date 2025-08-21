# core/print_views.py
from decimal import Decimal
from django.shortcuts import get_object_or_404, render
from django.contrib.admin.views.decorators import staff_member_required

from core.models import Invoice

@staff_member_required
def invoice_preview(request, pk: int):
    """
    Eenvoudige HTML-voorvertoning van een factuur.
    Alleen voor ingelogde staf/admin (zelfde rechten als admin).
    """
    inv = get_object_or_404(Invoice, pk=pk)

    lines = inv.invoiceline_set.select_related("product").all()

    totals = {"excl": Decimal("0.00"), "vat": Decimal("0.00"), "incl": Decimal("0.00")}
    for l in lines:
        q = l.quantity or 0
        unit = l.unit_price_excl or Decimal("0")
        line_excl = unit * q
        rate = (l.vat_rate or Decimal("0")) / Decimal("100")
        line_vat = (line_excl * rate).quantize(Decimal("0.01"))
        totals["excl"] += line_excl
        totals["vat"] += line_vat
        totals["incl"] += (line_excl + line_vat)

    ctx = {
        "inv": inv,
        "lines": lines,
        "totals": totals,
    }
    return render(request, "invoices/preview.html", ctx)