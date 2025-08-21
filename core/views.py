import csv
import os
import uuid
from datetime import datetime
from typing import Dict, List, Tuple

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .models import Member, Household, ImportMapping

# -------- Helper: veilige temp-map ----------
TMP_DIR = os.path.join(settings.BASE_DIR, "tmp")
os.makedirs(TMP_DIR, exist_ok=True)

# -------- Welke velden van Member ondersteunen we? ----------
# key = modelveld; value = label dat je in de UI ziet
MEMBER_FIELDS: Dict[str, str] = {
    "first_name": "Voornaam",
    "last_name": "Naam",
    "email": "E-mail",
    "phone": "Telefoon",
    "street": "Straat",
    "postal_code": "Postcode",
    "city": "Gemeente",
    "country": "Land",
    "date_of_birth": "Geboortedatum",
    "membership_mode": "Lidmaatschapsmodus (investment/flex)",
    "federation_via_club": "Federatie via club (ja/nee)",
    "active": "Actief (ja/nee)",
    # virtuele velden voor koppelingen:
    "household_name": "Gezinsnaam (maakt/gebruikt Household)",
    "household_role": "Gezinsrol (head/partner/child/other)",
}

# -------- Hulpfuncties ----------
def _try_decode(raw: bytes) -> str:
    """Probeer UTF-8 (met BOM) en val terug op latin-1."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="ignore")

def _read_csv(filepath: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """Lees CSV en geef (headers, rows) terug."""
    with open(filepath, "rb") as f:
        text = _try_decode(f.read())
    sniffer = csv.Sniffer()
    dialect = sniffer.sniff(text.splitlines()[0] if text.splitlines() else ",")
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    headers = reader.fieldnames or []
    rows = [row for row in reader]
    return headers, rows

def _guess_mapping(headers: List[str]) -> Dict[str, str]:
    """Eenvoudige gok: match op lowercase zonder spaties/accents."""
    import re
    def norm(s: str) -> str:
        s = s.lower().strip()
        s = s.replace("é", "e").replace("è", "e").replace("ê", "e").replace("à", "a").replace("ä", "a").replace("ö","o")
        return re.sub(r"[^a-z0-9]+", "", s)

    norm_headers = {norm(h): h for h in headers}
    candidates = {
        "first_name": ["voornaam", "firstname", "first"],
        "last_name": ["naam", "achternaam", "lastname", "last"],
        "email": ["email", "e-mailadres", "mail"],
        "phone": ["telefoon", "gsm", "phone", "mobile"],
        "street": ["straat", "address", "adres", "adreslijn1", "line1"],
        "postal_code": ["postcode", "zip", "postnr", "postalcode"],
        "city": ["gemeente", "stad", "city", "plaats"],
        "country": ["land", "country"],
        "date_of_birth": ["geboortedatum", "dob", "birthdate", "geboren"],
        "membership_mode": ["membershipmode", "mode", "lidmaatschap", "flexinvestment"],
        "federation_via_club": ["federatieviaclub", "gvvia", "gv", "federation"],
        "active": ["actief", "active"],
        "household_name": ["gezin", "gezinshoofd", "household", "familie"],
        "household_role": ["gezinsrol", "rol", "role"],
    }
    mapping = {}
    for field, opts in candidates.items():
        for opt in opts:
            if norm(opt) in norm_headers:
                mapping[field] = norm_headers[norm(opt)]
                break
    return mapping

def _parse_bool(v: str) -> bool | None:
    if v is None: return None
    v = str(v).strip().lower()
    if v in {"1", "ja", "true", "y", "yes"}: return True
    if v in {"0", "nee", "false", "n", "no"}: return False
    return None

def _parse_date(v: str):
    if not v: return None
    v = v.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None

def _norm_membership_mode(v: str) -> str | None:
    if not v: return None
    v = v.strip().lower()
    if v.startswith("inv"): return "investment"
    if v.startswith("flex"): return "flex"
    return None

def _household_role(v: str) -> str | None:
    if not v: return None
    v = v.strip().lower()
    if v.startswith("hoof"): return "head"
    if v.startswith("part") or v.startswith("partner"): return "partner"
    if v.startswith("kind") or v.startswith("child"): return "child"
    return "other"

# -------- Views ----------
@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    return render(request, "dashboard.html", {})

@login_required
def import_upload(request: HttpRequest) -> HttpResponse:
    # reset sessie
    for k in ("csv_path", "csv_headers", "import_mapping", "unique_by"):
        request.session.pop(k, None)

    if request.method == "POST":
        f = request.FILES.get("csvfile")
        if not f:
            messages.error(request, "Kies een CSV-bestand.")
            return redirect("import_upload")
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in (".csv", ".txt"):
            messages.error(request, "Alleen .csv of .txt is toegestaan.")
            return redirect("import_upload")
        dest = os.path.join(TMP_DIR, f"import_{uuid.uuid4().hex}.csv")
        with open(dest, "wb") as out:
            for chunk in f.chunks():
                out.write(chunk)
        headers, _ = _read_csv(dest)
        request.session["csv_path"] = dest
        request.session["csv_headers"] = headers
        return redirect("import_map")

    saved_maps = ImportMapping.objects.filter(model="Member").order_by("name")
    return render(request, "import/upload.html", {"saved_maps": saved_maps})

@login_required
def import_map(request: HttpRequest) -> HttpResponse:
    csv_path = request.session.get("csv_path")
    headers = request.session.get("csv_headers") or []
    if not csv_path or not os.path.exists(csv_path):
        messages.error(request, "Geen geüpload CSV-bestand gevonden. Start opnieuw.")
        return redirect("import_upload")

    initial_map = _guess_mapping(headers)

    # Als user een bestaande mapping kiest/opslaat
    if request.method == "POST":
        # Laden van bestaande mapping
        load_id = request.POST.get("load_mapping_id")
        if load_id:
            try:
                im = ImportMapping.objects.get(pk=load_id)
                mapping: Dict[str, str] = im.mapping or {}
            except ImportMapping.DoesNotExist:
                mapping = {}
        else:
            # Lezen van form selects
            mapping = {}
            for field in MEMBER_FIELDS.keys():
                col = request.POST.get(f"map_{field}") or ""
                if col:
                    mapping[field] = col

            # Optioneel opslaan
            save_name = (request.POST.get("save_mapping_name") or "").strip()
            if save_name:
                obj, _ = ImportMapping.objects.get_or_create(
                    name=save_name,
                    defaults={"model": "Member", "mapping": mapping},
                )
                if _ is False:
                    obj.model = "Member"
                    obj.mapping = mapping
                    obj.save()

        request.session["import_mapping"] = mapping
        return redirect("import_confirm")

    saved_maps = ImportMapping.objects.filter(model="Member").order_by("name")
    return render(
        request,
        "import/map.html",
        {
            "headers": headers,
            "member_fields": MEMBER_FIELDS,
            "initial_map": initial_map,
            "saved_maps": saved_maps,
        },
    )

@login_required
def import_confirm(request: HttpRequest) -> HttpResponse:
    csv_path = request.session.get("csv_path")
    mapping: Dict[str, str] = request.session.get("import_mapping") or {}
    if not csv_path or not os.path.exists(csv_path) or not mapping:
        messages.error(request, "CSV of mapping ontbreekt. Start opnieuw.")
        return redirect("import_upload")

    headers, rows = _read_csv(csv_path)
    preview = []
    for row in rows[:20]:  # eerste 20
        mapped = {f: row.get(col) for f, col in mapping.items()}
        preview.append(mapped)

    if request.method == "POST":
        unique_by = request.POST.get("unique_by") or "email"
        request.session["unique_by"] = unique_by
        return redirect("import_run")

    return render(
        request,
        "import/confirm.html",
        {"mapping": mapping, "preview": preview, "member_fields": MEMBER_FIELDS},
    )

@login_required
def import_run(request: HttpRequest) -> HttpResponse:
    csv_path = request.session.get("csv_path")
    mapping: Dict[str, str] = request.session.get("import_mapping") or {}
    unique_by = request.session.get("unique_by") or "email"

    if not csv_path or not os.path.exists(csv_path) or not mapping:
        messages.error(request, "CSV of mapping ontbreekt. Start opnieuw.")
        return redirect("import_upload")

    headers, rows = _read_csv(csv_path)

    created = 0
    updated = 0
    skipped = 0
    errors = []

    @transaction.atomic
    def _import():
        nonlocal created, updated, skipped
        for idx, row in enumerate(rows, start=2):  # +1 voor header, dus data vanaf 2
            try:
                # Bepaal zoeksleutel
                member_obj = None
                if unique_by == "email":
                    email = (row.get(mapping.get("email", ""), "") or "").strip().lower()
                    if email:
                        member_obj = Member.objects.filter(email__iexact=email).first()
                else:
                    fn = (row.get(mapping.get("first_name", ""), "") or "").strip()
                    ln = (row.get(mapping.get("last_name", ""), "") or "").strip()
                    dob_raw = row.get(mapping.get("date_of_birth", ""), "")
                    dob = _parse_date(dob_raw) if dob_raw else None
                    qs = Member.objects.filter(first_name__iexact=fn, last_name__iexact=ln)
                    if dob:
                        qs = qs.filter(date_of_birth=dob)
                    member_obj = qs.first()

                # Nieuw of updaten
                is_new = False
                if member_obj is None:
                    member_obj = Member()
                    is_new = True

                # Velden mappen
                for field in MEMBER_FIELDS.keys():
                    if field in ("household_name", "household_role"):
                        continue  # later
                    col = mapping.get(field)
                    if not col:
                        continue
                    val = row.get(col)
                    if field == "date_of_birth":
                        val = _parse_date(val)
                    elif field == "federation_via_club" or field == "active":
                        b = _parse_bool(val)
                        if b is not None:
                            val = b
                        else:
                            val = False if val in (None, "",) else member_obj.__dict__.get(field, False)
                    elif field == "membership_mode":
                        mm = _norm_membership_mode(val)
                        if mm:
                            val = mm
                        else:
                            continue
                    if val is not None:
                        setattr(member_obj, field, val)

                # Household
                hh_name_col = mapping.get("household_name")
                if hh_name_col:
                    hh_name = (row.get(hh_name_col) or "").strip()
                    if hh_name:
                        hh, _ = Household.objects.get_or_create(name=hh_name)
                        member_obj.household = hh
                hh_role_col = mapping.get("household_role")
                if hh_role_col:
                    member_obj.household_role = _household_role(row.get(hh_role_col) or "")

                member_obj.save()
                created += 1 if is_new else 1 if member_obj.pk else 0
                # “updated” tellen we als hij bestond en door ons gewijzigd is — voor nu simpel:
                if not is_new:
                    updated += 1

            except Exception as e:
                skipped += 1
                errors.append(f"Rij {idx}: {e}")

    _import()

    # Opruimen temp
    try:
        os.remove(csv_path)
    except Exception:
        pass
    for k in ("csv_path", "csv_headers", "import_mapping", "unique_by"):
        request.session.pop(k, None)

    return render(
        request,
        "import/run.html",
        {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors[:200],
        },
    )
