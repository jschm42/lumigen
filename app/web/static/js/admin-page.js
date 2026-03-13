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

  window.toggleApiKeyField = toggleApiKeyField;
  window.updateProviderHint = updateProviderHint;

  document.addEventListener("DOMContentLoaded", initProviderHints);
})();
