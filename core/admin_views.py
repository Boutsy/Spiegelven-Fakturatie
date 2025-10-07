from decimal import Decimal, ROUND_HALF_UP
from django.apps import apps
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import get_template

Invoice = apps.get_model("core", "Invoice")
InvoiceLine = apps.get_model("core", "InvoiceLine")
OrganizationProfile = apps.get_model("core", "OrganizationProfile")
Product = apps.get_model("core", "Product")

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
    # Kies het meest complete OrganizationProfile
    qs = OrganizationProfile.objects.all()
    op = None
    if qs.exists():
        def _score(o):
            fields = ["name","address_line1","address_line2","postal_code","city","country","iban","bic","email","website","vat_number"]
            return sum(1 for f in fields if getattr(o, f, None))
        op = sorted(qs, key=_score, reverse=True)[0]

    # Geef ALLE velden door zodat templates zoals _footer_org.html ze kunnen gebruiken
    org = {
        "name": getattr(op, "name", "") if op else "",
        "address_line1": getattr(op, "address_line1", "") if op else "",
        "address_line2": getattr(op, "address_line2", "") if op else "",
        "postal_code": getattr(op, "postal_code", "") if op else "",
        "city": getattr(op, "city", "") if op else "",
        "country": getattr(op, "country", "") if op else "",
        "vat_number": getattr(op, "vat_number", "") if op else "",
        "email": getattr(op, "email", "") if op else "",
        "website": getattr(op, "website", "") if op else "",
        "iban": getattr(op, "iban", "") if op else "",
        "bic": getattr(op, "bic", "") if op else "",
    }
    payment = {
        "iban": org["iban"],
        "bic": org["bic"],
        "ogm": "",
    }
    return org, payment

def _ctx_for(invoice):
    lines = _lines_for(invoice)
    vat_summary = _vat_summary(lines) if lines else []
    total_excl = _q(sum((l["line_excl"] for l in lines), Decimal("0.00")))
    total_vat = _q(sum((l["vat_amount"] for l in lines), Decimal("0.00")))
    total_incl = _q(total_excl + total_vat)
    org, payment = _org_and_payment()
    ogm = getattr(invoice, "payment_reference_display", None)
    if callable(ogm):
        payment["ogm"] = invoice.payment_reference_display()
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

# ---------- Dagfactuur (preview/print) in 2 smaken ----------

@staff_member_required
def daily_invoice_preview_logo(request, pk: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    ctx = _ctx_for(invoice)
    tpl = "invoices/preview_logo.html"
    try:
        get_template(tpl)
    except Exception:
        tpl = "invoices/preview.html"
    return render(request, tpl, ctx)

@staff_member_required
def daily_invoice_preview_preprinted(request, pk: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    ctx = _ctx_for(invoice)
    tpl = "invoices/preview_preprinted.html"
    try:
        get_template(tpl)
    except Exception:
        tpl = "invoices/preview.html"
    return render(request, tpl, ctx)

@staff_member_required
def daily_invoice_print_logo(request, pk: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    ctx = _ctx_for(invoice)
    tpl = "invoices/print_logo.html"
    try:
        get_template(tpl)
    except Exception:
        tpl = "invoices/print.html"
    return render(request, tpl, ctx)

@staff_member_required
def daily_invoice_print_preprinted(request, pk: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    ctx = _ctx_for(invoice)
    tpl = "invoices/print_preprinted.html"
    try:
        get_template(tpl)
    except Exception:
        tpl = "invoices/print.html"
    return render(request, tpl, ctx)

# ---------- Product-catalogus voor inline autofill ----------

@staff_member_required
def products_catalog_json(request):
    data = {}
    for p in Product.objects.filter(active=True):
        try:
            vat = int(Decimal(str(getattr(p, "default_vat_rate", 21))))
        except Exception:
            vat = 21
        price = getattr(p, "default_price_excl", None)
        price_s = ""
        if price not in (None, ""):
            try:
                price_s = f"{Decimal(str(price)):.2f}"
            except Exception:
                price_s = ""
        data[str(p.id)] = {
            "name": getattr(p, "name", str(p)) or str(p),
            "unit_price_excl": price_s,
            "vat_rate": vat,
        }
    return JsonResponse(data)