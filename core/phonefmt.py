import re

def _digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def _chunks(s, sizes):
    out, i = [], 0
    for n in sizes:
        out.append(s[i:i+n])
        i += n
    if i < len(s):
        out.append(s[i:])
    return out

def format_phone_be(raw: str) -> str:
    """
    Heuristische formatter voor BE-nummers.
    - Internationaal: 00.. -> +.. ; laat verder 'netjes' met slashes/puntjes
    - Mobiel: 04xx/xx.xx.xx
    - Vast 2-digit zone (0x): 0x/xxx.xx.xx
    - Vast 3-digit zone (0xx): 0xx/xx.xx.xx
    Valt het buiten patroon? geef raw opgeschoond terug.
    """
    if not raw: return ""
    s = raw.strip()
    # 00.. -> +..
    if s.startswith("00"):
        s = "+" + s[2:]
    # Als internationaal met +: laat plus staan, verwijder ruis na de landcode en groepeer basic
    if s.startswith("+"):
        d = "+" + _digits(s)
        # Probeer +32-specifiek te verfraaien
        if d.startswith("+32"):
            rest = d[3:]  # zonder +32
            # maak 0 weg als het 0-prefixed nationale vorm was
            if rest.startswith("0"):
                rest = rest[1:]
            # mobiele BE na +32: 4xx xx xx xx
            if rest.startswith("4") and len(rest) >= 9:
                parts = _chunks(rest, [3,2,2,2])  # 4xx/xx.xx.xx (met extra groep)
                return "+32/" + parts[0] + "." + ".".join(parts[1:])
            # vast BE: heuristiek — 1 of 2-digit zonecode (na 0 verwijderd)
            # hier is 32-variant zonder 0; zonecodes variëren. Groepeer in 2-2-2-... na een eerste 1-2-3 blok is lastig.
            # Toon gewoon "+32/" + blokken van 3-2-2-2 indien >= 9
            if len(rest) >= 8:
                parts = _chunks(rest, [2,2,2,2])  # best-effort
                return "+32/" + ".".join(parts)
        # generiek internationaal: laat + en groepeer in 3-2-2-2 als kan
        d2 = d[1:]
        if len(d2) >= 8:
            parts = _chunks(d2, [3,2,2,2])
            return "+" + parts[0] + "/" + ".".join(parts[1:])
        return d

    # Nationaal: alleen cijfers
    d = _digits(s)
    if not d:
        return ""

    # Mobiel (04..), typisch 10 cijfers
    if d.startswith("04") and len(d) >= 10:
        # 04xx/xx.xx.xx
        op = d[0:4] + "/" + d[4:6] + "." + d[6:8] + "." + d[8:10]
        return op

    # Vast: 0x... of 0xx...
    if d.startswith("0") and len(d) >= 9:
        # 2-digit zone: 0x...
        if d[1] in "2349" and len(d) >= 9:
            # 0x/xxx.xx.xx
            return f"{d[0:2]}/{d[2:5]}.{d[5:7]}.{d[7:9]}"
        # 3-digit zone: 0xx...
        if len(d) >= 10:
            # 0xx/xx.xx.xx
            return f"{d[0:3]}/{d[3:5]}.{d[5:7]}.{d[7:9]}"

    # fallback: geef iets net opgekuist terug met punt-groepering
    if len(d) >= 9:
        return d[0:3] + "/" + ".".join(_chunks(d[3:], [2,2,2]))
    return d
