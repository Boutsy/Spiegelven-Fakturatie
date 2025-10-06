(() => {
  const CATALOG_URL = "/admin/products-catalog.json";

  // --- helpers ------------------------------------------------------------
  function toFixedDot(n, digits) {
    if (n === null || n === undefined || isNaN(n)) return "";
    return Number(n).toFixed(digits); // "1750.00"
  }
  function toFixedComma(n, digits) {
    const s = toFixedDot(n, digits);
    return s ? s.replace(".", ",") : s; // "1750,00"
  }
  function parseNum(s) {
    if (s === null || s === undefined) return NaN;
    const t = String(s).trim().replace(",", ".");
    if (t === "") return NaN;
    return Number(t);
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

  // Schrijf numeriek:
  // - number inputs -> valueAsNumber
  // - text inputs (gelokaliseerd) -> schrijf met KOMMA
  function setNumeric(input, num, digits = 2) {
    if (!input) return;
    const n = Number(num);
    if (!isFinite(n)) return;

    const isNumber = (String(input.type || "").toLowerCase() === "number");

    if (isNumber && "valueAsNumber" in input) {
      input.step ||= "0.01";
      input.valueAsNumber = n;
    } else {
      input.setAttribute("inputmode", "decimal");
      input.value = toFixedComma(n, digits);
    }
    triggerChange(input);
  }

  // --- totalen per rij ----------------------------------------------------
  function computeRowTotals(row) {
    const qtyEl = qInRow(row, "quantity");
    const upEl  = qInRow(row, "unit_price_excl");
    const vatEl = qInRow(row, "vat_rate");
    const exEl  = qInRow(row, "total_excl_display");
    const incEl = qInRow(row, "total_incl_display");

    const q   = parseNum(qtyEl && qtyEl.value);
    const up  = parseNum(upEl  && upEl.value);
    const vat = parseNum(vatEl && (vatEl.value ?? vatEl.textContent));

    if (!isFinite(q) || !isFinite(up)) {
      if (exEl)  exEl.value  = "";
      if (incEl) incEl.value = "";
      return;
    }
    const ex  = q * up;
    const vr  = isFinite(vat) ? vat : 21;
    const inc = ex * (1 + (vr / 100));

    if (exEl)  exEl.value  = toFixedComma(ex, 2);
    if (incEl) incEl.value = toFixedComma(inc, 2);
  }

  function wireTotals(row) {
    ["quantity", "unit_price_excl", "vat_rate"].forEach(suffix => {
      const el = qInRow(row, suffix);
      if (!el) return;
      el.addEventListener("input",  () => computeRowTotals(row));
      el.addEventListener("change", () => computeRowTotals(row));
    });
    // initial
    computeRowTotals(row);
  }

  // --- core ---------------------------------------------------------------
  // force=false => alleen invullen als leeg/0 (initial load)
  // force=true  => altijd overschrijven (bij productwijziging)
  function prefillRow(row, prod, force) {
    if (!row || !prod) return;

    const dsc = qInRow(row, "description");
    const up  = qInRow(row, "unit_price_excl");
    const vat = qInRow(row, "vat_rate");

    // Omschrijving
    if (dsc && (force || dsc.value.trim() === "")) {
      dsc.value = prod.name || "";
      triggerChange(dsc);
    }

    // Eenheidsprijs excl
    if (up) {
      const pv = parseNum(prod.unit_price_excl);
      if (isFinite(pv) && (force || isEmptyOrZero(up.value))) {
        setNumeric(up, pv, 2);
      }
    }

    // BTW (werkt voor input én select)
    if (vat) {
      const vv  = parseNum(prod.vat_rate);
      const val = isFinite(vv) ? String(Math.trunc(vv)) : "21";
      if (force || String(vat.value || "").trim() === "" || val !== String(vat.value)) {
        vat.value = val;
        triggerChange(vat);
      }
    }

    // Na prefill: totalen herberekenen
    computeRowTotals(row);
  }

  function handleSelectChange(sel, catalog, force) {
    const val = String(sel.value || "");
    const prod = catalog[val];
    const row = findRow(sel);
    if (prod) prefillRow(row, prod, force);
  }

  function wireSelect(sel, catalog) {
    // bij wijziging altijd overschrijven
    sel.addEventListener("change", () => handleSelectChange(sel, catalog, true));
    // initial load: alleen invullen als leeg/0
    const chosen = String(sel.value || "");
    if (chosen && catalog[chosen]) handleSelectChange(sel, catalog, false);

    // totals live koppelen voor deze rij
    const row = findRow(sel);
    wireTotals(row);
  }

  function wireContainer(root, catalog) {
    root.querySelectorAll('select[id$="-product"]').forEach(sel => wireSelect(sel, catalog));
  }

  function initWithCatalog(catalog) {
    window._PRODUCTS_CATALOG = catalog;
    wireContainer(document, catalog);

    // nieuwe inline-rijen
    document.addEventListener("formset:added", e => {
      wireContainer(e.target || document, catalog);
    });

    // popup product picker (Django related-lookup)
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