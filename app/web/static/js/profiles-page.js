(function () {
  function isTruthy(value) {
    if (!value) return false;
    var normalized = String(value).toLowerCase();
    return normalized === "1" || normalized === "true" || normalized === "yes" || normalized === "on";
  }

  function setupUpscaleProviderToggle(container) {
    var selects = container.querySelectorAll("[data-upscale-provider-select]");
    selects.forEach(function (select) {
      var modelRowId = select.getAttribute("data-local-models-field");
      if (!modelRowId) return;

      function update() {
        var row = document.getElementById(modelRowId);
        if (!row) return;
        if (select.value === "local") {
          row.classList.remove("hidden");
        } else {
          row.classList.add("hidden");
        }
      }

      select.addEventListener("change", update);
      update();
    });
  }

  window.addEventListener("DOMContentLoaded", function () {
    var root = document.querySelector("[data-profiles-page]");
    if (!root) return;

    var openCreate = root.getAttribute("data-open-create");
    var openEditId = root.getAttribute("data-open-edit-id");

    if (isTruthy(openCreate)) {
      var createDialog = document.getElementById("create-profile-dialog");
      if (createDialog) {
        createDialog.showModal();
      }
    }

    if (openEditId) {
      var editDialog = document.getElementById("edit-profile-dialog-" + openEditId);
      if (editDialog) {
        editDialog.showModal();
      }
    }

    setupUpscaleProviderToggle(document);

    document.querySelectorAll("dialog").forEach(function (dialog) {
      dialog.addEventListener("open", function () {
        setupUpscaleProviderToggle(dialog);
      });
    });
  });
})();