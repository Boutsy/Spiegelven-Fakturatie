from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from .models import Invoice, OrganizationProfile

def _D(x):
    try:
        return Decimal(x or 0)
    except Exception:
        return Decimal(0)

def invoice_preview(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    lines_qs = getattr(invoice, "lines", None)
    lines_qs = lines_qs.all().order_by("id") if lines_qs is not None else []
    lines = list(lines_qs)

    # ---- totalen & BTW-samenvatting berekenen ----
    tot_excl = Decimal("0")
    tot_vat  = Decimal("0")
    tot_incl = Decimal("0")

    # per BTW-tarief groeperen: rate -> [excl, vat, incl]
    summary = {}

    for l in lines:
        qty   = _D(getattr(l, "quantity", 0))
        unit  = _D(getattr(l, "unit_price_excl", 0))
        rate  = _D(getattr(l, "vat_rate", 0))  # bv. 21 voor 21%

        # bestaande velden gebruiken als ze er zijn, anders berekenen
        line_excl = getattr(l, "line_excl", None)
        if line_excl is None:
            line_excl = qty * unit
        else:
            line_excl = _D(line_excl)

        vat_amount = getattr(l, "vat_amount", None)
        if vat_amount is None:
            vat_amount = (line_excl * rate) / Decimal("100")
        else:
            vat_amount = _D(vat_amount)

        line_incl = getattr(l, "line_incl", None)
        if line_incl is None:
            line_incl = line_excl + vat_amount
        else:
            line_incl = _D(line_incl)

        tot_excl += line_excl
        tot_vat  += vat_amount
        tot_incl += line_incl

        if rate not in summary:
            summary[rate] = [Decimal("0"), Decimal("0"), Decimal("0")]
        summary[rate][0] += line_excl
        summary[rate][1] += vat_amount
        summary[rate][2] += line_incl

    vat_summary = [
        {
            "rate": f"{int(r)}%" if r == r.to_integral() else f"{r}%",
            "excl": v[0],
            "vat":  v[1],
            "incl": v[2],
        }
        for r, v in sorted(summary.items(), key=lambda t: t[0])
    ]

    # organisatie t.b.v. footer
    org = OrganizationProfile.objects.order_by("id").first()

    payment = {
        "iban": getattr(org, "iban", "") if org else "",
        "bic": getattr(org, "bic", "") if org else "",
        "ogm": getattr(invoice, "structured_message", ""),
    }

    ctx = {
        "invoice": invoice,
        "lines": lines,
        "totals": {"excl": tot_excl, "vat": tot_vat, "incl": tot_incl},
        "vat_summary": vat_summary,
        "org": org,
        "payment": payment,
    }
    return render(request, "invoices/preview.html", ctx)