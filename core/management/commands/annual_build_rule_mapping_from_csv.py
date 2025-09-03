from django.core.management.base import BaseCommand, CommandError
from core.models import ImportMapping
import os, csv, re, json, unicodedata

def _norm_header(s: str) -> str:
    s = s or ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    return s

def _code_alias(code: str) -> str:
    if not code:
        return code
    c = code.strip().upper()
    c = c.replace("-", "_").replace(" ", "_")
    c = re.sub(r"[^A-Z0-9_]", "_", c)
    c = re.sub(r"_+", "_", c).strip("_")
    return c

def _sniff_reader(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        sample = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        except csv.Error:
            class D(csv.excel): pass
            D.delimiter = ";"
            dialect = D()
        reader = csv.reader(f, dialect)
        try:
            header = next(reader)
        except StopIteration:
            raise CommandError("CSV is leeg.")
        return header, list(reader)

def _find_indexes(header):
    hmap = {_norm_header(h): i for i, h in enumerate(header)}
    def find(*cands):
        for c in cands:
            k = _norm_header(c)
            if k in hmap:
                return hmap[k]
        return None
    idx = {
        "code":  find("Afkorting","Code","Afk","Afkorting code"),
        "desc":  find("Omschrijving","Description","Naam","Product"),
        "price": find("Prijs","Amount","Bedrag"),
        "vat":   find("BTW-tarief","BTW tarief","BTW","VAT","VAT rate"),
        "rules": find("Hoe factureren","Regels","Uitleg","Factureren"),
    }
    if idx["code"] is None or idx["rules"] is None:
        raise CommandError(
            Kon