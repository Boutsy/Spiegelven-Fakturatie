cd "/Users/marcbouts/spiegelven-login"
cat > core/invoice_views.py <<'PY'
from decimal import Decimal
from django.apps import apps
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render

Invoice = apps.get_model("core", "Invoice")
InvoiceLine = apps.get_model("core", "InvoiceLine")

def _totals(invoice, lines):
    buckets = {}
    total_excl = Decimal("0.00")
    total_vat = Decimal("0.00")
    for ln in lines:
        qty = ln.quantity or Decimal("1")
        up = ln.unit_price_excl or Decimal("0.00")
        rate = Decimal(str(getattr(ln, "vat_rate", 0) or 0))
        excl = qty * up
        vat_amt = excl * rate / Decimal("100")
        total_excl += excl
        total_vat += vat_amt
        key = str(rate)
        b = buckets.get(key) or {"rate": rate, "excl": Decimal("0.00"), "vat": Decimal("0.00"), "incl": Decimal("0.00")}
        b["excl"] += excl
        b["vat"] += vat_amt
        b["incl"] = b["excl"] + b["vat"]
        buckets[key] = b
    return {
        "buckets": [buckets[k] for k in sorted(buckets.keys(), key=lambda x: Decimal(x))],
        "total_excl": total_excl,
        "total_vat": total_vat,
        "total_incl": total_excl + total_vat,
    }

def _recipient(invoice):
    m = getattr(invoice, "member", None)
    return {
        "name": getattr(invoice, "to_name", None) or (f"{getattr(m,'first_name','').strip()} {getattr(m,'last_name','').strip()}".strip() if m else ""),
        "street": getattr(invoice, "to_street", None) or getattr(m, "street", "") if m else getattr(invoice, "to_street", ""),
        "postal_code": getattr(invoice, "to_postal_code", None) or getattr(m, "postal_code", "") if m else getattr(invoice, "to_postal_code", ""),
        "city": getattr(invoice, "to_city", None) or getattr(m, "city", "") if m else getattr(invoice, "to_city", ""),
    }

@staff_member_required
def invoice_preview(request, pk:int):
    inv = get_object_or_404(Invoice, pk=pk)
    lines = list(InvoiceLine.objects.filter(invoice=inv).order_by("id"))
    t = _totals(inv, lines)
    ctx = {
        "invoice": inv,
        "lines": lines,
        "recipient": _recipient(inv),
        "vat_buckets": t["buckets"],
        "total_excl": t["total_excl"],
        "total_vat": t["total_vat"],
        "total_incl": t["total_incl"],
        "mode": "preview",
    }
    return render(request, "invoices/preview.html", ctx)

@staff_member_required
def invoice_print(request, pk:int):
    inv = get_object_or_404(Invoice, pk=pk)
    lines = list(InvoiceLine.objects.filter(invoice=inv).order_by("id"))
    t = _totals(inv, lines)
    ctx = {
        "invoice": inv,
        "lines": lines,
        "recipient": _recipient(inv),
        "vat_buckets": t["buckets"],
        "total_excl": t["total_excl"],
        "total_vat": t["total_vat"],
        "total_incl": t["total_incl"],
        "mode": "print",
    }
    return render(request, "invoices/print.html", ctx)
PY