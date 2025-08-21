/* SV v3 — Autofill prijs, btw en omschrijving bij productkeuze in factuurregels (Django admin inline) */
(function () {
  console.debug("SV: invoice_line.js v3 geladen");

  function rowOf(el) { return el ? el.closest("tr") : null; }
  function fieldBySuffix(row, suffix) {
    return row ? row.querySelector(`input[name$="${suffix}"], select[name$="${suffix}"], textarea[name$="${suffix}"]`) : null;
  }

  async function fetchProduct(pk) {
    const url = `/admin/core/product/${pk}/json/`;
    try {
      const res = await fetch(url, { credentials: "same-origin", headers: { "Accept": "application/json" } });
      if (!res.ok) { console.warn("SV: fetch product NOK", pk, res.status); return null; }
      return await res.json();
    } catch (e) {
      console.warn("SV: fetch product error", e);
      return null;
    }
  }

  async function fillFromProduct(selectEl) {
    const pk = selectEl && selectEl.value;
    if (!pk) return;

    const row = rowOf(selectEl);
    const data = await fetchProduct(pk);
    if (!data) return;

    const price = fieldBySuffix(row, "-unit_price_excl");
    const vat   = fieldBySuffix(row, "-vat_rate");
    const desc  = fieldBySuffix(row, "-description");

    if (price && (!price.value || Number(price.value) === 0)) {
      price.value = data.default_price_excl || "";
      price.dispatchEvent(new Event("input", { bubbles: true }));
    }
    if (vat && (!vat.value || Number(vat.value) === 0)) {
      vat.value = data.default_vat_rate || "";
      vat.dispatchEvent(new Event("input", { bubbles: true }));
    }
    if (desc && (!desc.value || desc.value.trim() === "")) {
      desc.value = data.name || "";
      desc.dispatchEvent(new Event("input", { bubbles: true }));
    }
    console.debug("SV: autofilled", { pk, name: data.name });
  }

  function bindRow(row) {
    const sel = row.querySelector('select[name$="-product"]');
    if (sel && !sel.dataset.svBound) {
      sel.addEventListener("change", function (e) { fillFromProduct(e.target); });
      sel.dataset.svBound = "1";
    }
  }

  function scanAllRows() {
    document.querySelectorAll("tr.form-row").forEach(bindRow);
  }

  document.addEventListener("DOMContentLoaded", scanAllRows);
  window.addEventListener("load", function () {
    scanAllRows();
    // Prefill voor al gekozen producten bij laden
    document.querySelectorAll('select[name$="-product"]').forEach(function (sel) {
      if (sel.value) fillFromProduct(sel);
    });
  });

  // Als er dynamisch regels bijkomen, opnieuw binden
  document.body.addEventListener("click", function (e) {
    if (e.target && e.target.matches(".add-row a, .add-row button")) {
      setTimeout(scanAllRows, 0);
    }
  });
})();
