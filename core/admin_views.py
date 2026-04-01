from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from django.apps import apps
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import admin
from django.core.mail import EmailMessage
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import get_template
from django.template.response import TemplateResponse
from django.utils import timezone
from django.db.models import Q
from django.urls import reverse
from types import SimpleNamespace
import xml.etree.ElementTree as ET


Invoice = apps.get_model("core", "Invoice")
InvoiceLine = apps.get_model("core", "InvoiceLine")
OrganizationProfile = apps.get_model("core", "OrganizationProfile")
Product = apps.get_model("core", "Product")
Member = apps.get_model("core", "Member")
try:
    MemberAsset = apps.get_model("core", "MemberAsset")
except LookupError:
    MemberAsset = None
try:
    YearPricing = apps.get_model("core", "YearPricing")
except LookupError:
    YearPricing = None

def _q(val):
    return Decimal(str(val or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _split_amount(d):
    s = f"{_q(d):.2f}"
    i, dec = s.split(".")
    return {"int": i.replace("-", "−"), "dec": dec}

def _lines_for(invoice):
    qs = InvoiceLine.objects.filter(invoice=invoice).order_by("id")
    out = []
    for l in qs:
        qty = _q(getattr(l, "quantity", 1))
        unit = _q(getattr(l, "unit_price_excl", 0))
        rate = Decimal(str(getattr(l, "vat_rate", 0) or 0))
        ex = _q(qty * unit)
        vat = _q(ex * rate / Decimal("100"))
        inc = _q(ex + vat)
        out.append({
            "description": getattr(l, "description", "") or "",
            "quantity": qty,
            "unit_price_excl": unit,
            "vat_rate": rate,
            "line_excl": ex,
            "vat_amount": vat,
            "line_incl": inc,
        })
    return out

def _vat_summary(lines):
    bucket = {}
    for l in lines:
        r = int(l["vat_rate"])
        b = bucket.setdefault(r, {"rate": f"{r}%", "excl": Decimal("0.00"), "vat": Decimal("0.00"), "incl": Decimal("0.00")})
        b["excl"] = _q(b["excl"] + l["line_excl"])
        b["vat"] = _q(b["vat"] + l["vat_amount"])
        b["incl"] = _q(b["incl"] + l["line_incl"])
    return [bucket[k] for k in sorted(bucket)]

def _org_and_payment():
    # Kies het meest complete OrganizationProfile
    qs = OrganizationProfile.objects.all()
    op = None
    if qs.exists():
        def _score(o):
            fields = [
                "name","address_line1","address_line2","postal_code","city","country",
                "iban","bic","email","website","vat_number",
                "phone","fax",   # <- toegevoegd
            ]
            return sum(1 for f in fields if getattr(o, f, None))
        op = sorted(qs, key=_score, reverse=True)[0]

    # Geef ALLE velden door zodat templates zoals _footer_org.html ze kunnen gebruiken
    org = {
        "id": getattr(op, "id", None) if op else None, 
        "name": getattr(op, "name", "") if op else "",
        "address_line1": getattr(op, "address_line1", "") if op else "",
        "address_line2": getattr(op, "address_line2", "") if op else "",
        "postal_code": getattr(op, "postal_code", "") if op else "",
        "city": getattr(op, "city", "") if op else "",
        "country": getattr(op, "country", "") if op else "",
        "vat_number": getattr(op, "vat_number", "") if op else "",
        "email": getattr(op, "email", "") if op else "",
        "website": getattr(op, "website", "") if op else "",
        "iban": getattr(op, "iban", "") if op else "",
        "bic": getattr(op, "bic", "") if op else "",
        "phone": getattr(op, "phone", "") if op else "",
        "fax": getattr(op, "fax", "") if op else "",
    }
    payment = {
        "iban": org["iban"],
        "bic": org["bic"],
        "ogm": "",
    }
    return org, payment

# ---------- UBL export ----------

def _ubl_text(invoice, org, lines):
    """
    Bouw een minimale UBL 2.1 factuur op basis van het dagfactuur-model.
    """
    NS = {
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    }
    for pfx, uri in NS.items():
        if pfx:
            ET.register_namespace(pfx, uri)
        else:
            ET.register_namespace("", uri)

    def _el(tag, text=None, ns="cbc"):
        q = f"{{{NS[ns]}}}{tag}"
        elem = ET.Element(q)
        if text not in (None, ""):
            elem.text = str(text)
        return elem

    inv = ET.Element(f"{{{NS['']}}}Invoice")
    inv.append(_el("CustomizationID", "urn:cen.eu:en16931:2017"))
    inv.append(_el("ProfileID", "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"))
    inv.append(_el("ID", invoice.number or f"concept-{invoice.pk or 'temp'}"))
    inv.append(_el("IssueDate", invoice.issue_date.isoformat()))
    inv.append(_el("InvoiceTypeCode", "380"))
    inv.append(_el("DocumentCurrencyCode", "EUR"))

    # Leverancier (club)
    acct_supplier = ET.SubElement(inv, f"{{{NS['cac']}}}AccountingSupplierParty")
    party = ET.SubElement(acct_supplier, f"{{{NS['cac']}}}Party")
    party.append(_el("EndpointID", org.get("vat_number") or "BE0000000000"))
    party_name = ET.SubElement(party, f"{{{NS['cac']}}}PartyName")
    party_name.append(_el("Name", org.get("name", "")))
    postal = ET.SubElement(party, f"{{{NS['cac']}}}PostalAddress")
    postal.append(_el("StreetName", org.get("address_line1", "")))
    postal.append(_el("AdditionalStreetName", org.get("address_line2", "")))
    postal.append(_el("CityName", org.get("city", "")))
    postal.append(_el("PostalZone", org.get("postal_code", "")))
    postal.append(_el("CountrySubentity", ""))
    country = ET.SubElement(postal, f"{{{NS['cac']}}}Country")
    country.append(_el("IdentificationCode", (org.get("country") or "BE")[:2].upper()))
    tax_scheme = ET.SubElement(party, f"{{{NS['cac']}}}PartyTaxScheme")
    tax_scheme.append(_el("CompanyID", org.get("vat_number", "")))
    tax_scheme.append(ET.Element(f"{{{NS['cac']}}}TaxScheme"))
    contact = ET.SubElement(party, f"{{{NS['cac']}}}Contact")
    contact.append(_el("Telephone", org.get("phone", "")))
    contact.append(_el("ElectronicMail", org.get("email", "")))

    # Klant (account of member)
    acct_customer = ET.SubElement(inv, f"{{{NS['cac']}}}AccountingCustomerParty")
    cust_party = ET.SubElement(acct_customer, f"{{{NS['cac']}}}Party")
    cust_name = ET.SubElement(cust_party, f"{{{NS['cac']}}}PartyName")
    cust_name.append(_el("Name", getattr(invoice.account, "name", "") or str(getattr(invoice, "member", "") or "Klant")))
    cust_addr = ET.SubElement(cust_party, f"{{{NS['cac']}}}PostalAddress")
    cust_addr.append(_el("StreetName", getattr(invoice.account, "street", "") or getattr(invoice.member, "street", "")))
    cust_addr.append(_el("CityName", getattr(invoice.account, "city", "") or getattr(invoice.member, "city", "")))
    cust_addr.append(_el("PostalZone", getattr(invoice.account, "postal_code", "") or getattr(invoice.member, "postal_code", "")))
    cust_country = ET.SubElement(cust_addr, f"{{{NS['cac']}}}Country")
    cust_country.append(_el("IdentificationCode", (getattr(invoice.account, "country", "") or getattr(invoice.member, "country", "") or "BE")[:2].upper()))
    cust_tax = ET.SubElement(cust_party, f"{{{NS['cac']}}}PartyTaxScheme")
    cust_tax.append(_el("CompanyID", getattr(invoice.account, "vat_number", "") or ""))
    cust_tax.append(ET.Element(f"{{{NS['cac']}}}TaxScheme"))
    cust_contact = ET.SubElement(cust_party, f"{{{NS['cac']}}}Contact")
    cust_contact.append(_el("ElectronicMail", getattr(invoice.account, "email", "") or getattr(invoice.member, "email", "")))

    # Lijnen
    total_excl = Decimal("0.00")
    total_vat = Decimal("0.00")
    for idx, l in enumerate(lines, start=1):
        qty = _q(getattr(l, "quantity", 1))
        unit = _q(getattr(l, "unit_price_excl", 0))
        vat_rate = Decimal(str(getattr(l, "vat_rate", 0) or 0))
        line_excl = _q(qty * unit)
        vat_amount = _q(line_excl * vat_rate / Decimal("100"))
        line_incl = _q(line_excl + vat_amount)
        total_excl += line_excl
        total_vat += vat_amount

        inv_line = ET.SubElement(inv, f"{{{NS['cac']}}}InvoiceLine")
        inv_line.append(_el("ID", idx))
        inv_line.append(_el("InvoicedQuantity", f"{qty}", ns="cbc"))
        inv_line.append(_el("LineExtensionAmount", f"{line_excl}", ns="cbc"))
        inv_line.append(_el("Note", getattr(l, "description", "")))
        pricing = ET.SubElement(inv_line, f"{{{NS['cac']}}}PricingReference")
        alt_price = ET.SubElement(pricing, f"{{{NS['cac']}}}AlternativeConditionPrice")
        alt_price.append(_el("PriceAmount", f"{unit}", ns="cbc"))
        alt_price.append(_el("PriceTypeCode", "EXW"))
        tax_total = ET.SubElement(inv_line, f"{{{NS['cac']}}}TaxTotal")
        tax_total.append(_el("TaxAmount", f"{vat_amount}", ns="cbc"))
        tax_sub = ET.SubElement(tax_total, f"{{{NS['cac']}}}TaxSubtotal")
        tax_sub.append(_el("TaxableAmount", f"{line_excl}", ns="cbc"))
        tax_sub.append(_el("TaxAmount", f"{vat_amount}", ns="cbc"))
        category = ET.SubElement(tax_sub, f"{{{NS['cac']}}}TaxCategory")
        category.append(_el("ID", "S"))
        category.append(_el("Percent", f"{vat_rate}", ns="cbc"))
        scheme = ET.SubElement(category, f"{{{NS['cac']}}}TaxScheme")
        scheme.append(_el("ID", "VAT"))
        item = ET.SubElement(inv_line, f"{{{NS['cac']}}}Item")
        item.append(_el("Name", getattr(l, "description", "")))
        price = ET.SubElement(inv_line, f"{{{NS['cac']}}}Price")
        price.append(_el("PriceAmount", f"{unit}", ns="cbc"))

    # Totaal
    tax_total = ET.SubElement(inv, f"{{{NS['cac']}}}TaxTotal")
    tax_total.append(_el("TaxAmount", f"{total_vat}", ns="cbc"))
    legal_monetary = ET.SubElement(inv, f"{{{NS['cac']}}}LegalMonetaryTotal")
    legal_monetary.append(_el("LineExtensionAmount", f"{total_excl}", ns="cbc"))
    legal_monetary.append(_el("TaxExclusiveAmount", f"{total_excl}", ns="cbc"))
    legal_monetary.append(_el("TaxInclusiveAmount", f"{_q(total_excl + total_vat)}", ns="cbc"))
    legal_monetary.append(_el("PayableAmount", f"{_q(total_excl + total_vat)}", ns="cbc"))

    return ET.tostring(inv, encoding="utf-8", xml_declaration=True)

def _ctx_for(invoice):
    lines = _lines_for(invoice)
    vat_summary = _vat_summary(lines) if lines else []
    total_excl = _q(sum((l["line_excl"] for l in lines), Decimal("0.00")))
    total_vat = _q(sum((l["vat_amount"] for l in lines), Decimal("0.00")))
    total_incl = _q(total_excl + total_vat)
    org, payment = _org_and_payment()
    ogm = getattr(invoice, "payment_reference_display", None)
    if callable(ogm):
        payment["ogm"] = invoice.payment_reference_display()
    return {
        "invoice": invoice,
        "lines": lines,
        "vat_summary": vat_summary,
        "totals_parts": {
            "excl": _split_amount(total_excl),
            "vat": _split_amount(total_vat),
            "incl": _split_amount(total_incl),
        },
        "org": org,
        "payment": payment,
    }

# ---------- Dagfactuur (preview/print) in 2 smaken ----------

@staff_member_required
def daily_invoice_preview_logo(request, pk: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    ctx = _ctx_for(invoice)
    ctx["send_ubl_url"] = reverse("invoice-send-ubl", args=[pk])
    ctx["papier"] = request.GET.get("papier") or "digitaal"
    tpl = "invoices/preview_logo.html"
    try:
        get_template(tpl)
    except Exception:
        tpl = "invoices/preview.html"
    return render(request, tpl, ctx)

@staff_member_required
def daily_invoice_preview_preprinted(request, pk: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    ctx = _ctx_for(invoice)
    ctx["send_ubl_url"] = reverse("invoice-send-ubl", args=[pk])
    ctx["papier"] = request.GET.get("papier") or "voorbedrukt"
    tpl = "invoices/preview_preprinted.html"
    try:
        get_template(tpl)
    except Exception:
        tpl = "invoices/preview.html"
    return render(request, tpl, ctx)

@staff_member_required
def daily_invoice_print_logo(request, pk: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    ctx = _ctx_for(invoice)
    ctx["send_ubl_url"] = reverse("invoice-send-ubl", args=[pk])
    ctx["papier"] = request.GET.get("papier") or "digitaal"
    tpl = "invoices/print_logo.html"
    try:
        get_template(tpl)
    except Exception:
        tpl = "invoices/print.html"
    return render(request, tpl, ctx)

@staff_member_required
def daily_invoice_print_preprinted(request, pk: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    ctx = _ctx_for(invoice)
    ctx["send_ubl_url"] = reverse("invoice-send-ubl", args=[pk])
    ctx["papier"] = request.GET.get("papier") or "voorbedrukt"
    tpl = "invoices/print_preprinted.html"
    try:
        get_template(tpl)
    except Exception:
        tpl = "invoices/print.html"
    return render(request, tpl, ctx)


@staff_member_required
def send_invoice_ubl(request, pk: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method != "POST":
        return redirect("daily-invoice-preview", pk=pk)

    org, _payment = _org_and_payment()
    ubl_bytes = _ubl_text(invoice, org, InvoiceLine.objects.filter(invoice=invoice).order_by("id"))

    recipient = getattr(settings, "BILLIT_FORWARD_EMAIL", None) or "spiegelvengolf-ylcpib6-nosplit@my.billit.be"
    sender = getattr(settings, "DEFAULT_FROM_EMAIL", None) or org.get("email") or "no-reply@example.com"
    subject = f"UBL factuur {invoice.number or 'concept'}"
    body = "UBL factuur bijgevoegd (Peppol/Billit doorgifte)."

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=sender,
        to=[recipient],
    )
    filename = f"invoice-{invoice.number or invoice.pk or 'concept'}.xml"
    email.attach(filename, ubl_bytes, "application/xml")
    try:
        email.send(fail_silently=False)
        messages.success(request, f"UBL verzonden naar {recipient}.")
    except Exception as exc:
        messages.error(request, f"Kon UBL niet versturen: {exc}")

    referer = request.META.get("HTTP_REFERER") or reverse("daily-invoice-preview", args=[pk])
    return redirect(referer)


class _YearInvoiceStub:
    """Kleine container zodat templates een factuur-object hebben."""

    def __init__(self, member, year: int):
        self.pk = None
        self.member = member
        self.issue_date = date(year, 1, 1)
        self.doc_type = Invoice.TYPE_INVOICE
        self.status = Invoice.STATUS_DRAFT
        self.number = None
        self.notes = ""
        account = getattr(member, "billing_account", None)
        if account is None:
            account = SimpleNamespace(
                name=_member_display_name(member),
                email=getattr(member, "email", "") or "",
                street=getattr(member, "street", "") or "",
                postal_code=getattr(member, "postal_code", "") or "",
                city=getattr(member, "city", "") or "",
                country=getattr(member, "country", "") or "",
                vat_number="",
            )
        self.account = account
        self.payment_reference_raw = ""
        self.structured_message = ""

    def payment_reference_display(self) -> str:
        return ""

    def get_status_display(self) -> str:
        return "Concept"


def _yearly_invoice_context(member, year: int):
    preview = _build_member_preview(member, year)
    invoice_obj = (
        Invoice.objects.filter(member=member, issue_date__year=year)
        .order_by("-issue_date")
        .first()
    )
    if invoice_obj is None:
        invoice_obj = _YearInvoiceStub(member, year)

    lines = []
    for section in preview["sections"]:
        person = section.get("member")
        display_name = section.get("display_name") or _member_display_name(person)
        for raw_line in section.get("lines", []):
            desc = raw_line.get("desc") or ""
            if display_name and display_name.lower() not in desc.lower():
                description = f"{display_name}: {desc}"
            else:
                description = desc
            qty = _q(raw_line.get("qty") or Decimal("1"))
            unit = _q(raw_line.get("unit") or Decimal("0"))
            vat_rate = Decimal(str(raw_line.get("vat_rate") or "0"))
            line_excl = _q(raw_line.get("total") or qty * unit)
            vat_amount = _q(raw_line.get("total_vat") or (line_excl * vat_rate / Decimal("100")))
            line_incl = _q(raw_line.get("total_incl") or (line_excl + vat_amount))
            lines.append({
                "description": description,
                "quantity": qty,
                "unit_price_excl": unit,
                "vat_rate": vat_rate,
                "line_excl": line_excl,
                "vat_amount": vat_amount,
                "line_incl": line_incl,
            })

    vat_summary = _vat_summary(lines) if lines else []
    org, payment = _org_and_payment()

    ogm = ""
    payment_ref = getattr(invoice_obj, "payment_reference_display", None)
    if callable(payment_ref):
        ogm = payment_ref() or ""
    if not ogm:
        ogm = getattr(invoice_obj, "structured_message", "") or getattr(invoice_obj, "payment_reference_raw", "")
    if ogm:
        payment["ogm"] = ogm

    totals_parts = {
        "excl": _split_amount(preview["total_excl"]),
        "vat": _split_amount(preview["total_vat"]),
        "incl": _split_amount(preview["total_incl"]),
    }

    return {
        "invoice": invoice_obj,
        "lines": lines,
        "vat_summary": vat_summary,
        "totals_parts": totals_parts,
        "org": org,
        "payment": payment,
        "year": year,
        "preview_sections": preview["sections"],
    }


def _iter_yearly_invoice_contexts(year: int):
    active_members = Member.objects.filter(active=True)
    owner_map = {}
    for person in active_members:
        owner = _billing_owner(person)
        owner_pk = getattr(owner, "pk", None)
        if owner_pk is None:
            continue
        owner_map.setdefault(owner_pk, owner)

    owners = sorted(
        owner_map.values(),
        key=lambda m: (
            (getattr(m, "last_name", "") or "").casefold(),
            (getattr(m, "first_name", "") or "").casefold(),
            getattr(m, "pk", 0),
        ),
    )

    contexts = []
    for owner in owners:
        ctx = _yearly_invoice_context(owner, year)
        if ctx["lines"]:
            contexts.append(ctx)
    return contexts


def _yearly_batch_response(request, year: int, papier: str, view_mode: str):
    contexts = _iter_yearly_invoice_contexts(year)
    if not contexts:
        messages.info(request, f"Geen jaarfacturen met lijnen gevonden voor {year}.")
        url = f"{reverse('admin-yearly-totals')}?jaar={year}"
        return redirect(url)
    template = "invoices/preview_batch.html" if view_mode == "preview" else "invoices/print_batch.html"
    return render(request, template, {
        "year": year,
        "papier": papier,
        "invoices": contexts,
        "mode": view_mode,
    })


@staff_member_required
def yearly_invoice_preview_logo(request, member_id: int, year: int):
    member = get_object_or_404(Member, pk=member_id)
    ctx = _yearly_invoice_context(_billing_owner(member), int(year))
    ctx["papier"] = request.GET.get("papier") or "digitaal"
    tpl = "invoices/preview_logo.html"
    try:
        get_template(tpl)
    except Exception:
        tpl = "invoices/preview.html"
    return render(request, tpl, ctx)


@staff_member_required
def yearly_invoice_preview_preprinted(request, member_id: int, year: int):
    member = get_object_or_404(Member, pk=member_id)
    ctx = _yearly_invoice_context(_billing_owner(member), int(year))
    ctx["papier"] = request.GET.get("papier") or "voorbedrukt"
    tpl = "invoices/preview_preprinted.html"
    try:
        get_template(tpl)
    except Exception:
        tpl = "invoices/preview.html"
    return render(request, tpl, ctx)


@staff_member_required
def yearly_invoice_print_logo(request, member_id: int, year: int):
    member = get_object_or_404(Member, pk=member_id)
    ctx = _yearly_invoice_context(_billing_owner(member), int(year))
    ctx["papier"] = request.GET.get("papier") or "digitaal"
    tpl = "invoices/print_logo.html"
    try:
        get_template(tpl)
    except Exception:
        tpl = "invoices/print.html"
    return render(request, tpl, ctx)


@staff_member_required
def yearly_invoice_print_preprinted(request, member_id: int, year: int):
    member = get_object_or_404(Member, pk=member_id)
    ctx = _yearly_invoice_context(_billing_owner(member), int(year))
    ctx["papier"] = request.GET.get("papier") or "voorbedrukt"
    tpl = "invoices/print_preprinted.html"
    try:
        get_template(tpl)
    except Exception:
        tpl = "invoices/print.html"
    return render(request, tpl, ctx)


@staff_member_required
def yearly_invoice_batch_preview_logo(request, year: int):
    return _yearly_batch_response(request, int(year), "digitaal", "preview")


@staff_member_required
def yearly_invoice_batch_preview_preprinted(request, year: int):
    return _yearly_batch_response(request, int(year), "voorbedrukt", "preview")


@staff_member_required
def yearly_invoice_batch_print_logo(request, year: int):
    return _yearly_batch_response(request, int(year), "digitaal", "print")


@staff_member_required
def yearly_invoice_batch_print_preprinted(request, year: int):
    return _yearly_batch_response(request, int(year), "voorbedrukt", "print")

# ---------- Product-catalogus voor inline autofill ----------

@staff_member_required
def products_catalog_json(request):
    data = {}
    for p in Product.objects.filter(active=True):
        try:
            vat = int(Decimal(str(getattr(p, "default_vat_rate", 21))))
        except Exception:
            vat = 21
        price = getattr(p, "default_price_excl", None)
        price_s = ""
        if price not in (None, ""):
            try:
                price_s = f"{Decimal(str(price)):.2f}"
            except Exception:
                price_s = ""
        data[str(p.id)] = {
            "name": getattr(p, "name", str(p)) or str(p),
            "unit_price_excl": price_s,
            "vat_rate": vat,
        }
    return JsonResponse(data)


# ---------- Lidfactuur-preview (volgend jaar) ----------

def _member_age_on(year: int, dob):
    if not dob:
        return None
    ref = date(year, 1, 1)
    try:
        return max(0, ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day)))
    except Exception:
        return None

def _member_role_tag(member):
    val = (getattr(member, "household_role", "") or "").strip().lower()
    if val in {"prt", "partner", "partner_role", "husband", "wife"}:
        return "PRT"
    if val in {"kid", "child"}:
        return "KID"
    return "IND"

def _member_display_name(member):
    first = (getattr(member, "first_name", "") or "").strip()
    last = (getattr(member, "last_name", "") or "").strip()
    name = " ".join(part for part in (first, last) if part)
    if name:
        return name
    fallback = getattr(member, "last_name", None) or getattr(member, "first_name", None)
    if fallback:
        return str(fallback)
    return str(member)

def _member_role_display(member):
    display_method = getattr(member, "get_household_role_display", None)
    if callable(display_method):
        label = display_method() or ""
        return label.strip()
    raw = getattr(member, "household_role", "") or ""
    return raw.strip()

def _billing_owner(member, _seen=None):
    pk = getattr(member, "pk", None)
    if _seen is None:
        _seen = set()
    if pk and pk in _seen:
        return member
    if pk:
        _seen.add(pk)
    if getattr(member, "billing_account_id", None):
        return member
    via = getattr(member, "factureren_via", None)
    via_pk = getattr(via, "pk", None)
    if via and via_pk and via_pk != pk:
        return _billing_owner(via, _seen)
    head = getattr(member, "household_head", None)
    head_pk = getattr(head, "pk", None)
    if head and head_pk and head_pk != pk:
        return _billing_owner(head, _seen)
    return member

def _account_display(account):
    if not account:
        return ""
    parts = []
    name = (getattr(account, "name", "") or "").strip()
    if name:
        parts.append(name)
    email = (getattr(account, "email", "") or "").strip()
    if email:
        parts.append(email)
    address_parts = [
        (getattr(account, "street", "") or "").strip(),
        " ".join(filter(None, [
            (getattr(account, "postal_code", "") or "").strip(),
            (getattr(account, "city", "") or "").strip(),
        ])).strip(),
    ]
    address = " ".join(part for part in address_parts if part).strip()
    if address:
        parts.append(address)
    return " — ".join(parts) if parts else str(account)

def _household_dependents(head):
    if Member is None:
        return []
    qs = Member.objects.filter(active=True).exclude(pk=head.pk)
    qs = qs.filter(Q(factureren_via=head) | Q(household_head=head)).distinct()
    return list(qs)

def _federation_enabled(member):
    exclusions = set(getattr(member, "billing_code_exclusions", []) or [])
    if "FEDERATIE" in exclusions:
        return False
    val = getattr(member, "federale_bijdrage_via_spiegelven", None)
    if val is None:
        val = getattr(member, "federation_via_club", False)
    return bool(val)

def _membership_codes(member, year: int):
    course = (getattr(member, "course", "") or "").strip().upper()
    age = _member_age_on(year, getattr(member, "date_of_birth", None) or getattr(member, "birth_date", None))
    role = _member_role_tag(member)

    lid = None
    fed = None

    if course == "CC":
        include_fed = _federation_enabled(member)
        if age is None:
            lid = f"LID_CC_{role}"
            if include_fed:
                fed = f"FED_CC_{role if role in {'IND', 'PRT'} else 'IND'}"
        elif age <= 15:
            lid = "LID_CC_KID_0_15"
            if include_fed:
                fed = "FED_CC_KID"
        elif 16 <= age <= 21:
            lid = "LID_CC_KID_16_21"
            if include_fed:
                fed = "FED_CC_KID"
        elif 22 <= age <= 26:
            lid = "LID_CC_YA_22_26"
            if include_fed:
                fed = f"FED_CC_{role}"
        elif 27 <= age <= 29:
            lid = "LID_CC_YA_27_29"
            if include_fed:
                fed = f"FED_CC_{role}"
        elif 30 <= age <= 35:
            lid = "LID_CC_YA_30_35"
            if include_fed:
                fed = f"FED_CC_{role}"
        else:
            lid = f"LID_CC_{role}"
            if include_fed:
                fed = f"FED_CC_{role}"
    elif course == "P3":
        base = role if role in {"IND", "PRT"} else "IND"
        if age is None:
            lid = f"P3_{base}"
        elif age <= 21:
            lid = "P3_KID"
        else:
            lid = f"P3_{base}"
        fed = None

    return [c for c in (lid, fed) if c]

def _investment_codes(member, year: int):
    codes = []
    plan = getattr(member, "investment_plan", "") or ""
    role = _member_role_tag(member)
    if plan == getattr(Member, "INVESTMENT_PLAN_DIRECT", "direct"):
        if getattr(member, "investment_direct_bill_next", False):
            codes.append(f"INV_{role}")
    if plan == getattr(Member, "INVESTMENT_PLAN_FLEX", "flex"):
        if getattr(member, "flex_years_remaining", 0):
            codes.append(f"INV_FLEX_{role}")
    return codes

def _asset_codes(member):
    if MemberAsset is None:
        return []
    qs = MemberAsset.objects.filter(member=member)
    try:
        qs = qs.filter(active=True)
    except Exception:
        pass
    return [c for c in qs.values_list("asset_type", flat=True) if c]

def _unique_keep_order(seq):
    seen = set()
    out = []
    for item in seq:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out

def _apply_proration(lines, member):
    for line in lines:
        code = (line.get("code") or "").upper()
        desc = (line.get("desc") or "").lower()
        qty = Decimal(str(line.get("qty", "1")))
        total = Decimal(str(line.get("total", "0") or 0))

        if qty <= 0:
            qty = Decimal("1")

        plan = getattr(member, "investment_plan", "") or ""
        if code in ("INV_IND", "INV_PRT") or ("invest" in desc and not code.startswith("INV_FLEX")):
            if plan == getattr(Member, "INVESTMENT_PLAN_DIRECT", "direct") and getattr(member, "investment_direct_bill_next", False):
                amount = getattr(member, "investment_direct_amount", None)
                if amount is not None:
                    try:
                        new_total = Decimal(str(amount)).quantize(Decimal("0.01"))
                    except Exception:
                        new_total = Decimal("0.00")
                    if new_total > 0:
                        line["total"] = new_total
                        line["unit"] = (new_total / qty).quantize(Decimal("0.01"))
                        if not line.get("desc"):
                            line["desc"] = "Investering (eenmalig)"
                        continue
            line["total"] = Decimal("0.00")
            line["unit"] = Decimal("0.00")
            continue

        if code.startswith("INV_FLEX") or "flex" in desc:
            if plan == getattr(Member, "INVESTMENT_PLAN_FLEX", "flex") and getattr(member, "flex_years_remaining", 0) > 0:
                amount = getattr(member, "invest_flex_locked_amount", None)
                if amount is not None:
                    try:
                        new_total = Decimal(str(amount)).quantize(Decimal("0.01"))
                    except Exception:
                        new_total = Decimal("0.00")
                    if new_total > 0:
                        line["total"] = new_total
                        line["unit"] = (new_total / qty).quantize(Decimal("0.01"))
                        if not line.get("desc"):
                            line["desc"] = "Investering (flex)"
                        continue
            line["total"] = Decimal("0.00")
            line["unit"] = Decimal("0.00")

DESCRIPTIONS = {
    "LID_CC_IND": "Lidgeld CC (individueel)",
    "LID_CC_PRT": "Lidgeld CC (partner)",
    "LID_CC_KID_0_15": "Lidgeld CC (kind 0–15)",
    "LID_CC_KID_16_21": "Lidgeld CC (kind 16–21)",
    "LID_CC_YA_22_26": "Lidgeld CC (jongvolw. 22–26)",
    "LID_CC_YA_27_29": "Lidgeld CC (jongvolw. 27–29)",
    "LID_CC_YA_30_35": "Lidgeld CC (jongvolw. 30–35)",
    "FED_CC_IND": "Federatie CC (individueel)",
    "FED_CC_PRT": "Federatie CC (partner)",
    "FED_CC_KID": "Federatie CC (kind)",
    "P3_IND": "Lidgeld P3 (individueel)",
    "P3_PRT": "Lidgeld P3 (partner)",
    "P3_KID": "Lidgeld P3 (kind)",
    "INV_IND": "Investering (individueel)",
    "INV_PRT": "Investering (partner)",
    "INV_FLEX_IND": "Investering flex (individueel)",
    "INV_FLEX_PRT": "Investering flex (partner)",
    "VST_KAST": "Kast",
    "KAR_KLN": "Kar-kast",
    "KAR_ELEC": "E-kar-kast",
}


def _build_member_preview(member, year: int):
    preview_members = [member]
    member_pk = getattr(member, "pk", None)
    member_head_id = getattr(member, "household_head_id", None)
    # Neem ook afhankelijken mee als dit lid het gezinshoofd is (None of zichzelf).
    if member_head_id is None or member_head_id == member_pk:
        dependents = _household_dependents(member)
        partners, children, others = [], [], []
        partner_code = (getattr(Member, "ROLE_PARTNER", "partner") or "partner").lower()
        child_code = (getattr(Member, "ROLE_CHILD", "child") or "child").lower()

        def _sort_key(m):
            return (
                (getattr(m, "last_name", "") or "").lower(),
                (getattr(m, "first_name", "") or "").lower(),
                getattr(m, "pk", 0),
            )

        for dep in dependents:
            role = (getattr(dep, "household_role", "") or "").strip().lower()
            if role == partner_code:
                partners.append(dep)
            elif role == child_code:
                children.append(dep)
            else:
                others.append(dep)

        for group in (partners, children, others):
            group.sort(key=_sort_key)

        preview_members = [member, *partners, *children, *others]

    member_codes = []
    codes_seen = set()
    for person in preview_members:
        codes = _unique_keep_order(
            _membership_codes(person, year)
            + _investment_codes(person, year)
            + _asset_codes(person)
        )
        exclusions = set(getattr(person, "billing_code_exclusions", []) or [])
        if "LIDMAATSCHAP" in exclusions:
            exclusions = (exclusions - {"LIDMAATSCHAP"}) | {
                "LID_CC_IND",
                "LID_CC_KID_0_15",
                "LID_CC_KID_16_21",
                "LID_CC_PRT",
                "LID_CC_YA_22_26",
                "LID_CC_YA_27_29",
                "LID_CC_YA_30_35",
                "P3_IND",
                "P3_KID",
                "P3_PRT",
            }
        if exclusions:
            codes = [c for c in codes if c not in exclusions]
        member_codes.append((person, codes))
        codes_seen.update(codes)

    price_map = {}
    if YearPricing is not None and codes_seen:
        # Eerst proberen het gevraagde jaar; als er niets is, neem het meest recente jaar met prijzen.
        target_year = year
        qs = YearPricing.objects.filter(year=target_year, code__in=codes_seen)
        if not qs.exists():
            fallback_year = (
                YearPricing.objects.order_by("-year")
                .values_list("year", flat=True)
                .first()
            )
            if fallback_year:
                target_year = fallback_year
                qs = YearPricing.objects.filter(year=target_year, code__in=codes_seen)
        for yp in qs:
            try:
                amount = Decimal(str(yp.amount or "0")).quantize(Decimal("0.01"))
            except Exception:
                amount = Decimal("0.00")
            try:
                vat_rate = Decimal(str(getattr(yp, "vat_rate", "0") or "0"))
            except Exception:
                vat_rate = Decimal("0")
            price_map[yp.code] = {
                "amount": amount,
                "vat_rate": vat_rate,
            }

    sections = []
    notes = []
    for person, codes in member_codes:
        billing_owner = _billing_owner(person)
        member_pk = getattr(member, "pk", None)
        owner_pk = getattr(billing_owner, "pk", None)
        if member_pk is not None and owner_pk is not None and owner_pk != member_pk:
            continue
        if (member_pk is None or owner_pk is None) and billing_owner is not member:
            continue

        person_lines = []
        for code in codes:
            price_info = price_map.get(code)
            if price_info is None:
                notes.append(f"Geen prijs gevonden voor code {code} ({year}) voor {_member_display_name(person)}.")
                amount = Decimal("0.00")
                vat_rate = Decimal("0.00")
            else:
                amount = price_info.get("amount", Decimal("0.00"))
                vat_rate = Decimal(str(price_info.get("vat_rate", "0") or 0))
            qty = Decimal("1")
            vat_rate_decimal = (vat_rate / Decimal("100"))
            line_total = (amount * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            line_vat = (line_total * vat_rate_decimal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            person_lines.append({
                "code": code,
                "desc": DESCRIPTIONS.get(code, code),
                "qty": qty,
                "unit": amount,
                "total": line_total,
                "vat_rate": vat_rate,
                "total_vat": line_vat,
                "total_incl": (line_total + line_vat).quantize(Decimal("0.01")),
            })

        _apply_proration(person_lines, person)

        for line in person_lines:
            qty = Decimal(str(line.get("qty", "1") or 1))
            unit = Decimal(str(line.get("unit", "0") or 0))
            if qty <= 0:
                qty = Decimal("1")
            line_total = (unit * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            rate_percent = Decimal(str(line.get("vat_rate", "0") or 0))
            rate_decimal = rate_percent / Decimal("100")
            vat_amount = (line_total * rate_decimal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            line["total"] = line_total
            line["total_vat"] = vat_amount
            line["total_incl"] = (line_total + vat_amount).quantize(Decimal("0.01"))

        subtotal_excl = sum(
            (Decimal(str(line.get("total", "0") or 0)) for line in person_lines),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))
        subtotal_vat = sum(
            (Decimal(str(line.get("total_vat", "0") or 0)) for line in person_lines),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))
        subtotal_incl = (subtotal_excl + subtotal_vat).quantize(Decimal("0.01"))

        billing_account = getattr(billing_owner, "billing_account", None)
        billing_account_display = _account_display(billing_account) or None
        age = _member_age_on(
            year,
            getattr(person, "date_of_birth", None) or getattr(person, "birth_date", None),
        )
        sections.append({
            "member": person,
            "display_name": _member_display_name(person),
            "role": _member_role_display(person),
            "age": age,
            "lines": person_lines,
            "subtotal_excl": subtotal_excl,
            "subtotal_vat": subtotal_vat,
            "subtotal_incl": subtotal_incl,
            "billing_owner": billing_owner,
            "billing_owner_display": _member_display_name(billing_owner),
            "billing_account": billing_account,
            "billing_account_display": billing_account_display,
        })

    total_excl = sum((section["subtotal_excl"] for section in sections), Decimal("0.00")).quantize(Decimal("0.01"))
    total_vat = sum((section["subtotal_vat"] for section in sections), Decimal("0.00")).quantize(Decimal("0.01"))
    total_incl = (total_excl + total_vat).quantize(Decimal("0.01"))

    primary_billing_owner = _billing_owner(member)
    primary_account = getattr(primary_billing_owner, "billing_account", None)
    primary_account_display = _account_display(primary_account) or None
    primary_owner_display = _member_display_name(primary_billing_owner)

    return {
        "sections": sections,
        "notes": notes,
        "total_excl": total_excl,
        "total_vat": total_vat,
        "total_incl": total_incl,
        "primary_account_display": primary_account_display,
        "primary_owner_display": primary_owner_display,
    }

@staff_member_required
def member_invoice_preview(request, member_id: int, year: int):
    member = get_object_or_404(Member, pk=member_id)
    if not getattr(member, "active", True):
        messages.warning(request, "Dit lid is niet actief; er wordt geen factuurvoorbeeld getoond.")
        return redirect('admin:core_member_change', member_id)
    year = int(year)

    invoice_target = _billing_owner(member)
    preview = _build_member_preview(invoice_target, year)

    ctx = {
        "member": invoice_target,
        "requested_member": member,
        "year": year,
        "billing_sections": preview["sections"],
        "lines": preview["sections"][0]["lines"] if preview["sections"] else [],
        "total": preview["total_incl"],
        "notes": preview["notes"],
        "billing_via_account_display": preview["primary_account_display"],
        "billing_via_member_display": preview["primary_owner_display"],
        "has_multiple_sections": len(preview["sections"]) > 1,
        "total_excl": preview["total_excl"],
        "total_vat": preview["total_vat"],
        "total_incl": preview["total_incl"],
    }
    return render(request, "admin/invoice_preview.html", ctx)

def compute_yearly_totals(year: int):
    active_members = Member.objects.filter(active=True)
    owner_map = {}
    for person in active_members:
        owner = _billing_owner(person)
        owner_pk = getattr(owner, "pk", None)
        if owner_pk is None:
            continue
        owner_map.setdefault(owner_pk, owner)

    owners = sorted(
        owner_map.values(),
        key=lambda m: (
            (getattr(m, "last_name", "") or "").casefold(),
            (getattr(m, "first_name", "") or "").casefold(),
            getattr(m, "pk", 0),
        ),
    )

    component_totals = {}
    notes = []
    total_excl = Decimal("0.00")
    total_vat = Decimal("0.00")
    total_incl = Decimal("0.00")

    for owner in owners:
        preview = _build_member_preview(owner, year)
        total_excl += preview["total_excl"]
        total_vat += preview["total_vat"]
        total_incl += preview["total_incl"]
        notes.extend(preview["notes"])

        for section in preview["sections"]:
            for line in section["lines"]:
                key = line["code"]
                entry = component_totals.setdefault(
                    key,
                    {
                        "code": key,
                        "description": line["desc"],
                        "total_excl": Decimal("0.00"),
                        "total_vat": Decimal("0.00"),
                        "total_incl": Decimal("0.00"),
                        "members_map": {},
                    },
                )
                entry["total_excl"] = (entry["total_excl"] + line["total"]).quantize(Decimal("0.01"))
                entry["total_vat"] = (entry["total_vat"] + line["total_vat"]).quantize(Decimal("0.01"))
                entry["total_incl"] = (entry["total_incl"] + line["total_incl"]).quantize(Decimal("0.01"))

                members_map = entry["members_map"]
                member_obj = section.get("member")
                billing_owner = section.get("billing_owner")

                member_last = (getattr(member_obj, "last_name", "") or "").strip()
                member_first = (getattr(member_obj, "first_name", "") or "").strip()
                member_display = (
                    section.get("display_name")
                    or " ".join(part for part in (member_first, member_last) if part).strip()
                    or str(member_obj)
                )
                member_pk = getattr(member_obj, "pk", None)
                member_key = member_pk if member_pk is not None else (member_last.lower(), member_first.lower(), member_display.lower())

                owner_last = (getattr(billing_owner, "last_name", "") or "").strip()
                owner_first = (getattr(billing_owner, "first_name", "") or "").strip()
                owner_display = (
                    section.get("billing_owner_display")
                    or " ".join(part for part in (owner_first, owner_last) if part).strip()
                )
                if not owner_display:
                    owner_display = "—"

                owner_pk = getattr(billing_owner, "pk", None)
                if member_pk is not None and owner_pk is not None:
                    same_person = member_pk == owner_pk
                else:
                    same_person = (
                        (member_last or "").casefold(),
                        (member_first or "").casefold(),
                    ) == (
                        (owner_last or "").casefold(),
                        (owner_first or "").casefold(),
                    )

                member_entry = members_map.get(member_key)
                if not member_entry:
                    member_entry = {
                        "member_name": member_display,
                        "member_first_name": member_first,
                        "member_last_name": member_last,
                        "billing_owner_name": owner_display,
                        "billing_owner_first_name": owner_first,
                        "billing_owner_last_name": owner_last,
                        "billing_owner_same": same_person,
                    }
                    members_map[member_key] = member_entry
                else:
                    member_entry["billing_owner_same"] = member_entry.get("billing_owner_same", True) and same_person

    components = []
    for item in component_totals.values():
        members_map = item.pop("members_map", {})
        members = list(members_map.values())
        for entry in members:
            entry.setdefault("billing_owner_same", True)
        members.sort(
            key=lambda m: (
                (m["member_last_name"] or "").casefold(),
                (m["member_first_name"] or "").casefold(),
                (m["member_name"] or "").casefold(),
            )
        )
        item["members"] = members
        item["member_count"] = len(members)
        components.append(item)

    components.sort(key=lambda item: item["code"])

    return {
        "year": year,
        "components": components,
        "total_excl": total_excl.quantize(Decimal("0.01")),
        "total_vat": total_vat.quantize(Decimal("0.01")),
        "total_incl": total_incl.quantize(Decimal("0.01")),
        "notes": notes,
        "households": len(owners),
    }

@staff_member_required
def admin_yearly_totals(request):
    default_year = timezone.now().year + 1
    param = request.GET.get("jaar") or request.GET.get("year")
    try:
        selected = int(param) if param else default_year
    except (TypeError, ValueError):
        selected = default_year

    if YearPricing is not None:
        year_candidates = list(YearPricing.objects.order_by("-year").values_list("year", flat=True).distinct())
    else:
        year_candidates = []
    year_candidates.extend([selected, default_year])
    years = sorted(set(year_candidates), reverse=True)

    totals = compute_yearly_totals(selected)
    batch_contexts = _iter_yearly_invoice_contexts(selected)

    context = admin.site.each_context(request)
    context.update({
        "title": f"Totaal jaarfactuur {selected}",
        "selected_year": selected,
        "years": years,
        "components": totals["components"],
        "total_excl": totals["total_excl"],
        "total_vat": totals["total_vat"],
        "total_incl": totals["total_incl"],
        "notes": totals["notes"],
        "households": totals["households"],
        "batch_invoice_count": len(batch_contexts),
        "batch_urls": {
            "preview_logo": reverse("yearly-invoice-batch-preview-logo", args=[selected]),
            "preview_preprinted": reverse("yearly-invoice-batch-preview-preprinted", args=[selected]),
            "print_logo": reverse("yearly-invoice-batch-print-logo", args=[selected]),
            "print_preprinted": reverse("yearly-invoice-batch-print-preprinted", args=[selected]),
        },
    })
    return TemplateResponse(request, "admin/core/year_totals_page.html", context)

@staff_member_required
def member_invoice_preview_default(request, member_id: int):
    year = timezone.now().year + 1
    return member_invoice_preview(request, member_id, year)
