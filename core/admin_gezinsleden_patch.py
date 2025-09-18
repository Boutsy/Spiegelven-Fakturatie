from django.contrib import admin
from django.apps import apps
from django.utils.html import format_html, format_html_join
from datetime import date
import re

P_VEST = re.compile(r'^VST[_-]?KAST\s*(.+)$', re.I)
P_KARK = re.compile(r'^KAR[_-]?KLN\s*(.+)$', re.I)
P_ELEC = re.compile(r'^KAR[_-]?ELEC\s*(.+)$', re.I)
IDENT_CANDIDATES = ("identifier", "ident", "code", "label", "name")

def _order_fields(M):
    names = {f.name for f in M._meta.get_fields() if hasattr(f, "attname")}
    if {"last_name","first_name"}.issubset(names): return ["last_name","first_name"]
    if {"surname","given_name"}.issubset(names):   return ["surname","given_name"]
    if {"family_name","given_names"}.issubset(names): return ["family_name","given_names"]
    if "name" in names: return ["name"]
    return ["id"]

def _display_name(m):
    last = getattr(m, "last_name", None) or getattr(m, "surname", None) or getattr(m, "family_name", None)
    first = getattr(m, "first_name", None) or getattr(m, "given_name", None) or getattr(m, "given_names", None)
    if last and first: return f"{last} {first}"
    if getattr(m, "name", None): return m.name
    return str(m)

def _age_years(m):
    dob = (
        getattr(m, "birth_date", None)
        or getattr(m, "date_of_birth", None)
        or getattr(m, "dob", None)
        or getattr(m, "geboortedatum", None)
    )
    if not dob:
        return None
    try:
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return None

def _collect_slots(m):
    vest, kark, elec = [], [], []
    try:
        for rel in m._meta.related_objects:
            accessor = getattr(m, rel.get_accessor_name(), None)
            if not hasattr(accessor, "all"):
                continue
            for obj in accessor.all()[:300]:
                val = None
                for f in IDENT_CANDIDATES:
                    v = getattr(obj, f, None)
                    if v:
                        val = str(v).strip()
                        break
                if not val:
                    continue
                mv = P_VEST.match(val)
                mk = P_KARK.match(val)
                me = P_ELEC.match(val)
                if mv:      vest.append(mv.group(1).strip())
                elif mk:    kark.append(mk.group(1).strip())
                elif me:    elec.append(me.group(1).strip())
    except Exception:
        pass

    def uniq(xs):
        seen, out = set(), []
        for x in xs:
            if x and x not in seen:
                seen.add(x); out.append(x)
        return out

    return uniq(vest), uniq(kark), uniq(elec)

def apply():
    M = apps.get_model("core", "Member")
    ma = admin.site._registry.get(M)
    if not ma:
        return

    order = _order_fields(M)

    def gezinsleden(self, obj):
        if obj is None:
            return ""
        qs = M.objects.filter(factureren_via=obj).order_by(*order)
        if not qs.exists():
            return "—"

        head = format_html(
            '<table style="border-collapse:collapse;width:100%"><thead><tr>'
            '<th style="text-align:left;border-bottom:1px solid #ddd;padding:4px 6px">Naam</th>'
            '<th style="text-align:left;border-bottom:1px solid #ddd;padding:4px 6px">Leeftijd</th>'
            '<th style="text-align:left;border-bottom:1px solid #ddd;padding:4px 6px">Vestiaire</th>'
            '<th style="text-align:left;border-bottom:1px solid #ddd;padding:4px 6px">Kar Kast</th>'
            '<th style="text-align:left;border-bottom:1px solid #ddd;padding:4px 6px">Elec. Kar</th>'
            '<th style="text-align:left;border-bottom:1px solid #ddd;padding:4px 6px">ID</th>'
            "</tr></thead><tbody>"
        )

        rows = []
        for m in qs:
            vest, kark, elec = _collect_slots(m)
            age = _age_years(m)
            rows.append((
                _display_name(m),
                f"{age} j" if age is not None else "",
                ", ".join(vest) if vest else "",
                ", ".join(kark) if kark else "",
                ", ".join(elec) if elec else "",
                f"{m.pk}",
            ))

        body = format_html_join(
            "",
            "<tr>"
            "<td style=\"padding:4px 6px;border-bottom:1px solid #f0f0f0\">{}</td>"
            "<td style=\"padding:4px 6px;border-bottom:1px solid #f0f0f0\">{}</td>"
            "<td style=\"padding:4px 6px;border-bottom:1px solid #f0f0f0\">{}</td>"
            "<td style=\"padding:4px 6px;border-bottom:1px solid #f0f0f0\">{}</td>"
            "<td style=\"padding:4px 6px;border-bottom:1px solid #f0f0f0\">{}</td>"
            "<td style=\"padding:4px 6px;border-bottom:1px solid #f0f0f0\">{}</td>"
            "</tr>",
            rows
        )
        tail = format_html("</tbody></table>")
        return head + body + tail

    setattr(ma.__class__, "gezinsleden", gezinsleden)

    orig_ro = getattr(ma.__class__, "get_readonly_fields", None)
    def get_readonly_fields(self, request, obj=None):
        base = list(orig_ro(self, request, obj)) if orig_ro else []
        if "gezinsleden" not in base:
            base.append("gezinsleden")
        return tuple(base)
    setattr(ma.__class__, "get_readonly_fields", get_readonly_fields)

    orig_fs = ma.__class__.get_fieldsets
    def get_fieldsets(self, request, obj=None):
        fs = list(orig_fs(self, request, obj))
        block = ("Gezinsleden", {"fields": ("gezinsleden",)})
        try:
            i = next(i for i,(t,_) in enumerate(fs) if str(t or "").strip().lower() in {"facturatie","facturering","billing"})
            fs.insert(i+1, block)
        except StopIteration:
            fs.append(block)
        return tuple(fs)
    setattr(ma.__class__, "get_fieldsets", get_fieldsets)