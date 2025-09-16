import re

DIGITS = re.compile(r"\D+")

def _only_digits(s: str) -> str:
    return DIGITS.sub("", s or "")

def normalize_phone_be_store(raw: str) -> str:
    """
    Zet naar een stabiel opslagformaat:
    - BE nationaal (beginnend met 0...): -> +32... (0 valt weg)
    - 00..  -> +..
    - +..   -> laat +.. staan (alleen cijfers erna)
    - anders: return ontdaan van niet-cijfers (zonder +)
    """
    if not raw:
        return ""
    s = raw.strip()
    # 00.. -> +..
    if s.startswith("00"):
        s = "+" + s[2:]
    # +.. internationaal
    if s.startswith("+"):
        return "+" + _only_digits(s[1:])
    # Nationaal BE: 0xxxxxxxxx -> +32xxxxxxxxx (zonder 0)
    d = _only_digits(s)
    if d.startswith("0"):
        return "+32" + d[1:]
    # Anders: bewaar als plain digits (zeldzaam)
    return d

def _chunks(s, sizes):
    out, i = [], 0
    for n in sizes:
        out.append(s[i:i+n])
        i += n
    if i < len(s):
        out.append(s[i:])
    return out

def format_phone_be_display(stored: str) -> str:
    """
    Mooi formaat voor UI:
    - Als opslag +32…: probeer mobiel/vast pattern te tonen.
    - Als opslag +CC… (niet 32): toon +CC/… met punten
    - Als opslag digits-only: val terug op eenvoudige groepering.
    """
    if not stored:
        return "—"
    s = stored.strip()
    if s.startswith("+"):
        digits = s[1:]
        # België
        if digits.startswith("32"):
            rest = digits[2:]
            # Mobiel: 4xx xx xx xx (9 cijfers)
            if rest.startswith("4") and len(rest) >= 9:
                # naar 04xx/xx.xx.xx
                nat = "0" + rest  # 04...
                return f"{nat[0:4]}/{nat[4:6]}.{nat[6:8]}.{nat[8:10]}"
            # Vast (2-digit zone): 1e na 0 zou 2/3/4/9 zijn, maar we hebben al +32 zonder 0.
            # We reconstrueren nationale vorm met 0:
            nat = "0" + rest
            # 2-digit zone (0x...): totale lengte vaak 9
            if len(nat) >= 9 and nat[1] in "2349":
                return f"{nat[0:2]}/{nat[2:5]}.{nat[5:7]}.{nat[7:9]}"
            # 3-digit zone (0xx...): vaak 10
            if len(nat) >= 10:
                return f"{nat[0:3]}/{nat[3:5]}.{nat[5:7]}.{nat[7:9]}"
            # fallback
            d = _only_digits(nat)
            if len(d) >= 9:
                return d[0:3] + "/" + ".".join(_chunks(d[3:], [2,2,2]))
            return d
        # Niet-Belgisch: +CC/… met puntsgewijze groepen
        if len(digits) >= 8:
            parts = _chunks(digits, [3,2,2,2])
            return f"+{parts[0]}/" + ".".join(parts[1:])
        return "+" + digits
    # Digits only opgeslagen (fallback)
    d = _only_digits(s)
    if len(d) >= 10 and d.startswith("04"):
        return f"{d[0:4]}/{d[4:6]}.{d[6:8]}.{d[8:10]}"
    if len(d) >= 9:
        return d[0:3] + "/" + ".".join(_chunks(d[3:], [2,2,2]))
    return d or "—"
