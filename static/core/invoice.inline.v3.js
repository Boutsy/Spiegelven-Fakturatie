(() => {
  const CATALOG_URL = "/admin/products-catalog.json";

  // ---------- helpers ----------
  function fmtNL(n, digits = 2) {
    if (n === null || n === undefined || isNaN(n)) return "";
    return new Intl.NumberFormat("nl-BE", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits
    }).format(Number(n));
  }
  function normalizeNumericString(s) {
    if (s === null || s === undefined) return "";
    // verwijder duizendpunten, vervang komma door punt
    return String(s).trim().replace(/\./g, "").replace(",", ".");
  }
  // vervangt normalizeNumericString() en parseNum()
  // Slim parsen: EU ("1.234,56") en US ("1750.00")
  function parseNum(s) {
    if (s === null || s === undefined) return NaN;
    let t = String(s).trim();
    if (t === "") return NaN;

    // verwijder spaties / non-breaking / smalle spaties
    t = t.replace(/\s|\u00A0|\u202F/g, "");

    const hasComma = t.includes(",");
    const hasDot   = t.includes(".");

    if (hasComma && hasDot) {
      // "1.234,56" -> "1234.56"
      t = t.replace(/\./g, "").replace(",", ".");
    } else if (hasComma) {
      // "1234,56" -> "1234.56"
      t = t.replace(",", ".");
    } else {
      // Alleen punten of niets: laat één punt als decimaal
      const dots = (t.match(/\./g) || []).length;
      if (dots > 1) {
        const last = t.lastIndexOf(".");
        t = t.slice(0, last).replace(/\./g, "") + t.slice(last);
      }
      // bij 0 of 1 punt: niets doen (bv. "1750.00" blijft zo)
    }

    const n = Number(t);
    return isFinite(n) ? n : NaN;
  }

  function isEmptyOrZero(v) {
    if (v === null || v === undefined) return true;
    const t = String(v).trim();
    if (t === "") return true;
    const n = parseNum(t);
    return !isFinite(n) || n === 0;
  }
  function findRow(el) {
    return el.closest("tr") || el.closest(".inline-related") || document;
  }
  function qInRow(row, nameSuffix) {
    return row.querySelector('input[name$="' + nameSuffix + '"], select[name$="' + nameSuffix + '"]');
  }
  function triggerChange(el) {
    if (!el) return;
    el.dispatchEvent(new Event("input",  { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }
  // schrijf geformatteerde tekst (met duizendpunt/komma) naar TEXT inputs
  function setNumericText(input, num, digits = 2) {
    if (!input) return;
    const n = Number(num);
    if (!isFinite(n)) return;
    input.value = fmtNL(n, digits);
    triggerChange(input);
  }

  // ---------- totalen per rij ----------
  function computeRowTotals(row) {
    const qtyEl = qInRow(row, "quantity");
    const upEl  = qInRow(row, "unit_price_excl");
    const vatEl = qInRow(row, "vat_rate");
    const exEl  = qInRow(row, "total_excl_display");
    const incEl = qInRow(row, "total_incl_display");

    const qRaw  = qtyEl ? (qtyEl.value ?? qtyEl.valueAsNumber ?? "") : "";
    const q     = parseNum(qRaw);
    const up    = parseNum(upEl && upEl.value);
    const vat   = parseNum(vatEl && (vatEl.value ?? vatEl.textContent));

    if (!isFinite(q) || !isFinite(up)) {
      if (exEl)  exEl.value  = "";
      if (incEl) incEl.value = "";
      return;
    }
    const ex  = q * up;
    const vr  = isFinite(vat) ? vat : 21;
    const inc = ex * (1 + (vr / 100));

    if (exEl)  exEl.value  = fmtNL(ex, 2);
    if (incEl) incEl.value = fmtNL(inc, 2);
  }

  function wireTotals(row) {
    ["quantity", "unit_price_excl", "vat_rate"].forEach(suffix => {
      const el = qInRow(row, suffix);
      if (!el) return;
      el.addEventListener("input",  () => computeRowTotals(row));
      el.addEventListener("change", () => computeRowTotals(row));
    });

    // >>> NIEUW: Prijs EX automatisch mooi maken bij verlaten veld
    const upEl = qInRow(row, "unit_price_excl");
    if (upEl) {
      upEl.addEventListener("blur", () => {
        const n = parseNum(upEl.value);
        upEl.value = isFinite(n) ? fmtNL(n, 2) : "";
        triggerChange(upEl);
      });
    }
    // <<<
    computeRowTotals(row);
  }

  // ---------- core ----------
  function prefillRow(row, prod, force) {
    if (!row || !prod) return;

    const dsc = qInRow(row, "description");
    const qty = qInRow(row, "quantity");          // number input
    const up  = qInRow(row, "unit_price_excl");   // text (gelokaliseerd)
    const vat = qInRow(row, "vat_rate");

    // Omschrijving
    if (dsc && (force || dsc.value.trim() === "")) {
      dsc.value = prod.name || "";
      triggerChange(dsc);
    }
    // Aantal (NOOIT met komma in number input schrijven)
    if (qty && (force || String(qty.value || "").trim() === "")) {
      // native spinner laten werken: integer 1
      qty.value = "1";
      triggerChange(qty);
    }
    // Eenheidsprijs excl (geformatteerde tekst)
    if (up) {
      const pv = parseNum(prod.unit_price_excl);
      if (isFinite(pv) && (force || isEmptyOrZero(up.value))) {
        setNumericText(up, pv, 2);
      }
    }
    // BTW
    if (vat) {
      const vv  = parseNum(prod.vat_rate);
      const val = isFinite(vv) ? String(Math.trunc(vv)) : "21";
      if (force || String(vat.value || "").trim() === "" || val !== String(vat.value)) {
        vat.value = val;
        triggerChange(vat);
      }
    }
    computeRowTotals(row);
  }

  function handleSelectChange(sel, catalog, force) {
    const val = String(sel.value || "");
    const prod = catalog[val];
    const row = findRow(sel);
    if (prod) prefillRow(row, prod, force);
  }

  function wireSelect(sel, catalog) {
    sel.addEventListener("change", () => handleSelectChange(sel, catalog, true));
    const chosen = String(sel.value || "");
    if (chosen && catalog[chosen]) handleSelectChange(sel, catalog, false);

    const row = findRow(sel);
    wireTotals(row);
  }

  function wireContainer(root, catalog) {
    // product selects
    root.querySelectorAll('select[id$="-product"]').forEach(sel => wireSelect(sel, catalog));

    // bestaande rijen zonder productkeuze: zorg dat Aantal niet leeg is (1)
    root.querySelectorAll('input[name$="quantity"]').forEach(inp => {
      if (!inp.value || String(inp.value).trim() === "") {
        inp.value = "1"; // integer (geen komma) voor number input
        triggerChange(inp);
      }
      const row = findRow(inp);
      wireTotals(row);
    });
  }

  function initWithCatalog(catalog) {
    window._PRODUCTS_CATALOG = catalog;
    wireContainer(document, catalog);

    document.addEventListener("formset:added", e => {
      wireContainer(e.target || document, catalog);
    });

    window.addEventListener("message", ev => {
      const d = ev && ev.data;
      if (!d || !d.relatedField || !d.value || !d.action) return;
      if (!String(d.relatedField).endsWith("-product")) return;
      const sel = document.getElementById(String(d.relatedField));
      if (sel) {
        sel.value = d.value;
        sel.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
  }

  function init() {
    fetch(CATALOG_URL, { credentials: "same-origin" })
      .then(r => r.json())
      .then(catalog => { initWithCatalog(catalog); })
      .catch(() => {});
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();