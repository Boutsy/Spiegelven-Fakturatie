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

  // Slim parsen: EU ("1.234,56") en US ("1750.00")
  function parseNum(s) {
    if (s === null || s === undefined) return NaN;
    let t = String(s).trim();
    if (t === "") return NaN;

    t = t.replace(/\s|\u00A0|\u202F/g, "");
    const hasComma = t.includes(",");
    const hasDot   = t.includes(".");

    if (hasComma && hasDot) {
      t = t.replace(/\./g, "").replace(",", ".");
    } else if (hasComma) {
      t = t.replace(",", ".");
    } else {
      const dots = (t.match(/\./g) || []).length;
      if (dots > 1) {
        const last = t.lastIndexOf(".");
        t = t.slice(0, last).replace(/\./g, "") + t.slice(last);
      }
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
  function setNumericText(input, num, digits = 2) {
    if (!input) return;
    const n = Number(num);
    if (!isFinite(n)) return;
    input.value = fmtNL(n, digits);
    triggerChange(input);
  }

  // ---------- delete helpers ----------
  function inlineGroupOf(node) {
    return node.closest(".inline-group") || document;
  }
  function decrementTotalForms(row) {
    const group = inlineGroupOf(row);
    const total = group.querySelector('input[id$="-TOTAL_FORMS"]');
    if (total) {
      const n = parseInt(total.value || "0", 10);
      if (n > 0) total.value = String(n - 1);
    }
  }
  function removeUnsavedRow(row) {
    decrementTotalForms(row);
    (row.closest("tr") || row).remove();
  }

  // --- header “VERWIJDEREN?” verbergen ---
  function hideDeleteHeader(root) {
    root.querySelectorAll(".inline-group table thead th").forEach((th) => {
      const cls = (th.className || "").toLowerCase();
      const txt = (th.textContent || "").toLowerCase();
      const hasDeleteInput = !!th.querySelector('input[name$="-DELETE"]');
      if (cls.includes("delete") || cls.includes("field-delete") || txt.includes("verwijder") || txt.includes("delete") || hasDeleteInput) {
        th.style.display = "none";
      }
    });
  }

  // --- één ✖ naast Tot. INC. per rij (werkt voor bestaande én nieuwe rijen) ---
  function moveDeleteNextToTotal(row) {
    const totInc =
      row.querySelector('td.field-total_incl_display') ||
      row.querySelector('td[class*="total_incl_display"]');
    if (!totInc) return;

    // voorkom 2x / 3x
    totInc.querySelectorAll(".line-del-btn").forEach(n => n.remove());

    // bron zoeken
    const delCell =
      row.querySelector('td.delete, td.field-DELETE, td[class*="DELETE"]') || row;
    const delCheckbox = delCell.querySelector('input[type="checkbox"][name$="-DELETE"]');
    const delLinkInCell = delCell.querySelector("a.inline-deletelink, a, button");
    const delLinkAnywhere = row.querySelector("a.inline-deletelink");

    let btn = null;

    if (delLinkAnywhere || delLinkInCell) {
      // verplaats ingebouwde verwijderlink
      btn = (delLinkAnywhere || delLinkInCell);
      btn.classList.add("line-del-btn");
    } else if (delCheckbox) {
      // bestaande (opgeslagen) rij: koppel aan DELETE-checkbox
      btn = document.createElement("a");
      btn.href = "#";
      btn.className = "line-del-btn";
      btn.title = "Verwijder deze lijn";
      btn.textContent = "✖";
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        delCheckbox.checked = true;
        delCheckbox.dispatchEvent(new Event("change", { bubbles: true }));
        (row.closest("tr") || row).style.display = "none";
      });
    } else {
      // NIEUWE (nog niet opgeslagen) rij zonder delete-link: maak eigen ✖ + corrigeer TOTAL_FORMS
      btn = document.createElement("a");
      btn.href = "#";
      btn.className = "line-del-btn";
      btn.title = "Verwijder deze (nieuwe) lijn";
      btn.textContent = "✖";
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        removeUnsavedRow(row);
      });
    }

    if (btn) {
      const input = totInc.querySelector("input");
      totInc.style.display = "flex";
      totInc.style.alignItems = "center";
      totInc.style.gap = "0.4ch";
      if (input) input.insertAdjacentElement("afterend", btn);
      else totInc.appendChild(btn);
    }

    // verberg originele delete-cel (kolom neemt dan geen ruimte in)
    const origDelCell =
      row.querySelector('td.delete, td.field-DELETE, td[class*="DELETE"]');
    if (origDelCell) origDelCell.style.display = "none";
  }

  // Link-tekst aanpassen
  function retitleAddRow(root=document) {
    root.querySelectorAll(".inline-group .add-row a").forEach(a => {
      a.textContent = "+ Nog een factuurlijn toevoegen";
    });
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
    ["quantity", "unit_price_excl", "vat_rate"].forEach((suffix) => {
      const el = qInRow(row, suffix);
      if (!el) return;
      el.addEventListener("input",  () => computeRowTotals(row));
      el.addEventListener("change", () => computeRowTotals(row));
    });

    const upEl = qInRow(row, "unit_price_excl");
    if (upEl) {
      upEl.addEventListener("blur", () => {
        const n = parseNum(upEl.value);
        upEl.value = isFinite(n) ? fmtNL(n, 2) : "";
        triggerChange(upEl);
      });
    }

    computeRowTotals(row);
    moveDeleteNextToTotal(row);
  }

  // ---------- core ----------
  function prefillRow(row, prod, force) {
    if (!row || !prod) return;

    const dsc = qInRow(row, "description");
    const qty = qInRow(row, "quantity");
    const up  = qInRow(row, "unit_price_excl");
    const vat = qInRow(row, "vat_rate");

    if (dsc && (force || dsc.value.trim() === "")) {
      dsc.value = prod.name || "";
      triggerChange(dsc);
    }
    if (qty && (force || String(qty.value || "").trim() === "")) {
      qty.value = "1";
      triggerChange(qty);
    }
    if (up) {
      const pv = parseNum(prod.unit_price_excl);
      if (isFinite(pv) && (force || isEmptyOrZero(up.value))) {
        setNumericText(up, pv, 2);
      }
    }
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

    // bestaande + nieuwe rijen
    root.querySelectorAll('tr.form-row, .inline-related').forEach(row => {
      // default aantal
      const qty = qInRow(row, "quantity");
      if (qty && (!qty.value || String(qty.value).trim() === "")) {
        qty.value = "1";
        triggerChange(qty);
      }
      wireTotals(row);
    });

    // header verbergen + plus-link hernoemen
    root.querySelectorAll(".inline-group table").forEach(tbl => hideDeleteHeader(tbl));
    retitleAddRow(root);
  }

  function initWithCatalog(catalog) {
    window._PRODUCTS_CATALOG = catalog;
    wireContainer(document, catalog);

    // wanneer een nieuwe rij wordt toegevoegd
    document.addEventListener("formset:added", (e) => {
      const scope = e.target || document;
      wireContainer(scope, catalog);
    });

    // popup product picker (Django related-lookup)
    window.addEventListener("message", (ev) => {
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