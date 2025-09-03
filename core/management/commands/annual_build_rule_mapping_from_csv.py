from __future__ import annotations
import csv, json, re
from pathlib import Path
from typing import Dict, Any, List, Tuple
from django.core.management.base import BaseCommand, CommandError

# Herken NL-fragmenten -> gestandaardiseerde velden
def parse_lines(code: str, how_text: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    t = (how_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"^[•\-\s]+", "", L).strip() for L in t.split("\n") if L.strip()]
    low = "\n".join(lines).lower()

    # bill_to
    if "eigen factuur" in low:
        payload["bill_to"] = "self"
    if "gelinkt" in low and "gezinshoofd" in low:
        payload["bill_to"] = "head"
    if "gezinshoofd" in low and "indien geen" in low or "of bij zichzelf" in low:
        payload["bill_to"] = payload.get("bill_to", "head")  # head als voorkeur
    # fallback voor assets: factureer op gezinshoofd tenzij expliciet anders
    if code.startswith(("VST", "KAR", "KAE", "ELEC")) and "bill_to" not in payload:
        payload["bill_to"] = "head"

    # course
    if "course" in low:
        if "cc" in low:
            payload["course"] = "CC"
        elif "gc" in low:
            payload["course"] = "GC"
        elif "gp" in low:
            payload["course"] = "GP"

    # leeftijd
    m = re.search(r"ouder dan\s+(\d+)", low)
    if m:
        payload["age_min"] = int(m.group(1)) + 1
    m = re.search(r"vanaf\s+(\d+)\s*jaar", low)
    if m:
        payload["age_min"] = min(payload.get("age_min", 999), int(m.group(1)))

    # flex
    if "flex" in low:
        payload["mode"] = "flex"
        payload["flex"] = True
        payload["flex_years"] = 7

    # investerings-schaal (degenererend vanaf 60)
    if "degressief" in low or ("vanaf 60" in low and "invester" in low):
        payload["use_invest_scale"] = True

    # rol afleiden
    if "partner" in low or "prt" in code.lower():
        payload["role"] = "PRT"
    elif "individueel" in low or "ind" in code.lower():
        payload["role"] = "IND"

    # soort afleiden op basis van code + tekst
    if code.startswith("LID"):
        payload["kind"] = "membership"
    elif code.startswith("INV"):
        payload["kind"] = "investment_partner" if payload.get("role") == "PRT" else "investment_member"
    elif code.startswith(("VST", "KAR", "KAE", "ELEC")):
        # assets
        if "elektr" in low or "e-karr" in low or "e kar" in low or "elec" in code.lower():
            payload.update({"kind": "asset_e_trolley", "requires_asset": "e_trolley_locker"})
        elif "kar" in low or "trolley" in low or code.startswith(("KAR","KAE")):
            payload.update({"kind": "asset_trolley", "requires_asset": "trolley_locker"})
        else:
            payload.update({"kind": "asset_locker", "requires_asset": "locker"})
        payload["include_asset_identifier"] = True
        # Standaard-omschrijving (kan per code elders nog verfijnd worden)
        payload.setdefault("description_template", "{identifier}")

    elif "federale bijdrage" in low or code.startswith("FED"):
        payload["kind"] = "federation"

    return payload

def merge_mapping(existing: Dict[str, Any], additions: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    skipped = []
    merged = dict(existing)
    for code, payload in additions.items():
        if code in merged:
            skipped.append(code)
            continue
        merged[code] = payload
    return merged, skipped

class Command(BaseCommand):
    help = "Bouw/actualiseer core/data/year_rule_mapping.json vanuit core/data/prijslijst.csv"

    def add_arguments(self, parser):
        parser.add_argument("--csv", default="core/data/prijslijst.csv", help="Pad naar CSV (UTF-8)")
        parser.add_argument("--apply", action="store_true", help="Wegschrijven naar mapping + niet-dry-run rapport")
        parser.add_argument("--show", action="store_true", help="Toon resultaat (codes + payload)")

    def handle(self, *args, **opts):
        csv_path = Path(opts["csv"])
        if not csv_path.exists():
            raise CommandError(f"CSV niet gevonden: {csv_path}")

        # mapping inlezen (als aanwezig)
        mapping_path = Path("core/data/year_rule_mapping.json")
        existing = {}
        if mapping_path.exists():
            try:
                existing = json.loads(mapping_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # CSV sniffer
        data = csv_path.read_text(encoding="utf-8")
        dialect = csv.Sniffer().sniff(data.splitlines()[0] if data else ";")
        if dialect.delimiter not in (";", ","):
            # simpele fallback (NL Excel = ;)
            delimiter = ";"
        else:
            delimiter = dialect.delimiter

        reader = csv.reader(data.splitlines(), delimiter=delimiter)
        rows = list(reader)

        # Header detectie
        header = [h.strip().lower() for h in rows[0]]
        has_header = any(k in header for k in ["afkorting", "code", "hoe factureren"])
        idx = {"code":0, "desc":1, "price":2, "vat":3, "how":4}
        if has_header:
            def col(name,*alts):
                for n in (name,)+alts:
                    if n in header:
                        return header.index(n)
                return None
            idx["code"] = col("afkorting","code")
            idx["desc"] = col("omschrijving","description")
            idx["price"] = col("prijs","amount")
            idx["vat"] = col("btw","vat")
            idx["how"] = col("hoe factureren","hoe", "rules")
            rows = rows[1:]  # skip header

        additions: Dict[str, Any] = {}
        unknown: Dict[str, List[str]] = {}

        for r in rows:
            if not r or len(r) <= max([i for i in idx.values() if i is not None] or [-1]):
                continue
            code = (r[idx["code"]] or "").strip()
            if not code:
                continue
            how = (r[idx["how"]] or "").strip() if idx["how"] is not None else ""
            payload = parse_lines(code, how)

            # Verrijking op basis van bekende codes (consistent met eerdere regels)
            if code == "VST_KAST":
                payload.update({"description_template":"Kast {identifier}", "bill_to": payload.get("bill_to","head_or_self")})
            if code == "KAE_KLN":
                payload.update({"description_template":"Kar-kast {identifier}"})
            if code == "KAR_ELEC":
                payload.update({"description_template":"Karrengarage elektrisch {identifier}"})

            # Controle: als payload leeg is -> unknown
            if not payload:
                unknown.setdefault(code, []).append(how)
                continue

            additions[code] = payload

        merged, skipped = merge_mapping(existing, additions)

        # Rapportage
        self.stdout.write(self.style.MIGRATE_HEADING(f"Geparseerd uit CSV: {len(additions)} codes"))
        if skipped:
            self.stdout.write(self.style.WARNING(f"Overslagen (bestonden al): {sorted(skipped)}"))
        if unknown:
            self.stdout.write(self.style.WARNING(f"Niet herkende regels voor {len(unknown)} code(s): {sorted(unknown.keys())}"))
            Path("core/data/_unparsed_rules.txt").write_text(
                "\n\n".join([f"{k}:\n{''.join(v)}" for k,v in unknown.items()]), encoding="utf-8"
            )
            self.stdout.write(self.style.WARNING("Details -> core/data/_unparsed_rules.txt"))

        if opts["show"]:
            # toon een korte dump (alleen keys + kern)
            preview = {k: merged[k] for k in sorted(additions.keys())}
            self.stdout.write(json.dumps(preview, ensure_ascii=False, indent=2))

        if opts["apply"]:
            mapping_path.parent.mkdir(parents=True, exist_ok=True)
            mapping_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Weggeschreven: {mapping_path}"))
        else:
            self.stdout.write(self.style.SUCCESS("Dry-run: niets weggeschreven. Gebruik --apply om te bewaren."))
