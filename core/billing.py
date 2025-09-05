from decimal import Decimal, ROUND_HALF_UP

def quantize2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def prorated_investment_amount(member, total_investment: Decimal) -> Decimal:
    """
    Pro-rata deel van de investering voor dit jaar:
    - Alleen als years_total > 0 en years_remaining > 0.
    - Anders 0,00.
    """
    years_total = getattr(member, "investment_years_total", 0) or 0
    years_remaining = getattr(member, "investment_years_remaining", 0) or 0
    if years_total > 0 and years_remaining > 0:
        per_year = (Decimal(total_investment) / Decimal(years_total))
        return quantize2(per_year)
    return Decimal("0.00")

def prorated_flex_amount(member, total_flex: Decimal, surcharge: Decimal = Decimal("0.17")) -> Decimal:
    """
    Pro-rata deel van flex: (totaal/years_total) * (1 + surcharge)
    Standaard surcharge = 17% (0.17).
    Alleen als years_total > 0 en years_remaining > 0.
    """
    years_total = getattr(member, "flex_years_total", 0) or 0
    years_remaining = getattr(member, "flex_years_remaining", 0) or 0
    if years_total > 0 and years_remaining > 0:
        base = (Decimal(total_flex) / Decimal(years_total))
        with_surcharge = base * (Decimal("1.00") + Decimal(surcharge))
        return quantize2(with_surcharge)
    return Decimal("0.00")
