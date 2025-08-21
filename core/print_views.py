# core/print_views.py
from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import get_object_or_404, render
from django.contrib.admin.views.decorators import staff_member_required

from core.models import Invoice, InvoiceLine  # belangrijk: direct via het model ophalen

TWOPL = Decimal("0.01")

def q2(v: Decimal) -> Decimal:
    """Rond af op 2 decimalen (handelsafronding)."""
    return (v or Decimal("0")).quantize(TWOPL, rounding=ROUND_HALF_UP)

@staff_member_required
def invoice_preview(request, pk: int):
    """
    HTML-voorvertoning van een factuur (printvriendelijk).
    """
    inv = get_object_or_404(Invoice, pk=pk)

    # Niet vertrouwen op related_name; altijd filteren op foreign key:
    raw_lines = (
        InvoiceLine.objects.filter(invoice=inv)
        .select_related("product")
        .order_by("id")
    )

    lines = []
    totals_excl = Decimal("0.00")
    totals_vat = Decimal("0.00")
    totals_incl = Decimal("0.00")

    for l in raw_lines:
        qty = l.quantity or Decimal("0")
        unit = l.unit_price_excl or Decimal("0")
        rate_pct = l.vat_rate or Decimal("0")
        rate = rate_pct / Decimal("100")

        line_excl = q2(unit * qty)
        vat_amount = q2(line_excl * rate)
        line_incl = q2(line_excl + vat_amount)

        lines.append({
            "description": l.description or (getattr(l.product, "name", "") or ""),
            "quantity": qty,
            "unit_price_excl": q2(unit),
            "vat_rate": rate_pct,
            "line_excl": line_excl,
            "vat_amount": vat_amount,
            "line_incl": line_incl,
        })

        totals_excl += line_excl
        totals_vat += vat_amount
        totals_incl += line_incl

    context = {
        "inv": inv,
        "lines": lines,
        "totals": {
            "excl": q2(totals_excl),
            "vat": q2(totals_vat),
            "incl": q2(totals_incl),
        },
    }
    return render(request, "invoices/preview.html", context)