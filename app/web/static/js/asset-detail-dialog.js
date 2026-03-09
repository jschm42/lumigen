(function () {
  var dialog = document.querySelector("[data-asset-detail-dialog]");
  var content = document.querySelector("[data-asset-detail-dialog-content]");
  if (!dialog || !content) return;

  function closeDialog() {
    if (dialog.open) {
      dialog.close();
    }
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

  document.body.addEventListener("htmx:afterSwap", function (event) {
    if (event.detail && event.detail.target === content) {
      wireCloseButton();
      if (!dialog.open) {
        dialog.showModal();
      }
    }
  });
})();
