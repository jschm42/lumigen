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
  window.adminImport = adminImport;

  document.addEventListener("DOMContentLoaded", function () {
    initProviderHints();
    initFalModelDialogs();
  });

  function adminImport() {
    var fileInput = document.getElementById("import-file");
    var conflictSelect = document.getElementById("import-conflict");
    var dryRunCheck = document.getElementById("import-dry-run");
    var resultDiv = document.getElementById("import-result");
    var submitBtn = document.getElementById("import-submit-btn");

    if (!fileInput || !fileInput.files || !fileInput.files.length) {
      _showImportError(resultDiv, "Please select a JSON file to import.");
      return;
    }

    var metaTag = document.querySelector('meta[name="csrf-token"]');
    var csrfToken = metaTag ? metaTag.getAttribute("content") : "";

    var formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("conflict_strategy", conflictSelect ? conflictSelect.value : "skip");
    formData.append("dry_run", dryRunCheck && dryRunCheck.checked ? "true" : "false");
    formData.append("csrf_token", csrfToken);

    if (submitBtn) submitBtn.disabled = true;
    _showImportLoading(resultDiv);

    fetch("/admin/import", {
      method: "POST",
      body: formData,
    })
      .then(function (resp) { return resp.json().then(function (data) { return { status: resp.status, data: data }; }); })
      .then(function (obj) {
        if (submitBtn) submitBtn.disabled = false;
        if (obj.status !== 200) {
          _showImportError(resultDiv, obj.data.error || "Import failed.");
          return;
        }
        _showImportResults(resultDiv, obj.data);
      })
      .catch(function (err) {
        if (submitBtn) submitBtn.disabled = false;
        _showImportError(resultDiv, "Request failed: " + err.message);
      });
  }

  function _showImportLoading(resultDiv) {
    resultDiv.className = "mt-2 rounded-2xl border border-slate-300/60 bg-white/90 px-4 py-3 text-sm text-slate-800 dark:border-white/10 dark:bg-slate-950/40 dark:text-slate-100";
    resultDiv.textContent = "Importing…";
  }

  function _showImportError(resultDiv, msg) {
    resultDiv.className = "mt-2 rounded-2xl border border-rose-300/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-800 dark:text-rose-100";
    resultDiv.textContent = msg;
  }

  function _showImportResults(resultDiv, data) {
    var isDryRun = data.dry_run;
    var results = data.results || [];
    var html = "";

    if (!results.length) {
      html = '<p class="text-slate-600 dark:text-slate-400">' + (data.message || "No entities imported.") + "</p>";
    } else {
      if (isDryRun) {
        html += '<p class="mb-3 font-semibold text-amber-700 dark:text-amber-300">Dry-run preview — no changes were saved.</p>';
      }
      results.forEach(function (r) {
        html += '<div class="mb-4">';
        html += '<p class="font-semibold capitalize text-slate-800 dark:text-slate-100">' + _esc(r.entity_type) + "</p>";
        html += '<ul class="mt-1 space-y-0.5 text-xs">';
        html += '<li><span class="text-emerald-600 dark:text-emerald-400">Created: ' + r.created + "</span></li>";
        html += '<li><span class="text-sky-600 dark:text-sky-400">Updated: ' + r.updated + "</span></li>";
        html += '<li><span class="text-slate-500 dark:text-slate-400">Skipped: ' + r.skipped + "</span></li>";
        if (r.failed) {
          html += '<li><span class="text-rose-600 dark:text-rose-400">Failed: ' + r.failed + "</span></li>";
        }
        html += "</ul>";
        var failedRecords = (r.records || []).filter(function (rec) { return rec.outcome === "failed"; });
        if (failedRecords.length) {
          html += '<ul class="mt-1 space-y-0.5 text-xs text-rose-600 dark:text-rose-400">';
          failedRecords.forEach(function (rec) {
            html += "<li>&bull; " + _esc(rec.name) + ": " + _esc(rec.reason) + "</li>";
          });
          html += "</ul>";
        }
        html += "</div>";
      });
    }

    resultDiv.className = "mt-2 rounded-2xl border border-slate-300/60 bg-white/90 px-4 py-3 text-sm dark:border-white/10 dark:bg-slate-950/40";
    resultDiv.innerHTML = html;
  }

  function _esc(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
})();
