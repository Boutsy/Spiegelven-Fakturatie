from django import forms
from .models import InvoiceLine

class InvoiceLineForm(forms.ModelForm):
    class Meta:
        model = InvoiceLine
        fields = ["product","description","quantity","unit_price_excl","vat_rate"]
        labels = {
            "product": "Product",
            "description": "Omschrijving",
            "quantity": "Aantal",
            "unit_price_excl": "Eenheidsprijs (excl.)",
            "vat_rate": "BTW %",
        }
