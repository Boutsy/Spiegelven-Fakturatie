
from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction
from django.db.models import Q
import csv, re
from datetime import datetime, date

Member = apps.get_model('core','Member')
MemberAsset = apps.get_model('core','MemberAsset')

def norm(s):
    return (s or "").strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")

def pick(row, *names):
    """Case-insensitive pick met normalisatie van kolomnamen."""
    d = {norm(k): (v or "").strip() for k,v in row.items()}
    for n in names:
        v = d.get(norm(n))
        if v:
            return v
    return ""

def parse_bool(val):
    s = (val or "").strip().lower()
    return s in ("1","true","t","yes","y","ja","waar","active","actief")

def parse_date(s):
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d","%d-%m-%Y","%d/%m/%Y","%Y/%m/%d","%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    m = re.match(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$", s)
    if m:
        d, mn, y = m.groups()
        return date(int(y), int(mn), int(d))
    return None

_CANON = {"VST_KAST","KAR_KLN","KAR_ELEC"}
_ALIASES = {
    # vestiaire
    "vestiaire": "VST_KAST",
    "vestiairekast": "VST_KAST",
    "vst_kast": "VST_KAST",
    "locker": "VST_KAST",
    # kar klein
    "kar_kln": "KAR_KLN",
    "karrengarage_klein": "KAR_KLN",
    "trolley_locker": "KAR_KLN",
    # kar elektrisch
    "kar_elec": "KAR_ELEC",
    "karrengarage_groot_elektrisch": "KAR_ELEC",
    "e_trolley_locker": "KAR_ELEC",
    "electrische_kar_garage": "KAR_ELEC",
}

def coerce_asset_type(raw):
    if not raw:
        return None
    s = (raw or "").strip()
    if s.upper() in _CANON:
        return s.upper()
    key = norm(s)
    return _ALIASES.get(key)

def has_field(model, name):
    try:
        model._meta.get_field(name); return True
    except Exception:
        return False

def split_name_guess(full):
    full = (full or "").strip()
    if not full:
        return []
    if "," in full:  # "Achternaam, Voornaam"
        ln, fn = [x.strip() for x in full.split(",", 1)]
        return [(fn, ln)]
    parts = full.split()
    if len(parts) < 2:
        return []
    fn1, ln1 = " ".join(parts[:-1]), parts[-1]
    ln2, fn2 = parts[0], " ".join(parts[1:])
    return [(fn1, ln1), (fn2, ln2)]

class Command(BaseCommand):
    help = "Importeer MemberAsset uit CSV."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument("--update", action="store_true", help="Bestaande assets bijwerken")
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, csv_path, update=False, dry_run=False, **opts):
        # CSV lezen
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as fh:
            sample = fh.read(4096); fh.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=";,")
                delim = dialect.delimiter
            except Exception:
                delim = ","
            reader = csv.DictReader(fh, delimiter=delim)
            rows = list(reader)
        self.stdout.write(f"CSV delimiter: {repr(delim)}")

        created = updated_n = skipped = missing_member = ambiguous_member = bad_type = 0

        have_ext   = has_field(Member, "external_id")
        have_email = has_field(Member, "email")

        ext_keys = (
            "member_external_id","external_id",
            "Fichenummer_Totaal","fichenummer_totaal","FICHENUMMER_TOTAAL",
            "Fichenummer Totaal","fichenummer totaal","fiche","fiche_nummer","fichenummer",
            "FicheNummer Totaal","Fiche Nummer Totaal",
        )

        for idx, row in enumerate(rows, start=2):
            # type
            at_raw = pick(row, "asset_type", "type", "asset")
            at = coerce_asset_type(at_raw)
            if not at:
                bad_type += 1
                self.stderr.write(f"Rij {idx}: onbekend asset_type {repr(at_raw)}, overslaan.")
                continue

            # member keys
            eid   = pick(row, *ext_keys)
            email = pick(row, "email", "e-mail")
            fn    = pick(row, "first_name", "voornaam", "given_name")
            ln    = pick(row, "last_name",  "achternaam", "familienaam")
            name_single = pick(row, "name","naam","full_name","volledige_naam")
            st    = pick(row, "street", "straat")
            pc    = pick(row, "postal_code", "postcode", "postalcode")

            qs = Member.objects.all()
            matched = None

            if have_ext and eid:
                qs = qs.filter(external_id=eid)
                c = qs.count()
                if c == 1:
                    matched = qs.first()
                elif c > 1:
                    ambiguous_member += 1
                    self.stderr.write(f"Rij {idx}: meerdere members voor external_id={eid}.")
                    continue

            if matched is None and have_email and email:
                qs = Member.objects.filter(email__iexact=email)
                c = qs.count()
                if c == 1:
                    matched = qs.first()
                elif c > 1:
                    ambiguous_member += 1
                    self.stderr.write(f"Rij {idx}: meerdere members voor email={email}.")
                    continue

            if matched is None:
                attempts = []
                if fn and ln:
                    attempts = [(fn, ln)]
                elif name_single:
                    attempts = split_name_guess(name_single)

                tried = False
                for a_fn, a_ln in attempts:
                    flt = Q(first_name__iexact=a_fn) & Q(last_name__iexact=a_ln)
                    if st and has_field(Member,"street"): flt &= Q(street__iexact=st)
                    if pc and has_field(Member,"postal_code"): flt &= Q(postal_code__iexact=pc)
                    qs2 = Member.objects.filter(flt)
                    tried = True
                    if qs2.count() == 1:
                        matched = qs2.first()
                        break
                    elif qs2.count() > 1:
                        ambiguous_member += 1
                        self.stderr.write(f"Rij {idx}: meerdere members voor naam={a_fn} {a_ln}.")
                        matched = None
                        break

                if matched is None and not tried:
                    self.stderr.write(f"Rij {idx}: geen member match (external_id={eid}, email={email}, name={name_single}).")
                    missing_member += 1
                    continue

            if matched is None:
                missing_member += 1
                continue

            member = matched

            # identifier
            ident = pick(row, "identifier","number","no","nr","locker_number","kast","kastnr","kast_nr","nummer")

            active = parse_bool(pick(row, "active"))
            rel    = parse_date(pick(row, "released_on", "vrijgegeven_op", "released"))

            qsa = MemberAsset.objects.filter(member=member, asset_type=at)
            if ident:
                qsa = qsa.filter(identifier=ident)

            if qsa.exists():
                asset = qsa.first()
                changed = False
                if asset.active != active:
                    asset.active = active; changed = True
                if rel is not None and asset.released_on != rel:
                    asset.released_on = rel; changed = True
                if changed:
                    if dry_run:
                        updated_n += 1
                    else:
                        asset.save(update_fields=["active","released_on"])
                        updated_n += 1
                else:
                    skipped += 1
            else:
                if dry_run:
                    created += 1
                else:
                    MemberAsset.objects.create(
                        member=member,
                        asset_type=at,
                        identifier=ident or None,
                        active=active,
                        released_on=rel
                    )
                    created += 1

        self.stdout.write(
            f"Assets import: created={created}, updated={updated_n}, skipped={skipped}, "
            f"missing_member={missing_member}, ambiguous_member={ambiguous_member}, bad_type={bad_type}"
        )
