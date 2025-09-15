# Spiegelven-Fakturatie

![Debug](https://img.shields.io/badge/ChatGPT%20debug-on%20main-blue?style=for-the-badge)
![Workflow](https://img.shields.io/badge/workflow-snapshot%20to%20main-brightgreen?style=for-the-badge)

![Workflow](https://img.shields.io/badge/workflow-snapshot%20to%20main-brightgreen?style=for-the-badge)

## 🔑 Workflow checklist

1. **Code aanpassen** in VS Code (branch = `main`).  
2. **Cmd+Option+S** → snapshot commit + push naar GitHub (`main`).  
3. **Controle nodig?** → ChatGPT kijkt rechtstreeks in `main` op GitHub.  
4. **Altijd up-to-date** → geen zipjes of manuele uploads meer nodig.  

---



## ℹ️ Debug & controle

ChatGPT kijkt **altijd rechtstreeks in de laatste versie van de `main` branch** op GitHub.  
➡️ Zorg dat je na wijzigingen in VS Code **Cmd+Option+S** gebruikt, zodat alles meteen up-to-date staat.  
➡️ Geen zipjes of losse uploads meer nodig.

# Spiegelven-Fakturatie

![Workflow](https://img.shields.io/badge/workflow-snapshot%20to%20main-brightgreen?style=for-the-badge)
![Debug](https://img.shields.io/badge/ChatGPT%20debug-on%20main-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.12-yellow?style=for-the-badge)
![Django](https://img.shields.io/badge/Django-5.0.6-green?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-compose-blue?style=for-the-badge)

---

## 🔑 Workflow checklist
1. **Code aanpassen** in VS Code (branch = `main`).  
2. **Cmd+Option+S** → snapshot commit + push naar GitHub (`main`).  
3. **Controle nodig?** → ChatGPT kijkt rechtstreeks in `main` op GitHub.  
4. **Altijd up-to-date** → geen zipjes of manuele uploads meer nodig.  

## ℹ️ Debug & controle
- ChatGPT kijkt **altijd rechtstreeks in de laatste versie van de `main` branch** op GitHub.  
- Na wijzigingen: **Cmd+Option+S** gebruiken zodat alles meteen up-to-date is.  

---

## ⚙️ Omgeving
- **Stack:** Python 3.12 · Django 5.0.6 · SQLite  
- **Taal & tijdzone:** `LANG=nl-be`, `TIME_ZONE=Europe/Brussels`  
- **Runtime:** Docker Compose met services:
  - `web` → Django devserver (http://localhost:8000)  
  - `css` (optioneel; kan herstarten, niet blokkerend)

## 📂 Belangrijkste paden
- **Host (VS Code):** `~/spiegelven-login/`  
- **Container (code-root):** `/app`  
- **Django project:** `/app/app` (settings/urls/wsgi)  
- **App “core”:** `/app/core`  
- **Imports (CSV):** `/app/import/`  ← **altijd dit pad gebruiken**  
- **SQLite DB:** `/app/db.sqlite3`  
- **Admin template overrides:**  
  - Factuur preview → `/app/core/templates/admin/invoice_preview.html`  
  - Member change-form (knop) → `/app/core/templates/admin/core/member/change_form.html`  
- **Backups (code/db):** `/app/backup/<YYYYmmdd-HHMMSS>/`

---

## ▶️ Starten, logs, checks
```bash
docker compose up -d
docker compose restart web
docker compose ps
docker compose logs --tail=200 web
docker compose exec -T web python manage.py check
docker compose exec -it web bash


🧾 Factuur-preview in admin
	•	URLs:
	•	/admin/invoice/preview/<member_id>/<year>/
	•	/admin/invoice/preview/<member_id>/  → automatisch volgend jaar
	•	View: core/invoice_views.py
	•	Template: core/templates/admin/invoice_preview.html
	•	Knop op Member change-form: “Preview factuur (volgend jaar)”

Waarom soms geen lijnen?
	1.	Geen PricingRule match voor dat lid/jaar.
	2.	YearPricing ontbreekt voor een code.
	3.	Asset-lijn verwacht, maar lid heeft geen bijpassende asset.

⸻

🧩 Admin – Members & Assets
	•	Members lijst: kolommen = Last Name, First Name, GSM, Leeftijd (computed), Course (CC/P3), Active, Email.
Zoekvelden: Last Name, First Name, Leeftijd, Course.
	•	Assets (types & labels)
	•	locker → VST_KAST (Kast)
	•	trolley_locker → KAR_KLN (Kar-kast)
	•	e_trolley_locker → KAR_ELEC (E-kar-kast)

⸻

📥 CSV-imports (hoe te verwerken)

Zorg dat je CSV’s in de container staan onder /app/import/.

Member assets — kolommen:
member_external.id, asset_type, identifier, active, released_on

Commands:
docker compose exec -T web python manage.py import_member_assets_csv /app/import/member_assets.csv
docker compose exec -T web python manage.py import_member_assets_csv /app/import/member_assets.csv --dry-run

Member courses — kolommen:
external_id, course   # course = CC of P3

Commands:
docker compose exec -T web python manage.py import_member_courses_csv /app/import/member_courses.csv
docker compose exec -T web python manage.py import_member_courses_csv /app/import/member_courses.csv --dry-run
Imports overschrijven bestaande waarden (bewuste keuze).

💾 Backups (DB + broncode)
TS=$(date +%Y%m%d-%H%M%S)
docker compose exec -T web sh -lc "mkdir -p /app/backup/$TS && cp -a /app/db.sqlite3 /app/backup/$TS/ || true"
docker compose exec -T web sh -lc "tar -czf /app/backup/$TS/source.tar.gz -C /app app core manage.py"
docker compose exec -T web sh -lc "ls -lh /app/backup/$TS"


🧠 Bekende valkuilen
	•	Heredoc in bash voor Django templates: gebruik <<'EOF' (gequote) zodat {% ... %} niet breekt.
	•	Admin aanpassingen: altijd even python manage.py check.
	•	Static in template: {% load static %} + href="{% static "admin/css/base.css" %}".
	•	/app/import/: gebruik altijd dit pad bij imports (niet /app/app/...).

⸻

🧭 Praktisch
	•	Snapshot: Cmd+Option+S in VS Code → commit & push naar main.
	•	README clean-up: Cmd+Option+C (VS Code task) om dubbele secties te verwijderen.
	•	Branch: we werken op main; ChatGPT controleert in GitHub steeds deze branch.

---

## Optie 2: in VS Code editor (geen terminal nodig)
- Open je project in VS Code → maak/ open `README.md` → plak dezelfde inhoud → **Save**.  
- Druk **Cmd+Option+S** (jouw snapshot-task) → staat meteen in GitHub.

---

## Optie 3: terminal, maar zonder “vastlopen”
Als je per se de terminal wil gebruiken zónder dat de shell blijft wachten:

1) **Schrijf bestand met heredoc** (plak dit *in één keer*, inclusief de laatste `EOF`-regel):
```bash
cat > README.md <<'EOF'
# Spiegelven-Fakturatie
... (dezelfde inhoud als hierboven) ...
## 🧭 Praktisch
- **Snapshot**: **Cmd+Option+S** in VS Code → commit & push naar `main`.  
- **README clean-up**: **Cmd+Option+C** (VS Code task) om dubbele secties te verwijderen.  
- **Branch**: we werken op **`main`**; ChatGPT controleert in GitHub steeds deze branch.  
EOF

	2.	Dán pas apart uitvoeren:
git add README.md
git commit -m "docs: add comprehensive README"
git push

Belangrijk: plak nooit extra git-commando’s achter dezelfde cat … <<'EOF'. Alles na die regel wordt als tekst in het bestand geschreven totdat EOF komt.
