# core/print_views.py
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
from django.shortcuts import get_object_or_404, render
from django.contrib.admin.views.decorators import staff_member_required

from core.models import Invoice, InvoiceLine, OrganizationProfile

TWOPL = Decimal("0.01")

def q2(v: Decimal) -> Decimal:
    return (v or Decimal("0")).quantize(TWOPL, rounding=ROUND_HALF_UP)

def eur(v: Decimal) -> str:
    # Europese notatie: € 1.234,56
    s = f"{q2(v):,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {s}"

def pct(v: Decimal) -> str:
    return f"{(v or Decimal('0')):g}%"

def format_ogm(val) -> str:
    """
    Toon gestructureerde mededeling als +++123/4567/89012+++ wanneer mogelijk.
    Valt netjes terug op de ruwe waarde als de lengte niet herkenbaar is.
    """
    if not val:
        return ""
    d = "".join(ch for ch in str(val) if ch.isdigit())
    if len(d) == 12:
        return f"+++{d[0:3]}/{d[3:7]}/{d[7:12]}+++"
    if len(d) == 15:
        return f"+++{d[0:3]}/{d[3:7]}/{d[7:12]}{d[12:15]}+++"
    return str(val)

@staff_member_required
def invoice_preview(request, pk: int):
    inv = get_object_or_404(Invoice, pk=pk)
    org = OrganizationProfile.objects.first()

    raw_lines = (
        InvoiceLine.objects.filter(invoice=inv)
        .select_related("product")
        .order_by("id")
    )

    lines = []
    totals_excl = Decimal("0")
    totals_vat = Decimal("0")
    totals_incl = Decimal("0")
    vat_buckets = defaultdict(lambda: {"excl": Decimal("0"), "vat": Decimal("0"), "incl": Decimal("0")})

    for l in raw_lines:
        qty = l.quantity or Decimal("0")
        unit = l.unit_price_excl or Decimal("0")
        rate_pct = l.vat_rate or Decimal("0")
        rate = rate_pct / Decimal("100")

        line_excl = q2(unit * qty)
        vat_amount = q2(line_excl * rate)
        line_incl = q2(line_excl + vat_amount)

        desc = l.description or (getattr(l.product, "name", "") or "")

        lines.append({
            "description": desc,
            "quantity": qty,
            "unit_price_excl": eur(unit),
            "vat_rate": pct(rate_pct),
            "line_excl": eur(line_excl),
            "vat_amount": eur(vat_amount),
            "line_incl": eur(line_incl),
        })

        totals_excl += line_excl
        totals_vat += vat_amount
        totals_incl += line_incl

        b = vat_buckets[rate_pct]
        b["excl"] += line_excl
        b["vat"] += vat_amount
        b["incl"] += line_incl

    vat_summary = [
        {
            "rate": pct(rate),
            "excl": eur(data["excl"]),
            "vat": eur(data["vat"]),
            "incl": eur(data["incl"]),
        }
        for rate, data in sorted(vat_buckets.items(), key=lambda x: x[0])
    ]

    context = {
        "inv": inv,
        "org": org,
        "lines": lines,
        "vat_summary": vat_summary,
        "totals": {
            "excl": eur(totals_excl),
            "vat": eur(totals_vat),
            "incl": eur(totals_incl),
        },
        "payment": {
            "iban": getattr(org, "iban", "") if org else "",
            "bic": getattr(org, "bic", "") if org else "",
            "ogm": format_ogm(getattr(inv, "payment_reference_raw", "")),
        },
    }
    return render(request, "invoices/preview.html", context)