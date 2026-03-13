(function () {
  function toggleApiKeyField(prefix) {
    var checkbox = document.getElementById(prefix + "-use-custom-api-key");
    var field = document.getElementById(prefix + "-api-key-field");
    if (checkbox && field) {
      if (checkbox.checked) {
        field.classList.remove("hidden");
      } else {
        field.classList.add("hidden");
      }
    }
  }

  function updateProviderHint(selectEl) {
    var hintId = selectEl.getAttribute("data-provider-hint-target");
    if (!hintId) return;
    var hint = document.getElementById(hintId);
    if (!hint) return;

    var selectedOption = selectEl.options[selectEl.selectedIndex];
    var homepage = selectedOption ? selectedOption.getAttribute("data-homepage") : "";

    hint.textContent = "";
    if (homepage && /^https?:\/\//i.test(homepage)) {
      var prefix = document.createTextNode("Get your API key at ");
      var link = document.createElement("a");
      link.href = homepage;
      link.textContent = homepage;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.className = "underline hover:text-sky-600 dark:hover:text-sky-400";
      var suffix = document.createTextNode(".");
      hint.appendChild(prefix);
      hint.appendChild(link);
      hint.appendChild(suffix);
      hint.classList.remove("hidden");
    } else {
      hint.classList.add("hidden");
    }
  }

  function initProviderHints() {
    document.querySelectorAll("[data-provider-hint-target]").forEach(function (select) {
      updateProviderHint(select);
    });
  }

  function setFalEditDialogValues(button) {
    var modelId = button.getAttribute("data-model-id") || "";
    var name = button.getAttribute("data-model-name") || "";
    var identifier = button.getAttribute("data-model-identifier") || "";
    var params = button.getAttribute("data-model-params") || "{}";
    var enabled = button.getAttribute("data-model-enabled") === "1";

    var form = document.getElementById("edit-fal-model-form");
    var nameInput = document.getElementById("edit-fal-name");
    var identifierInput = document.getElementById("edit-fal-model-identifier");
    var paramsInput = document.getElementById("edit-fal-params");
    var enabledInput = document.getElementById("edit-fal-enabled");

    if (form) {
      form.action = "/admin/fal-models/" + encodeURIComponent(modelId) + "/update";
    }
    if (nameInput) {
      nameInput.value = name;
    }
    if (identifierInput) {
      identifierInput.value = identifier;
    }
    if (paramsInput) {
      paramsInput.value = params;
    }
    if (enabledInput) {
      enabledInput.checked = enabled;
    }
  }

  function initFalModelDialogs() {
    var editDialog = document.getElementById("edit-fal-model-dialog");
    var createDialog = document.getElementById("create-fal-model-dialog");

    document.querySelectorAll("[data-fal-edit-button]").forEach(function (button) {
      button.addEventListener("click", function () {
        setFalEditDialogValues(button);
        if (editDialog) {
          editDialog.showModal();
        }
      });
    });

    if (createDialog && createDialog.hasAttribute("data-open-on-load")) {
      createDialog.showModal();
    }
    if (editDialog && editDialog.hasAttribute("data-open-on-load")) {
      editDialog.showModal();
    }
  }

  window.toggleApiKeyField = toggleApiKeyField;
  window.updateProviderHint = updateProviderHint;

  document.addEventListener("DOMContentLoaded", function () {
    initProviderHints();
    initFalModelDialogs();
  });
})();
