(() => {
  const CATALOG_URL = "/admin/products-catalog.json";

  function isBlank(v) {
    return v === null || v === undefined || String(v).trim() === "";
  }
  function isZero(v) {
    if (isBlank(v)) return true;
    const t = String(v).trim().replace(",", "."); // tolerate comma
    if (t === "") return true;
    const n = Number(t);
    return !isFinite(n) || n === 0;
  }
  function findRow(el) {
    return el.closest("tr") || el.closest(".inline-related") || document;
  }
  function qInRow(row, suffix) {
    return row.querySelector('input[name$="' + suffix + '"]');
  }
  function prefillRow(row, prod) {
    if (!row || !prod) return;
    const dsc = qInRow(row, "description");
    const up  = qInRow(row, "unit_price_excl");
    const vat = qInRow(row, "vat_rate");

    if (dsc && isBlank(dsc.value)) {
      dsc.value = prod.name || "";
      dsc.dispatchEvent(new Event("input", {bubbles:true}));
      dsc.dispatchEvent(new Event("change", {bubbles:true}));
    }
    if (up && (isBlank(up.value) || isZero(up.value))) {
      // Always use dot as decimal separator for HTML inputs
      const price = String(prod.unit_price_excl ?? "").replace(",", ".");
      if (price !== "") {
        up.value = price;
        up.dispatchEvent(new Event("input", {bubbles:true}));
        up.dispatchEvent(new Event("change", {bubbles:true}));
      }
    }
    if (vat) {
      // Always override VAT when a product is chosen (user can change afterwards)
      const vr = prod.vat_rate;
      const val = (vr === null || vr === undefined) ? "" : String(vr).replace(",", ".");
      if (val !== "") {
        // Use plain integer/decimal (no commas)
        vat.value = val;
        vat.dispatchEvent(new Event("input", {bubbles:true}));
        vat.dispatchEvent(new Event("change", {bubbles:true}));
      }
    }
  }
  function handleProductChange(sel, catalog) {
    const key = String(sel.value || "");
    const prod = catalog[key];
    const row  = findRow(sel);
    if (prod) prefillRow(row, prod);
  }
  function wireSelect(sel, catalog) {
    sel.addEventListener("change", () => handleProductChange(sel, catalog));
    const chosen = String(sel.value || "");
    if (chosen) handleProductChange(sel, catalog);
  }
  function wireAll(catalog) {
    document.querySelectorAll('select[name$="-product"]').forEach(sel => wireSelect(sel, catalog));

    // Observe new inline rows
    const observer = new MutationObserver(muts => {
      muts.forEach(m => {
        m.addedNodes && m.addedNodes.forEach(node => {
          if (!(node instanceof Element)) return;
          node.querySelectorAll && node.querySelectorAll('select[name$="-product"]').forEach(sel => wireSelect(sel, catalog));
          // Also if the node itself is a select
          if (node.matches && node.matches('select[name$="-product"]')) wireSelect(node, catalog);
        });
      });
    });
    observer.observe(document.body, {childList:true, subtree:true});

    // Support selection from related-object popup
    window.addEventListener("message", ev => {
      const d = ev && ev.data;
      if (!d || !d.action || !d.value || !d.relatedField) return;
      // Expected {action: "select", value: "<pk>", relatedField: "id_lines-0-product"}
      const el = document.getElementById(String(d.relatedField));
      if (el && el.tagName === "SELECT") {
        el.value = d.value;
        el.dispatchEvent(new Event("change", {bubbles:true}));
      }
    });
  }
  function init() {
    fetch(CATALOG_URL, {credentials:"same-origin"})
      .then(r => r.json())
      .then(catalog => { window._PRODUCTS_CATALOG = catalog; wireAll(catalog); })
      .catch(() => {});
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
