/* Len Data Governance — menu "Visualisasi" di sidebar kiri OpenMetadata.
 * Disisipkan oleh gateway (nginx sub_filter) bersama leno.css. Membuka dashboard Gold (Superset)
 * di /visualisasi/ pada origin yang sama (:8585) — tidak ada port atau aplikasi terpisah untuk pengguna.
 * Item dibuat dengan menyalin item menu bawaan agar gaya (ikon, hover, mode ciut) tetap sama. */
(function () {
  "use strict";
  var ID = "len-menu-visualisasi";
  var HREF = "/visualisasi/dashboard/list/";
  var ICON = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" ' +
    'aria-hidden="true"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>';

  function build(menu) {
    var tpl = menu.querySelector("li.ant-menu-item");
    if (!tpl) return null;
    var li = tpl.cloneNode(true);           // tanpa handler React: klik ditangani sendiri di bawah
    li.id = ID;
    li.classList.remove("ant-menu-item-selected", "ant-menu-item-active");
    li.removeAttribute("data-menu-id");
    li.setAttribute("data-testid", "app-bar-item-visualisasi");
    li.setAttribute("title", "Visualisasi data Gold (Trino lakehouse)");
    var icon = li.querySelector(".ant-menu-item-icon, .anticon, svg");
    if (icon) {
      var span = document.createElement("span");
      span.className = "ant-menu-item-icon anticon";
      span.setAttribute("role", "img");
      span.innerHTML = ICON;
      icon.replaceWith(span);
    }
    var label = li.querySelector(".ant-menu-title-content");
    if (label) {
      label.innerHTML = "";
      var a = document.createElement("a");
      a.href = HREF;
      a.textContent = "Visualisasi";
      a.style.color = "inherit";
      label.appendChild(a);
    }
    li.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      window.location.assign(HREF);
    }, true);
    return li;
  }

  function ensure() {
    if (document.getElementById(ID)) return;
    var menu = document.querySelector(".left-sidebar-menu.ant-menu, .left-sidebar-layout ul.ant-menu");
    if (!menu) return;
    var li = build(menu);
    if (li) menu.appendChild(li);
  }

  new MutationObserver(ensure).observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener("DOMContentLoaded", ensure);
})();
