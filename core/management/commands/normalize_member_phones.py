from django.core.management.base import BaseCommand
from django.apps import apps
from core.phonefmt import normalize_phone_be_store

class Command(BaseCommand):
    help = "Normaliseer alle Member-telefoonvelden naar opslagformaat (+32… / +CC…)."

    def handle(self, *args, **opts):
        M = apps.get_model("core","Member")
        updated = 0
        fields = [fn for fn in ("phone_private","phone_mobile","phone_work","phone","mobile","gsm") if fn in {f.name for f in M._meta.get_fields()}]
        for m in M.objects.all():
            changed = False
            for fn in fields:
                old = getattr(m, fn, "") or ""
                new = normalize_phone_be_store(old)
                if new != old:
                    setattr(m, fn, new)
                    changed = True
            if changed:
                m.save(update_fields=fields)
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Genormaliseerd (opslagformaat) bij {updated} members"))
