(function () {
  function isTruthy(value) {
    if (!value) return false;
    var normalized = String(value).toLowerCase();
    return normalized === "1" || normalized === "true" || normalized === "yes" || normalized === "on";
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
  });
})();