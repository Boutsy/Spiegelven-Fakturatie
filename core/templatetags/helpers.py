from django import template
from decimal import Decimal, ROUND_HALF_UP

register = template.Library()

@register.filter
def get_item(d, key):
    if isinstance(d, dict):
        return d.get(key, "")
    return ""

@register.filter
def eur(value, digits=2):
    """
    Europese notatie: 1.234,56 — gebruik {{ bedrag|eur }} of {{ qty|eur:"0" }}
    """
    try:
        d = Decimal(value)
    except Exception:
        return value
    q = Decimal("1").scaleb(-int(digits))          # 10^-digits
    d = d.quantize(q, rounding=ROUND_HALF_UP)
    s = f"{d:,.{int(digits)}f}"                    # 1,234.56
    return s.replace(",", "§").replace(".", ",").replace("§", ".")

@register.filter(name="ogm")
def ogm(value):
    """
    Belgische OGM als +++123/4567/89012+++ (12 cijfers). Anders ongewijzigd.
    """
    s = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(s) == 12:
        return f"+++{s[0:3]}/{s[3:7]}/{s[7:12]}+++"
    return str(value or "")
