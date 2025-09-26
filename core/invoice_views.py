from decimal import Decimal, ROUND_HALF_UP
from django.apps import apps
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render

Invoice = apps.get_model("core", "Invoice")
InvoiceLine = apps.get_model("core", "InvoiceLine")
OrganizationProfile = apps.get_model("core", "OrganizationProfile")

def _q(val):
    return Decimal(str(val or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _split_amount(d):
    s = f"{_q(d):.2f}"
    i, dec = s.split(".")
    return {"int": i.replace("-", "−"), "dec": dec}

def _lines_for(invoice):
    qs = InvoiceLine.objects.filter(invoice=invoice).order_by("id")
    out = []
    for l in qs:
        qty = _q(getattr(l, "quantity", 1))
        unit = _q(getattr(l, "unit_price_excl", 0))
        rate = Decimal(str(getattr(l, "vat_rate", 0) or 0))
        ex = _q(qty * unit)
        vat = _q(ex * rate / Decimal("100"))
        inc = _q(ex + vat)
        out.append({
            "description": getattr(l, "description", "") or "",
            "quantity": qty,
            "unit_price_excl": unit,
            "vat_rate": rate,
            "line_excl": ex,
            "vat_amount": vat,
            "line_incl": inc,
        })
    return out

def _vat_summary(lines):
    bucket = {}
    for l in lines:
        r = int(l["vat_rate"])
        b = bucket.setdefault(r, {"rate": f"{r}%", "excl": Decimal("0.00"), "vat": Decimal("0.00"), "incl": Decimal("0.00")})
        b["excl"] = _q(b["excl"] + l["line_excl"])
        b["vat"] = _q(b["vat"] + l["vat_amount"])
        b["incl"] = _q(b["incl"] + l["line_incl"])
    return [bucket[k] for k in sorted(bucket)]

def _org_and_payment():
    org = {"name": "", "address": "", "vat": "", "email": "", "phone": ""}
    payment = {"iban": "", "bic": "", "ogm": ""}
    op = OrganizationProfile.objects.first()
    if op:
        org["name"] = getattr(op, "name", "") or ""
        org["address"] = getattr(op, "address", "") or ""
        org["vat"] = getattr(op, "vat_number", "") or getattr(op, "vat", "") or ""
        org["email"] = getattr(op, "email", "") or ""
        org["phone"] = getattr(op, "phone", "") or ""
        payment["iban"] = getattr(op, "iban", "") or ""
        payment["bic"] = getattr(op, "bic", "") or ""
    return org, payment

def _ctx_for(invoice):
    lines = _lines_for(invoice)
    vat_summary = _vat_summary(lines) if lines else []
    total_excl = _q(sum((l["line_excl"] for l in lines), Decimal("0.00")))
    total_vat = _q(sum((l["vat_amount"] for l in lines), Decimal("0.00")))
    total_incl = _q(total_excl + total_vat)
    org, payment = _org_and_payment()
    ogm = getattr(invoice, "structured_message", None) or getattr(invoice, "ogm", None) or ""
    if ogm:
        payment["ogm"] = ogm
    return {
        "invoice": invoice,
        "lines": lines,
        "vat_summary": vat_summary,
        "totals_parts": {
            "excl": _split_amount(total_excl),
            "vat": _split_amount(total_vat),
            "incl": _split_amount(total_incl),
        },
        "org": org,
        "payment": payment,
    }

@staff_member_required
def daily_invoice_preview(request, pk: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    ctx = _ctx_for(invoice)
    return render(request, "invoices/preview.html", ctx)

@staff_member_required
def daily_invoice_print(request, pk: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    ctx = _ctx_for(invoice)
    return render(request, "invoices/print.html", ctx)