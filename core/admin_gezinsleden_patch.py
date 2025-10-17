from django.utils.html import format_html, format_html_join
from django.contrib import admin
from django.apps import apps
from datetime import date
import re

def _order_fields(M):
    f = {f.name for f in M._meta.get_fields() if hasattr(f, "attname")}
    if {"last_name","first_name"}.issubset(f): return ["last_name","first_name"]
    if {"surname","given_name"}.issubset(f):   return ["surname","given_name"]
    if {"family_name","given_names"}.issubset(f): return ["family_name","given_names"]
    if "name" in f: return ["name"]
    return ["id"]

def _display_name(m):
    last = getattr(m, "last_name", None) or getattr(m, "surname", None) or getattr(m, "family_name", None)
    first = getattr(m, "first_name", None) or getattr(m, "given_name", None) or getattr(m, "given_names", None)
    if last and first: return f"{last} {first}"
    if getattr(m, "name", None): return getattr(m, "name")
    return str(m)

def _age(m):
    d = getattr(m, "birth_date", None) or getattr(m, "date_of_birth", None) or getattr(m, "dob", None)
    if not d: return ""
    t = date.today()
    try:
        return str(t.year - d.year - ((t.month, t.day) < (d.month, d.day)))
    except Exception:
        return ""

def _role_display(m):
    try:
        return m.get_household_role_display()
    except Exception:
        val = getattr(m, "household_role", "") or ""
        return str(val)

_ID_PATTERNS = [
    ("Vestiaire", r"^(?:VST)[_-]?KAST(\w+)$"),
    ("Kar Kast",  r"^(?:KAR)[_-]?(?:KAST|KLN)(\w+)$"),
    ("Elec. Kar", r"^(?:KAR[_-]?ELEC|ELEC[_-]?KAR)(\w+)$"),
]
_IDENTIFIER_CANDIDATES = ("identifier","code","name","label","slot","number","nummer","ref","reference")

def _pick_identifier_from(obj):
    for attr in _IDENTIFIER_CANDIDATES:
        v = getattr(obj, attr, None)
        if v:
            s = str(v).strip()
            if s: return s
    try:
        s = str(obj).strip()
        if s: return s
    except Exception:
        pass
    return ""

def _iter_member_assets(member):
    try:
        MemberAsset = apps.get_model("core","MemberAsset")
    except Exception:
        MemberAsset = None

    if MemberAsset:
        fk_names = []
        for f in MemberAsset._meta.get_fields():
            if getattr(f, "is_relation", False) and getattr(f, "many_to_one", False):
                rel = getattr(f, "remote_field", None)
                if rel and getattr(rel, "model", None) == member.__class__:
                    fk_names.append(f.name)
        qs = None
        for fk in fk_names or ["member","lid","owner","user"]:
            try:
                qs = MemberAsset.objects.filter(**{fk: member})
                break
            except Exception:
                pass
        if qs is not None:
            for a in qs: yield a

    for f in member._meta.get_fields():
        if getattr(f, "auto_created", False) and getattr(f, "one_to_many", False) and getattr(f, "related_model", None):
            relm = f.related_model
            nm = relm.__name__.lower()
            if any(k in nm for k in ("asset","locker","kast","kar","slot","vesti","elec")):
                try:
                    for a in getattr(member, f.get_accessor_name()).all():
                        yield a
                except Exception:
                    pass

def _asset_map(member):
    out = {"Vestiaire": "", "Kar Kast": "", "Elec. Kar": ""}
    for rel in _iter_member_assets(member):
        if hasattr(rel, "active") and not getattr(rel, "active"):
            continue
        idtxt = _pick_identifier_from(rel)
        asset_type = getattr(rel, "asset_type", "") or ""
        normalized = asset_type.lower()

        target_col = None
        if normalized in {"locker", "kast", "locker_kast"}:
            target_col = "Vestiaire"
        elif normalized in {"trolley_locker", "kar", "kar_kast", "kar_kln"}:
            target_col = "Kar Kast"
        elif normalized in {"e_trolley_locker", "elec_kar", "kar_elec", "kar_elektrisch"}:
            target_col = "Elec. Kar"

        # First try explicit mapping based on asset_type
        if target_col and not out[target_col]:
            if idtxt:
                out[target_col] = idtxt
            continue

        if not idtxt:
            continue

        # Fallback: detect based on identifier pattern (oude stijl)
        for col, pat in _ID_PATTERNS:
            m = re.match(pat, idtxt, flags=re.IGNORECASE)
            if m and not out[col]:
                out[col] = m.group(1) if m.lastindex else idtxt
                break
    return out

def apply():
    M = apps.get_model("core","Member")
    ma = admin.site._registry.get(M)
    if not ma: return
    C = ma.__class__
    if getattr(C, "_gzl_table_patched", False): return

    order = _order_fields(M)

    def gezinsleden(self, obj):
        if not obj: return ""
        qs = M.objects.filter(factureren_via_id=getattr(obj,"pk",None)).order_by(*order)
        if not qs.exists(): return "—"

        head = format_html(
            "<table style=\"border-collapse:collapse; width:100%\">"
            "<thead><tr>"
            "<th style=\"text-align:left; padding:6px; border-bottom:1px solid #f0f0f0\">Naam</th>"
            "<th style=\"text-align:left; padding:6px; border-bottom:1px solid #f0f0f0\">Leeftijd</th>"
            "<th style=\"text-align:left; padding:6px; border-bottom:1px solid #f0f0f0\">Rol</th>"
            "<th style=\"text-align:left; padding:6px; border-bottom:1px solid #f0f0f0\">Vestiaire</th>"
            "<th style=\"text-align:left; padding:6px; border-bottom:1px solid #f0f0f0\">Kar Kast</th>"
            "<th style=\"text-align:left; padding:6px; border-bottom:1px solid #f0f0f0\">Elec. Kar</th>"
            "</tr></thead><tbody>"
        )

        rows = []
        for m in qs:
            amap = _asset_map(m)
            rows.append((
                _display_name(m),
                _age(m) or "—",
                _role_display(m) or "—",
                amap.get("Vestiaire","") or "—",
                amap.get("Kar Kast","") or "—",
                amap.get("Elec. Kar","") or "—",
            ))

        body = format_html_join(
            "",
            "<tr>"
            "<td style=\"padding:6px; border-bottom:1px solid #f0f0f0\">{}</td>"
            "<td style=\"padding:6px; border-bottom:1px solid #f0f0f0\">{}</td>"
            "<td style=\"padding:6px; border-bottom:1px solid #f0f0f0\">{}</td>"
            "<td style=\"padding:6px; border-bottom:1px solid #f0f0f0\">{}</td>"
            "<td style=\"padding:6px; border-bottom:1px solid #f0f0f0\">{}</td>"
            "<td style=\"padding:6px; border-bottom:1px solid #f0f0f0\">{}</td>"
            "</tr>",
            rows
        )
        tail = format_html("</tbody></table>")
        return head + body + tail

    setattr(C, "gezinsleden", gezinsleden)

    orig_ro = getattr(C, "get_readonly_fields", None)
    def get_readonly_fields(self, request, obj=None):
        base = list(orig_ro(self, request, obj)) if orig_ro else []
        if "gezinsleden" not in base: base.append("gezinsleden")
        return tuple(base)
    setattr(C, "get_readonly_fields", get_readonly_fields)

    orig_fs = C.get_fieldsets
    def get_fieldsets(self, request, obj=None):
        fs = []
        for title, opts in orig_fs(self, request, obj):
            tnorm = str(title or "").strip().lower()
            fields = tuple((opts or {}).get("fields", ()))
            if tnorm == "gezinsleden" or any(str(f).lower() == "gezinsleden" for f in fields):
                continue
            fs.append((title, opts))
        block = ("Gezinsleden", {"fields": ("gezinsleden",)})
        try:
            i = next(i for i,(t,_) in enumerate(fs) if str(t or "").strip().lower() in {"facturatie","facturering","billing"})
            fs.insert(i+1, block)
        except StopIteration:
            fs.append(block)
        return tuple(fs)
    setattr(C, "get_fieldsets", get_fieldsets)

    C._gzl_table_patched = True
