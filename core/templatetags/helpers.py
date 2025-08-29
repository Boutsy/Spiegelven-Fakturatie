from decimal import Decimal, ROUND_HALF_UP
from django import template

register = template.Library()

@register.filter
def get_item(d, key):
    if isinstance(d, dict):
        return d.get(key, "")
    return ""

@register.filter
def eur(value, digits=2):
    """
    Europese notatie: duizendtallen met '.', decimalen met ','.
    Voorbeeld: 1234.5 -> '1.234,50'
    Gebruik: {{ bedrag|eur }} of {{ qty|eur:"0" }}
    """
    try:
        d = Decimal(value)
    except Exception:
        return value
    q = Decimal("1").scaleb(-int(digits))  # 10^-digits
    d = d.quantize(q, rounding=ROUND_HALF_UP)
    s = f"{d:,.{int(digits)}f}"                  # '12,345.67' (US)
    return s.replace(",", "§").replace(".", ",").replace("§", ".")  # -> '12.345,67'

@register.filter(name="ogm")
def ogm(value):
    """
    Belgische gestructureerde mededeling:
    12 cijfers -> +++123/4567/89012+++
    Anders: originele waarde.
    """
    s = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(s) == 12:
        return f"+++{s[0:3]}/{s[3:7]}/{s[7:12]}+++"
    return value or ""
