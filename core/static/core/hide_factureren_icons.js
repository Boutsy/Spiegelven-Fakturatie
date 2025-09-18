document.addEventListener("DOMContentLoaded", function () {
  var sel = document.getElementById("id_factureren_via");
  if (!sel) return;
  var wrapper = sel.closest(".related-widget-wrapper");
  if (!wrapper) return;
  wrapper.querySelectorAll("a.related-widget-wrapper-link").forEach(function(a){
    a.style.display = "none";
  });
});
