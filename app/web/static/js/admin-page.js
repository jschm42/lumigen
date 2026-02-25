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

  window.toggleApiKeyField = toggleApiKeyField;
})();