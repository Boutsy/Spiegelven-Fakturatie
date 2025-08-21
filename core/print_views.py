from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import get_object_or_404, render
from .models import Invoice, OrganizationProfile

def _fmt_eur(v: Decimal | None) -> str:
    if v is None:
        return "€ 0,00"
    q = (v if isinstance(v, Decimal) else Decimal(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = f"{q:.2f}".replace(".", ",")
    return f"€ {s}"

def _ogm_from_number(number: str) -> str:
    digits = "".join(ch for ch in (number or "") if ch.isdigit())[-10:]
    digits = digits.rjust(10, "0")
    base = int(digits)
    mod = base % 97 or 97
    body = digits.rjust(10, "0")
    ogm = f"{body[:3]}/{body[3:7]}/{body[7:]}{mod:02d}"
    return f"+++{ogm}+++"

def invoice_preview(request, pk: int):
    inv = get_object_or_404(Invoice, pk=pk)
    org = OrganizationProfile.objects.first()

    lines = []
    total_excl = Decimal("0")
    total_vat = Decimal("0")

    for ln in inv.invoiceline_set.all():
        qty = ln.quantity or 0
        unit = ln.unit_price_excl or Decimal("0")
        vat_rate = ln.vat_rate or Decimal("0")
        line_excl = (unit * Decimal(qty)).quantize(Decimal("0.01"))
        line_vat = (line_excl * (vat_rate / Decimal("100"))).quantize(Decimal("0.01"))
        total_excl += line_excl
        total_vat += line_vat
        lines.append({
            "description": ln.description or (ln.product.name if ln.product else ""),
            "qty": qty,
            "unit": _fmt_eur(unit),
            "vat_rate": f"{vat_rate:.0f}%",
            "sum_excl": _fmt_eur(line_excl),
            "sum_vat": _fmt_eur(line_vat),
        })

    total_incl = total_excl + total_vat
    number = getattr(inv, "number", "") or str(inv.pk)
    ogm = getattr(inv, "payment_reference_raw", None) or _ogm_from_number(number)

    ctx = {
        "inv": inv,
        "org": org,
        "lines": lines,
        "total_excl": _fmt_eur(total_excl),
        "total_vat": _fmt_eur(total_vat),
        "total_incl": _fmt_eur(total_incl),
        "ogm": ogm,
        "status_label": "CONCEPT" if getattr(inv, "status", "draft") == "draft" else "GEFINALISEERD",
        "logo_url": None,
    }
    return render(request, "invoices/preview.html", ctx)