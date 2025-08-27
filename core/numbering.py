import re
from django.db import transaction
from django.utils import timezone
from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from .models import Invoice, YearSequence

_NUM_RE = re.compile(r"^(?P<year>\d{4})(?P<seq>\d{5})$")

def _parse_number(num: str):
    m = _NUM_RE.match(num or "")
    if not m:
        return None, None
    return int(m.group("year")), int(m.group("seq"))

def _current_year(inv: Invoice) -> int:
    if inv.issue_date:
        return inv.issue_date.year
    return timezone.now().year

def _ensure_unique(inv: Invoice):
    # Uniek nummer afdwingen via applicatielogica (ook als DB-constraint ontbreekt)
    qs = Invoice.objects.filter(number=inv.number)
    if inv.pk:
        qs = qs.exclude(pk=inv.pk)
    if qs.exists():
        raise ValidationError(f"Nummer {inv.number} is al in gebruik.")

def _assign_next_number(inv: Invoice):
    year = _current_year(inv)
    with transaction.atomic():
        seq, _created = YearSequence.objects.select_for_update().get_or_create(
            year=year, defaults={"last_number": 0}
        )
        next_seq = (seq.last_number or 0) + 1
        inv.number = f"{year}{next_seq:05d}"
        _ensure_unique(inv)
        seq.last_number = next_seq
        seq.save(update_fields=["last_number"])

def _accept_manual_number_and_bump_sequence_if_needed(inv: Invoice):
    """Als gebruiker zelf 'number' invult:
    - format controleren (YYYY#####)
    - jaar moet overeenkomen met issue_date-jaar
    - YearSequence.last_number verhogen indien nodig
    """
    _ensure_unique(inv)
    year, seq = _parse_number(inv.number)
    if year is None:
        raise ValidationError("Ongeldig formaat voor Nummer. Verwacht: JJJJ##### (bv. 202500015).")
    year_from_issue = _current_year(inv)
    if year != year_from_issue:
        raise ValidationError(f"De eerste 4 cijfers van het nummer ({year}) moeten overeenkomen met het factuurjaar ({year_from_issue}).")

    with transaction.atomic():
        yseq, _ = YearSequence.objects.select_for_update().get_or_create(
            year=year, defaults={"last_number": 0}
        )
        if (yseq.last_number or 0) < seq:
            # Als je bv. 202500012 invult terwijl last_number 11 is, schuiven we de teller mee op
            yseq.last_number = seq
            yseq.save(update_fields=["last_number"])

@receiver(pre_save, sender=Invoice)
def set_or_validate_number_on_finalize(sender, instance: Invoice, **kwargs):
    """Nummer toekennen bij overgang naar FINALIZED (of valideren als handmatig gezet).
    We wijzigen het nummer alleen bij finaliseren en alleen als het nog leeg is.
    """
    # Haal oude status/nummer op (voor transitie-check)
    old_status = None
    old_number = None
    if instance.pk:
        try:
            prev = Invoice.objects.only("status", "number").get(pk=instance.pk)
            old_status = (prev.status or "").upper()
            old_number = prev.number
        except Invoice.DoesNotExist:
            pass

    new_status = (instance.status or "").upper()

    # Alleen ingrijpen wanneer je naar FINALIZED gaat
    going_to_finalized = (old_status != "FINALIZED") and (new_status == "FINALIZED")

    if going_to_finalized:
        if not instance.number:
            # Geen nummer ingevuld? Automatisch toekennen (volgende in rij)
            _assign_next_number(instance)
        else:
            # Handmatig ingevuld nummer gebruiken, mits geldig/uniek.
            _accept_manual_number_and_bump_sequence_if_needed(instance)
    else:
        # Niet naar FINALIZED? Niets doen, maar als nummer reeds gezet is en veranderd wordt,
        # hou dan minimale validatie aan (optioneel, hier niet nodig).
        pass

@receiver(post_delete, sender=Invoice)
def roll_back_sequence_on_delete(sender, instance: Invoice, **kwargs):
    """Als de laatst genummerde factuur/creditnota verwijderd wordt,
    draai de jaar-teller één stap terug zodat het nummer hergebruikt wordt.
    """
    if not instance.number:
        return
    year, seq = _parse_number(instance.number)
    if year is None:
        return
    try:
        with transaction.atomic():
            yseq = YearSequence.objects.select_for_update().get(year=year)
            if (yseq.last_number or 0) == seq:
                yseq.last_number = max(0, seq - 1)
                yseq.save(update_fields=["last_number"])
    except YearSequence.DoesNotExist:
        # Geen teller voor dit jaar? Dan niets te herstellen.
        pass
