(function () {
  var popovers = Array.from(document.querySelectorAll("[data-category-popover]"));
  if (!popovers.length) return;

  function closeAll(exceptRoot) {
    popovers.forEach(function (root) {
      if (exceptRoot && root === exceptRoot) return;
      var toggle = root.querySelector("[data-category-popover-toggle]");
      var panel = root.querySelector("[data-category-popover-panel]");
      if (!toggle || !panel) return;
      panel.classList.add("hidden");
      toggle.setAttribute("aria-expanded", "false");
    });
  }

  popovers.forEach(function (root) {
    var toggle = root.querySelector("[data-category-popover-toggle]");
    var panel = root.querySelector("[data-category-popover-panel]");
    if (!toggle || !panel) return;

    toggle.addEventListener("click", function (event) {
      event.preventDefault();
      var willOpen = panel.classList.contains("hidden");
      closeAll(root);
      panel.classList.toggle("hidden", !willOpen);
      toggle.setAttribute("aria-expanded", willOpen ? "true" : "false");
    });
  });

  document.addEventListener("click", function (event) {
    var clickedInside = popovers.some(function (root) {
      return root.contains(event.target);
    });
    if (!clickedInside) {
      closeAll();
    }
  });
})();

(function () {
  var STORAGE_KEY = "lumigen_gallery_thumb_size";
  var form = document.querySelector('form[action="/gallery"]');
  if (!form) return;

  var urlParams = new URLSearchParams(window.location.search);
  var hasThumbParam = urlParams.has("thumb_size");

  if (!hasThumbParam) {
    try {
      var savedSize = localStorage.getItem(STORAGE_KEY);
      if (savedSize && ["sm", "md", "lg"].indexOf(savedSize) !== -1) {
        var separator = window.location.search ? "&" : "?";
        window.location.href = window.location.pathname + window.location.search + separator + "thumb_size=" + savedSize;
        return;
      }
    } catch (e) {}
  } else {
    try {
      var currentSize = urlParams.get("thumb_size");
      if (currentSize && ["sm", "md", "lg"].indexOf(currentSize) !== -1) {
        localStorage.setItem(STORAGE_KEY, currentSize);
      }
    } catch (e) {}
  }

  document.querySelectorAll("[data-gallery-thumb-size]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var size = btn.getAttribute("data-gallery-thumb-size");
      try {
        localStorage.setItem(STORAGE_KEY, size);
      } catch (e) {}
    });
  });
})();