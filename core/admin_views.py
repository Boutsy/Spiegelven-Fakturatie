from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404
from django.template.loader import get_template
from django.core.exceptions import ObjectDoesNotExist
from core.models import Member, Invoice


def _lookup_member(val):
    try:
        return Member.objects.get(pk=int(val))
    except Exception:
        pass
    try:
        return Member.objects.get(external_id=str(val))
    except ObjectDoesNotExist:
        return None


@staff_member_required
def member_invoice_preview_default(request, pk: int):
    member = _lookup_member(pk) or get_object_or_404(Member, pk=pk)
    ctx = {"member": member, "preview_title": "Voorbeeldfactuur (default)"}
    return render(request, "admin/invoice_preview.html", ctx)


def invoice_preview_public(request, pk: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    ctx = {"invoice": invoice, "preview_title": "Voorbeeldfactuur"}
    return render(request, "invoices/preview.html", ctx)


@staff_member_required
def invoice_preview(request, pk: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    return render(request, "invoices/preview.html", {"invoice": invoice})


@staff_member_required
def invoice_print(request, pk: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    tpl = "invoices/print.html"
    try:
        get_template(tpl)
    except Exception:
        tpl = "invoices/preview.html"
    return render(request, tpl, {"invoice": invoice})