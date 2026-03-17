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

  function setupProviderToggle(container) {
    var forms = container.querySelectorAll("[data-profile-form]");
    forms.forEach(function (form) {
      var modelSelect = form.querySelector("[data-profile-model-select]");
      if (!modelSelect) return;

      var dimensionsEl = form.querySelector("[data-profile-dimensions]");
      var openrouterEl = form.querySelector("[data-profile-openrouter]");
      var falEl = form.querySelector("[data-profile-fal]");

      function update() {
        var selectedOption = modelSelect.options[modelSelect.selectedIndex];
        var provider = selectedOption ? (selectedOption.getAttribute("data-provider") || "").toLowerCase() : "";

        if (provider === "fal") {
          if (dimensionsEl) dimensionsEl.classList.add("hidden");
          if (openrouterEl) openrouterEl.classList.add("hidden");
          if (falEl) falEl.classList.remove("hidden");
        } else if (provider === "openrouter") {
          if (dimensionsEl) dimensionsEl.classList.add("hidden");
          if (openrouterEl) openrouterEl.classList.remove("hidden");
          if (falEl) falEl.classList.add("hidden");
        } else {
          if (dimensionsEl) dimensionsEl.classList.remove("hidden");
          if (openrouterEl) openrouterEl.classList.add("hidden");
          if (falEl) falEl.classList.add("hidden");
        }
      }

      modelSelect.addEventListener("change", update);
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
    setupProviderToggle(document);

    document.querySelectorAll("dialog").forEach(function (dialog) {
      dialog.addEventListener("open", function () {
        setupUpscaleProviderToggle(dialog);
        setupProviderToggle(dialog);
      });
    });
  });
})();
