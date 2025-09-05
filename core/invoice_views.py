from datetime import date
from decimal import Decimal
from django.apps import apps
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render

from core.billing import prorated_investment_amount, prorated_flex_amount

Member          = apps.get_model("core","Member")
YearPricing     = apps.get_model("core","YearPricing")
YearInvestScale = apps.get_model("core","YearInvestScale")

def _age_on_jan1(year:int, dob):
    if not dob:
        return None
    ref = date(year,1,1)
    return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))

def _role_tag(member):
    v = (getattr(member, "household_role", "") or "").strip().lower()
    return "PRT" if v in {"prt","partner","partner_role","husband","wife"} else "IND"

def _base_invest_amount_and_vat2(member, year: int) -> tuple[Decimal, int]:
    """
    Bepaalt het totale investeringsbedrag (zonder spreiding) + BTW%.
    Volgorde:
      1) YearInvestScale (voor 60-69 etc.)
      2) YearPricing code: INV_IND / INV_PRT
      3) Fallback: 2695 (IND) / 1355 (PRT), vat=21
    """
    role = _role_tag(member)
    age = _age_on_jan1(year, getattr(member,"date_of_birth",None))

    # 1) YearInvestScale
    if age is not None:
        try:
            rec = YearInvestScale.objects.get(age=age, role=role)
            vat = getattr(rec, "vat_rate", None)
            try:
                vat = int(vat) if vat is not None else 21
            except Exception:
                vat = 21
            return (rec.amount_normal, vat)
        except YearInvestScale.DoesNotExist:
            pass

    # 2) YearPricing
    code = "INV_PRT" if role == "PRT" else "INV_IND"
    yp = YearPricing.objects.filter(year=year, code=code).first()
    if yp:
        # probeer meerdere mogelijke veldnamen
        for fld in ("unit_price","price","amount","amount_excl"):
            if hasattr(yp, fld):
                amount = getattr(yp, fld)
                if amount is not None:
                    break
        else:
            amount = Decimal("0.00")
        vat = getattr(yp, "vat_rate", 21) or 21
        try:
            vat = int(vat)
        except Exception:
            vat = 21
        return (Decimal(str(amount)), vat)

    # 3) Fallback
    return (Decimal("1355.00") if role=="PRT" else Decimal("2695.00"), 21)

def _add_line(lines, desc:str, amount:Decimal, vat:int):
    lines.append({
        "description": desc,
        "quantity": Decimal("1"),
        "unit_price_excl": amount,
        "vat_rate": Decimal(str(vat)),
    })

def _fix_preview_prorata(lines, member):
    return

@staff_member_required
def invoice_preview(request, member_id:int, year:int):
    member = get_object_or_404(Member, pk=member_id)
    lines = []
    warnings = []

    # 1) Basistarief investering (totale som)
    total_invest, vat_invest = _base_invest_amount_and_vat2(member, year)

    # 2) INVESTERING: pro-rata
    inv_years_total = int(getattr(member, "investment_years_total", 0) or 0)
    inv_years_rem   = int(getattr(member, "investment_years_remaining", 0) or 0)
    if inv_years_total > 0 and inv_years_rem > 0 and total_invest > 0:
        per_year = prorated_investment_amount(member, total_invest)
        nth = inv_years_total - inv_years_rem + 1
        _add_line(lines, f"Investering (jaar {nth}/{inv_years_total})", per_year, vat_invest)

    # 3) FLEX: per jaar — locked bedrag of pro-rata + 17%
    flex_years_total = int(getattr(member, "flex_years_total", 0) or 0)
    flex_years_rem   = int(getattr(member, "flex_years_remaining", 0) or 0)
    if flex_years_total > 0 and flex_years_rem > 0:
        locked = getattr(member, "invest_flex_locked_amount", None)
        if locked is not None:
            flex_amount = Decimal(str(locked))
        else:
            base = (total_invest / Decimal(flex_years_total)) if flex_years_total else Decimal("0.00")
            flex_amount = (base * Decimal("1.17"))
        flex_amount = flex_amount.quantize(Decimal("0.01"))
        nth = flex_years_total - flex_years_rem + 1
        _add_line(lines, f"Flex (jaar {nth}/{flex_years_total})", flex_amount, vat_invest)

    # 4) Totalen
    total_excl = Decimal("0.00")
    total_vat = Decimal("0.00")
    for d in lines:
        qty = d["quantity"] or Decimal("1")
        up  = d["unit_price_excl"] or Decimal("0.00")
        excl = qty * up
        vat_rate = Decimal(str(d.get("vat_rate") or "0"))
        vat_amt = excl * vat_rate / 100
        total_excl += excl
        total_vat  += vat_amt

    ctx = {
        "member": member,
        "year": year,
        "lines": lines,
        "warnings": warnings,
        "total_excl": total_excl,
        "total_vat": total_vat,
        "total_incl": total_excl + total_vat,
    }
    return render(request, "admin/invoice_preview.html", ctx)

@staff_member_required
def invoice_preview_default_next_year(request, member_id:int):
    return invoice_preview(request, member_id, date.today().year + 1)

@staff_member_required
def invoice_preview_default(request, member_id:int):
    return invoice_preview(request, member_id, date.today().year)

def _base_invest_amount_and_vat2(member, year: int) -> tuple[Decimal, int]:
    """
    Haal basis investeringsbedrag (IND/PRT) + BTW uit YearPricing.
    Let op: in dit model heet het bedrag **amount**.
    """
    role_val = (getattr(member, "household_role", "") or "").strip().lower()
    role = "PRT" if role_val in {"prt", "partner", "husband", "wife"} else "IND"
    code = "INV_PRT" if role == "PRT" else "INV_IND"
    yp = YearPricing.objects.filter(year=year, code=code, active=True).first()
    if yp is not None:
        amt = getattr(yp, "amount", None) or Decimal("0.00")
        vat = int(getattr(yp, "vat_rate", 21) or 21)
        return amt, vat
    return Decimal("0.00"), 21

