from django.core.management.base import BaseCommand, CommandError
from core.models import ImportMapping
import os, csv, re, unicodedata

def _norm_header(s):
    s = s or ""
    s = unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode()
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    return s

def _code_alias(code):
    if not code:
        return code
    c = code.strip().upper()
    c = c.replace("-", "_").replace(" ", "_")
    c = re.sub(r"[^A-Z0-9_]", "_", c)
    c = re.sub(r"_+", "_", c).strip("_")
    return c

def _sniff_reader(path):
    with open(path,"r",encoding="utf-8",newline="") as f:
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
        msg = f"Kon verplichte kolommen niet vinden. Header={header!r} — vereist minstens 'Afkorting/Code' en 'Hoe factureren'."
        raise CommandError(msg)
    return idx

def _rows_to_records(rows, idx):
    records=[]
    cur=None
    max_i = max([i for i in idx.values() if i is not None] or [-1])
    for r in rows:
        if len(r) <= max_i:
            r = r + [""] * (max_i + 1 - len(r))
        code  = (r[idx["code"]] or "").strip()
        desc  = (r[idx["desc"]] or "").strip() if idx["desc"] is not None else ""
        rules = (r[idx["rules"]] or "").strip() if idx["rules"] is not None else ""
        if code:
            cur={"code":code, "description":desc, "rules_lines":[]}
            if rules:
                cur["rules_lines"].append(rules)
            records.append(cur)
        else:
            if cur is not None and rules:
                cur["rules_lines"].append(rules)
    return records

def _heuristics(code, desc, rules_text):
    t=(desc+"\n"+rules_text).lower()
    d={}
    # bill_to
    if "eigen factuur" in t:
        d["bill_to"]="self"
    if "gezinshoofd" in t or "gelinkte gezinshoofd" in t:
        d["bill_to"]="head"
    # course
    if "course" in t:
        if "cc" in t: d["course"]="CC"
        if "mac" in t: d["course"]="MAC"
    # leeftijd
    m=re.search(r"ouder\s+dan\s+(\d+)", t)
    if m:
        d["age_min"]=int(m.group(1))+1
    m=re.search(r"vanaf\s+(\d+)\s*jaar", t)
    if m:
        d.setdefault("age_min", int(m.group(1)))
    # flex
    if "flex" in t:
        d["mode"]="flex"; d["flex"]=True; d["flex_years"]=7
    # assets
    if "elektr" in t and ("kar" in t or "garage" in t):
        d.update({"kind":"asset_e_trolley","requires_asset":"e_trolley_locker","include_asset_identifier":True,"description_template":"Elektrische kar-kast {identifier}"})
    elif (("kar" in t and "kast" in t) or "karrengarage" in t):
        d.update({"kind":"asset_trolley","requires_asset":"trolley_locker","include_asset_identifier":True,"description_template":"Karrengarage {identifier}"})
    elif "kast" in t:
        d.update({"kind":"asset_locker","requires_asset":"locker","include_asset_identifier":True,"description_template":"Kast {identifier}"})
    # defaults
    if (code or "").upper().startswith("LID"):
        d.setdefault("kind","membership")
    if "partner" in t and ("investerings" in t or "investering" in t):
        d["kind"]="investment_partner"; d["use_invest_scale"]=True; d["role"]="PRT"
    return d or {"raw": rules_text}

class Command(BaseCommand):
    help = "Lees prijslijst-CSV (NL koppen, ; of ,), groepeer regels per code, maak ImportMapping 'csv_prijslijst'. Voegt alias-code toe (hyphen→underscore)."

    def add_arguments(self, parser):
        parser.add_argument("--csv", required=True, help="Pad naar CSV.")
        parser.add_argument("--show", action="store_true", help="Toon mapping in console.")

    def handle(self, *args, **opts):
        path=opts["csv"]
        if not os.path.exists(path):
            raise CommandError(f"CSV niet gevonden: {path}")
        header, rows = _sniff_reader(path)
        idx = _find_indexes(header)
        records = _rows_to_records(rows, idx)

        mapping_list=[]
        alias_notes=[]
        for rec in records:
            code_raw = rec["code"]
            code_norm = _code_alias(code_raw)
            rules_text = "\n".join(rec["rules_lines"])
            data = _heuristics(code_raw, rec.get("description",""), rules_text)
            mapping_list.append({"code": code_raw, "data": data})
            if code_norm and code_norm != code_raw:
                mapping_list.append({"code": code_norm, "data": data})
                alias_notes.append((code_raw, code_norm))

        imp, _ = ImportMapping.objects.get_or_create(name="csv_prijslijst", model="YearRule")
        imp.mapping = {m["code"]: m["data"] for m in mapping_list}
        imp.save()

        if opts.get("show"):
            self.stdout.write(self.style.MIGRATE_HEADING(f"{len(mapping_list)} mapping-entries (incl. alias-codes)"))
            for m in mapping_list:
                self.stdout.write(f"{m['code']}: {m['data']}")
            if alias_notes:
                self.stdout.write(self.style.WARNING("Alias-codes toegevoegd (CSV → genormaliseerd):"))
                for a,b in alias_notes:
                    self.stdout.write(f"  {a}  ->  {b}")

        self.stdout.write(self.style.SUCCESS("Mapping opgeslagen als ImportMapping 'csv_prijslijst'."))
