(function() {
  function ready(fn){ if(document.readyState !== 'loading'){ fn(); } else { document.addEventListener('DOMContentLoaded', fn); } }

  function rowElems(row){
    return {
      product:   row.querySelector("select[id$='-product']"),
      descr:     row.querySelector("input[id$='-description']"),
      qty:       row.querySelector("input[id$='-quantity']"),
      unitPrice: row.querySelector("input[id$='-unit_price_excl']"),
      vat:       row.querySelector("input[id$='-vat_rate']")
    };
  }

  async function fillFromProduct(row){
    const els = rowElems(row);
    if(!els.product || !els.product.value){ return; }
    const id = els.product.value;
    try{
      const resp = await fetch(`/admin/core/product_defaults/${id}/`, {credentials:'same-origin'});
      if(!resp.ok) return;
      const data = await resp.json();
      if(els.descr && (!els.descr.value || els.descr.value.trim()==="")){
        els.descr.value = data.name || "";
      }
      if(els.unitPrice && (!els.unitPrice.value || parseFloat(els.unitPrice.value)===0)){
        els.unitPrice.value = (data.default_price_excl || 0).toString();
      }
      if(els.vat && (!els.vat.value || els.vat.value==="")){
        els.vat.value = (data.default_vat_rate || 0).toString();
      }
      if(els.qty && (!els.qty.value || parseFloat(els.qty.value)===0)){
        els.qty.value = "1";
      }
    }catch(e){
      console.warn("Kon product defaults niet laden:", e);
    }
  }

  function wireRow(row){
    const els = rowElems(row);
    if(els.product){
      els.product.addEventListener('change', function(){ fillFromProduct(row); });
    }
  }

  function scanAllRows(){
    document.querySelectorAll("tr.dynamic-invoiceline_set").forEach(wireRow);
  }

  ready(function(){
    scanAllRows();

    // Her-wire als er nieuwe inline rijen bijkomen
    document.body.addEventListener('formset:added', function(e){
      const row = e.target.closest("tr");
      if(row) wireRow(row);
    });

    // Init: meteen invullen waar al een product staat
    document.querySelectorAll("tr.dynamic-invoiceline_set").forEach(fillFromProduct);
  });
})();
