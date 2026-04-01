from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import render, get_object_or_404
from .models import Invoice, OrganizationProfile

def _D(x):
    try:
        return Decimal(x or 0)
    except Exception:
        return Decimal(0)

Q2 = Decimal("0.01")

def _q2(x):
    return Decimal(x).quantize(Q2, rounding=ROUND_HALF_UP)

def _fmt_be_parts(x):
    q = _q2(x)
    s = f"{q:,.2f}"
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    left, right = s.split(",")
    return {"int": left, "dec": right}

def invoice_preview(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    line_objs = list(invoice.lines.all().order_by("id"))

    tot_excl = Decimal("0")
    tot_vat  = Decimal("0")
    summary  = {}

    for l in line_objs:
        qty  = _q2(_D(getattr(l, "quantity", 0)))
        unit = _q2(_D(getattr(l, "unit_price_excl", 0)))
        rate = _D(getattr(l, "vat_rate", 0))
        l.vat_rate_display = int(rate)

        line_excl = _q2(qty * unit)
        vat_amount = _q2(line_excl * rate / Decimal("100"))
        line_incl  = _q2(line_excl + vat_amount)

        tot_excl += line_excl
        tot_vat  += vat_amount

        bucket = summary.setdefault(rate, [Decimal("0"), Decimal("0"), Decimal("0")])
        bucket[0] += line_excl
        bucket[1] += vat_amount
        bucket[2] += line_incl

        l.line_excl  = line_excl
        l.vat_amount = vat_amount
        l.line_incl  = line_incl

    tot_excl = _q2(tot_excl)
    tot_vat  = _q2(tot_vat)
    tot_incl = _q2(tot_excl + tot_vat)

    vat_summary = [
        {
            "rate": f"{int(r)}%" if r == r.to_integral() else f"{r}%",
            "excl": v[0],
            "vat":  v[1],
            "incl": v[2],
        }
        for r, v in sorted(summary.items(), key=lambda t: t[0])
    ]

    org = None
    org_qs = OrganizationProfile.objects.all()
    if org_qs.exists():
        def _score(o):
            fields = ["name", "address_line1", "address_line2", "postal_code", "city",
                      "country", "iban", "bic", "email", "website", "vat_number"]
            return sum(1 for f in fields if getattr(o, f, None))
        org = sorted(org_qs, key=_score, reverse=True)[0]

    payment = {
        "iban": getattr(org, "iban", "") if org else "",
        "bic":  getattr(org, "bic", "") if org else "",
        "ogm":  invoice.payment_reference_display(),
    }

    ctx = {
        "invoice": invoice,
        "lines": line_objs,
        "totals": {"excl": tot_excl, "vat": tot_vat, "incl": tot_incl},
        "totals_parts": {
            "excl": _fmt_be_parts(tot_excl),
            "vat":  _fmt_be_parts(tot_vat),
            "incl": _fmt_be_parts(tot_incl),
        },
        "vat_summary": vat_summary,
        "org": org,
        "payment": payment,
    }

    return render(request, "invoices/preview.html", ctx)
