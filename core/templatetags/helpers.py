from django import template
register = template.Library()

@register.filter
def get_item(d, key):
    if isinstance(d, dict):
        return d.get(key, "")
    return ""

# --- EURO getalnotatie: 1.234,56 -------------------------------------------
from decimal import Decimal, ROUND_HALF_UP
from django import template

register = template.Library()

@register.filter
def eur(value, digits=2):
    """
    Format Decimal/float naar Europese notatie:
    duizendtallen met '.' en decimalen met ','. Voorbeeld: 1234.5 -> '1.234,50'
    Gebruik: {{ bedrag|eur }} of {{ qty|eur:"0" }}
    """
    try:
        d = Decimal(value)
    except Exception:
        return value  # laat ongewijzigd als het niet kan

    # afronden op 'digits' decimalen
    q = Decimal("1").scaleb(-int(digits))  # 10^-digits
    d = d.quantize(q, rounding=ROUND_HALF_UP)

    # eerst Engels format (1,234.56), dan omwisselen naar EU (1.234,56)
    s = f"{d:,.{int(digits)}f}"
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return s