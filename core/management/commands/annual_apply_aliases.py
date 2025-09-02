from __future__ import annotations
from django.core.management.base import BaseCommand
from django.db import transaction

class Command(BaseCommand):
    help = (
        "Pas alias-mapping toe op YearPricing: "
        "deactiveer alias-records als de canonieke bestaat, "
        "of zet de omschrijving om naar de canonieke term."
    )

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, help="Beperk tot een bepaald jaar")
        parser.add_argument("--apply", action="store_true", help="Voer de wijzigingen effectief uit")

    def handle(self, *args, **opts):
        from core.models import YearPricing
        from core.annual_aliases import canonical_desc

        qs = YearPricing.objects.all()
        if opts.get("year"):
            qs = qs.filter(year=opts["year"])

        changes = []
        for yp in qs:
            canon = canonical_desc(yp.description or "")
            if canon != (yp.description or ""):
                changes.append(yp)

        if not changes:
            self.stdout.write(self.style.SUCCESS("Geen alias-gevallen gevonden."))
            return

        # Toon plan
        self.stdout.write(self.style.WARNING(f"Gevonden alias-gevallen: {len(changes)}"))
        for yp in changes:
            self.stdout.write(
                f" - [id={yp.id}] {yp.year} | code={yp.code} | '{yp.description}'  ->  '{canonical_desc(yp.description)}' "
                f"(bedrag={yp.amount}, BTW={yp.vat_rate}%, actief={yp.active})"
            )

        if not opts.get("apply"):
            self.stdout.write(self.style.WARNING("\nDry-run. Voeg --apply toe om te wijzigen."))
            return

        # Pas daadwerkelijk toe
        updated, deactivated = 0, 0
        with transaction.atomic():
            for yp in changes:
                canon = canonical_desc(yp.description)
                # Bestaat er al een canoniek record in hetzelfde jaar?
                exists = YearPricing.objects.filter(year=yp.year, description=canon).exclude(pk=yp.pk).first()

                if exists:
                    # Alias deactiveren — canoniek record laten gelden
                    if yp.active:
                        yp.active = False
                        yp.save(update_fields=["active"])
                        deactivated += 1
                else:
                    # Geen canoniek record -> omschrijving rechttrekken naar de canonieke term
                    if yp.description != canon:
                        yp.description = canon
                        yp.save(update_fields=["description"])
                        updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Klaar. Gewijzigd: descriptions={updated}, gedeactiveerd={deactivated}."
        ))
