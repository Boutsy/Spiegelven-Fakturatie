from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from django.apps import apps
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import get_template
from django.utils import timezone

from .billing import prorated_investment_amount, prorated_flex_amount

Invoice = apps.get_model("core", "Invoice")
InvoiceLine = apps.get_model("core", "InvoiceLine")
OrganizationProfile = apps.get_model("core", "OrganizationProfile")
Product = apps.get_model("core", "Product")
Member = apps.get_model("core", "Member")
try:
    MemberAsset = apps.get_model("core", "MemberAsset")
except LookupError:
    MemberAsset = None
try:
    YearPricing = apps.get_model("core", "YearPricing")
except LookupError:
    YearPricing = None

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
            fields = [
                "name","address_line1","address_line2","postal_code","city","country",
                "iban","bic","email","website","vat_number",
                "phone","fax",   # <- toegevoegd
            ]
            return sum(1 for f in fields if getattr(o, f, None))
        op = sorted(qs, key=_score, reverse=True)[0]

    # Geef ALLE velden door zodat templates zoals _footer_org.html ze kunnen gebruiken
    org = {
        "id": getattr(op, "id", None) if op else None, 
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
        "phone": getattr(op, "phone", "") if op else "",
        "fax": getattr(op, "fax", "") if op else "",
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


# ---------- Lidfactuur-preview (volgend jaar) ----------

def _member_age_on(year: int, dob):
    if not dob:
        return None
    ref = date(year, 1, 1)
    try:
        return max(0, ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day)))
    except Exception:
        return None

def _member_role_tag(member):
    val = (getattr(member, "household_role", "") or "").strip().lower()
    if val in {"prt", "partner", "partner_role", "husband", "wife"}:
        return "PRT"
    if val in {"kid", "child"}:
        return "KID"
    return "IND"

def _membership_codes(member, year: int):
    course = (getattr(member, "course", "") or "").strip().upper()
    age = _member_age_on(year, getattr(member, "date_of_birth", None) or getattr(member, "birth_date", None))
    role = _member_role_tag(member)

    lid = None
    fed = None

    if course == "CC":
        if age is None:
            lid = f"LID_CC_{role}"
            fed = f"FED_CC_{role if role in {'IND', 'PRT'} else 'IND'}"
        elif age <= 15:
            lid, fed = "LID_CC_KID_0_15", "FED_CC_KID"
        elif 16 <= age <= 21:
            lid, fed = "LID_CC_KID_16_21", "FED_CC_KID"
        elif 22 <= age <= 26:
            lid, fed = "LID_CC_YA_22_26", f"FED_CC_{role}"
        elif 27 <= age <= 29:
            lid, fed = "LID_CC_YA_27_29", f"FED_CC_{role}"
        elif 30 <= age <= 35:
            lid, fed = "LID_CC_YA_30_35", f"FED_CC_{role}"
        else:
            lid, fed = f"LID_CC_{role}", f"FED_CC_{role}"
    elif course == "P3":
        base = role if role in {"IND", "PRT"} else "IND"
        if age is None:
            lid = f"P3_{base}"
        elif age <= 21:
            lid = "P3_KID"
        else:
            lid = f"P3_{base}"
        fed = None

    return [c for c in (lid, fed) if c]

def _investment_codes(member, year: int):
    codes = []
    mode = (getattr(member, "membership_mode", "") or "").strip().lower()
    role = _member_role_tag(member)
    if mode == "investment":
        codes.append(f"INV_{role}")
        start = getattr(member, "invest_flex_start_year", None)
        if start and isinstance(start, int) and year >= start:
            codes.append(f"INV_FLEX_{role}")
    return codes

def _asset_codes(member):
    if MemberAsset is None:
        return []
    qs = MemberAsset.objects.filter(member=member)
    try:
        qs = qs.filter(active=True)
    except Exception:
        pass
    return [c for c in qs.values_list("asset_type", flat=True) if c]

def _unique_keep_order(seq):
    seen = set()
    out = []
    for item in seq:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out

def _apply_proration(lines, member):
    for line in lines:
        code = (line.get("code") or "").upper()
        desc = (line.get("desc") or "").lower()
        qty = Decimal(str(line.get("qty", "1")))
        total = Decimal(str(line.get("total", "0") or 0))

        if qty <= 0:
            qty = Decimal("1")

        if any(tag in code for tag in ("INV_IND", "INV_PRT")) or "invest" in desc:
            new_total = prorated_investment_amount(member, total)
            if new_total > 0:
                line["total"] = new_total
                line["unit"] = (new_total / qty).quantize(Decimal("0.01"))
                try:
                    total_years = int(getattr(member, "investment_years_total", 0) or 0)
                    remaining = int(getattr(member, "investment_years_remaining", 0) or 0)
                    if total_years > 0 and remaining > 0:
                        nth = total_years - remaining + 1
                        line["desc"] = f"{line.get('desc') or 'Investering'} (jaar {nth}/{total_years})"
                except Exception:
                    pass
            else:
                line["total"] = Decimal("0.00")
                line["unit"] = Decimal("0.00")
            continue

        if "INV_FLX" in code or "flex" in desc:
            locked = getattr(member, "invest_flex_locked_amount", None)
            if locked is not None:
                new_total = Decimal(str(locked)).quantize(Decimal("0.01"))
            else:
                new_total = prorated_flex_amount(member, total)

            if new_total > 0:
                line["total"] = new_total
                line["unit"] = (new_total / qty).quantize(Decimal("0.01"))
                try:
                    total_years = int(getattr(member, "flex_years_total", 0) or 0)
                    remaining = int(getattr(member, "flex_years_remaining", 0) or 0)
                    if total_years > 0 and remaining > 0:
                        nth = total_years - remaining + 1
                        line["desc"] = f"{line.get('desc') or 'Flex'} (jaar {nth}/{total_years})"
                except Exception:
                    pass
            else:
                line["total"] = Decimal("0.00")
                line["unit"] = Decimal("0.00")

DESCRIPTIONS = {
    "LID_CC_IND": "Lidgeld CC (individueel)",
    "LID_CC_PRT": "Lidgeld CC (partner)",
    "LID_CC_KID_0_15": "Lidgeld CC (kind 0–15)",
    "LID_CC_KID_16_21": "Lidgeld CC (kind 16–21)",
    "LID_CC_YA_22_26": "Lidgeld CC (jongvolw. 22–26)",
    "LID_CC_YA_27_29": "Lidgeld CC (jongvolw. 27–29)",
    "LID_CC_YA_30_35": "Lidgeld CC (jongvolw. 30–35)",
    "FED_CC_IND": "Federatie CC (individueel)",
    "FED_CC_PRT": "Federatie CC (partner)",
    "FED_CC_KID": "Federatie CC (kind)",
    "P3_IND": "Lidgeld P3 (individueel)",
    "P3_PRT": "Lidgeld P3 (partner)",
    "P3_KID": "Lidgeld P3 (kind)",
    "INV_IND": "Investering (individueel)",
    "INV_PRT": "Investering (partner)",
    "INV_FLEX_IND": "Investering flex (individueel)",
    "INV_FLEX_PRT": "Investering flex (partner)",
    "VST_KAST": "Kast",
    "KAR_KLN": "Kar-kast",
    "KAR_ELEC": "E-kar-kast",
}

@staff_member_required
def member_invoice_preview(request, member_id: int, year: int):
    member = get_object_or_404(Member, pk=member_id)
    year = int(year)

    wanted = _unique_keep_order(
        _membership_codes(member, year)
        + _investment_codes(member, year)
        + _asset_codes(member)
    )

    price_map = {}
    if YearPricing is not None and wanted:
        for yp in YearPricing.objects.filter(year=year, code__in=wanted):
            try:
                price_map[yp.code] = Decimal(str(yp.amount or "0")).quantize(Decimal("0.01"))
            except Exception:
                price_map[yp.code] = Decimal("0.00")

    lines = []
    notes = []
    for code in wanted:
        amount = price_map.get(code)
        if amount is None:
            notes.append(f"Geen prijs gevonden voor code {code} ({year}).")
            amount = Decimal("0.00")
        qty = Decimal("1")
        lines.append({
            "code": code,
            "desc": DESCRIPTIONS.get(code, code),
            "qty": qty,
            "unit": amount,
            "total": amount * qty,
        })

    _apply_proration(lines, member)

    total = sum((Decimal(str(line.get("total", "0") or 0)) for line in lines), Decimal("0.00"))

    ctx = {
        "member": member,
        "year": year,
        "lines": lines,
        "total": total,
        "notes": notes,
    }
    return render(request, "admin/invoice_preview.html", ctx)

@staff_member_required
def member_invoice_preview_default(request, member_id: int):
    year = timezone.now().year + 1
    return member_invoice_preview(request, member_id, year)
