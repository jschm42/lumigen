(function () {
  var dialog = document.querySelector("[data-asset-detail-dialog]");
  var content = document.querySelector("[data-asset-detail-dialog-content]");
  if (!dialog || !content) return;

  var loadingMarkup = "<div class=\"rounded-xl border border-white/10 bg-white/5 px-4 py-8 text-center text-sm text-slate-300\">Loading asset details...</div>";

  function closeDialog() {
    if (dialog.open) {
      dialog.close();
    }
    dialog.removeAttribute("aria-busy");
  }

  function openDialogForPendingLoad() {
    dialog.setAttribute("aria-busy", "true");
    if (!dialog.open) {
      dialog.showModal();
    }
    content.innerHTML = loadingMarkup;
  }

  function wireCloseButton() {
    var closeButton = dialog.querySelector("[data-asset-detail-close]");
    if (!closeButton || closeButton.dataset.bound === "1") return;
    closeButton.dataset.bound = "1";
    closeButton.addEventListener("click", function () {
      closeDialog();
    });
  }

  wireCloseButton();

  dialog.addEventListener("click", function (event) {
    var rect = dialog.getBoundingClientRect();
    var isOutside =
      event.clientX < rect.left ||
      event.clientX > rect.right ||
      event.clientY < rect.top ||
      event.clientY > rect.bottom;
    if (isOutside) {
      closeDialog();
    }
  });

  document.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-asset-detail-trigger]");
    if (!trigger) return;
    if (event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

    var target = trigger.getAttribute("hx-target") || "";
    if (target !== "#asset-detail-dialog-content") return;

    openDialogForPendingLoad();
  }, true);

  document.body.addEventListener("htmx:beforeRequest", function (event) {
    if (!event.detail || event.detail.target !== content) return;
    if (!dialog.open) {
      openDialogForPendingLoad();
      return;
    }
    dialog.setAttribute("aria-busy", "true");
  });

  document.body.addEventListener("htmx:afterSwap", function (event) {
    if (event.detail && event.detail.target === content) {
      wireCloseButton();
      dialog.removeAttribute("aria-busy");
      if (!dialog.open) {
        requestAnimationFrame(function () {
          dialog.showModal();
        });
      }
    }
  });

  document.body.addEventListener("htmx:responseError", function (event) {
    if (!event.detail || event.detail.target !== content) return;
    dialog.removeAttribute("aria-busy");
  });

  document.body.addEventListener("htmx:sendError", function (event) {
    if (!event.detail || event.detail.target !== content) return;
    dialog.removeAttribute("aria-busy");
  });
})();
