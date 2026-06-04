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

  /**
   * Read the import form fields, POST the selected JSON file to /admin/import,
   * and render a summary of the results.
   *
   * Reads from DOM elements: #import-file, #import-conflict, #import-dry-run,
   * #import-result, #import-submit-btn.  The CSRF token is read from the
   * <meta name="csrf-token"> tag inserted by the server.
   */
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

  /**
   * Show a loading indicator in *resultDiv* while the import request is in
   * flight.
   * @param {HTMLElement} resultDiv - Container element for the result display.
   */
  function _showImportLoading(resultDiv) {
    resultDiv.className = "mt-2 rounded-2xl border border-slate-300/60 bg-white/90 px-4 py-3 text-sm text-slate-800 dark:border-white/10 dark:bg-slate-950/40 dark:text-slate-100";
    resultDiv.textContent = "Importing…";
  }

  /**
   * Render an error message inside *resultDiv*.
   * @param {HTMLElement} resultDiv - Container element for the result display.
   * @param {string} msg - Human-readable error text to show.
   */
  function _showImportError(resultDiv, msg) {
    resultDiv.className = "mt-2 rounded-2xl border border-rose-300/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-800 dark:text-rose-100";
    resultDiv.textContent = msg;
  }

  /**
   * Render a structured import summary inside *resultDiv*.
   *
   * @param {HTMLElement} resultDiv - Container element for the result display.
   * @param {object} data - Response body from POST /admin/import.
   * @param {boolean} data.dry_run - Whether the response is a dry-run preview.
   * @param {Array}   data.results - Array of per-entity-type result objects.
   * @param {string}  [data.message] - Optional message when results is empty.
   */
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

  /**
   * Escape special HTML characters in *str* to prevent XSS when injecting
   * server-supplied text into innerHTML.
   * @param {string} str - Raw string to escape.
   * @returns {string} HTML-escaped string.
   */
  function _esc(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /**
   * Find the model-config dialog that owns the given *prefix* and return its
   * provider select, model input, and API-key input elements.
   *
   * @param {string} prefix - DOM id prefix used by the macro (e.g. "new" or
   *   "edit-3").
   * @returns {{
   *   provider: HTMLSelectElement|null,
   *   modelInput: HTMLInputElement|null,
   *   apiKeyInput: HTMLInputElement|null,
   *   useCustomKey: HTMLInputElement|null,
   * }} Resolved DOM references (any may be null if not found).
   */
  function _resolveModelDialogElements(prefix) {
    var dialogId = prefix === "new"
      ? "create-model-config-dialog"
      : "edit-model-config-" + prefix.replace(/^edit-/, "");
    var dialog = document.getElementById(dialogId);
    if (!dialog) {
      return { provider: null, modelInput: null, apiKeyInput: null, useCustomKey: null };
    }
    var provider = dialog.querySelector('select[name="provider"]');
    var modelInput = dialog.querySelector('[data-model-input]');
    var apiKeyInput = dialog.querySelector('[data-api-key-input]');
    var useCustomKey = null;
    if (prefix === "new") {
      useCustomKey = document.getElementById("new-use-custom-api-key");
    } else {
      useCustomKey = document.getElementById(
        "edit-" + prefix.replace(/^edit-/, "") + "-use-custom-api-key"
      );
    }
    return { provider: provider, modelInput: modelInput, apiKeyInput: apiKeyInput, useCustomKey: useCustomKey };
  }

  /**
   * Build the absolute API URL for a provider endpoint on the admin page.
   * @param {string} provider - Provider name (e.g. "openai").
   * @param {string} suffix - Endpoint suffix (e.g. "/models").
   * @param {string} [query] - Optional raw query string (no leading "?").
   * @returns {string} Fully qualified URL.
   */
  function _providerEndpoint(provider, suffix, query) {
    var url = "/api/providers/" + encodeURIComponent(provider) + suffix;
    if (query) url += "?" + query;
    return url;
  }

  /**
   * Show a status message inside the model-discovery block of a dialog.
   * @param {string} prefix - DOM id prefix.
   * @param {string} message - Message text.
   * @param {"info"|"success"|"error"} kind - Style variant.
   */
  function _showDiscoveryStatus(prefix, message, kind) {
    var box = document.getElementById(prefix + "-model-discovery-status");
    if (!box) return;
    box.classList.remove(
      "hidden",
      "border-slate-300/60",
      "bg-white/90",
      "text-slate-800",
      "border-emerald-300/40",
      "bg-emerald-500/10",
      "text-emerald-100",
      "border-rose-300/40",
      "bg-rose-500/10",
      "text-rose-100"
    );
    if (kind === "success") {
      box.classList.add("border-emerald-300/40", "bg-emerald-500/10", "text-emerald-100");
    } else if (kind === "error") {
      box.classList.add("border-rose-300/40", "bg-rose-500/10", "text-rose-100");
    } else {
      box.classList.add("border-slate-300/60", "bg-white/90", "text-slate-800");
    }
    box.textContent = message;
  }

  /**
   * Fetch the list of available models for the currently selected provider in
   * the dialog identified by *prefix*, then populate the suggestions
   * datalist so the user can pick (or type a custom string).
   *
   * Resolution of the API key (highest priority first):
   *   1. Inline input in the dialog (only when "use custom API key" is on).
   *   2. Globally stored DB / .env key (sent implicitly — the server reads it).
   *
   * @param {string} prefix - DOM id prefix for the model dialog.
   */
  function discoverProviderModels(prefix) {
    var refs = _resolveModelDialogElements(prefix);
    if (!refs.provider) {
      _showDiscoveryStatus(prefix, "Provider select not found.", "error");
      return;
    }
    var provider = refs.provider.value;
    if (!provider) {
      _showDiscoveryStatus(prefix, "Select a provider first.", "error");
      return;
    }
    var inlineKey = "";
    if (refs.useCustomKey && refs.useCustomKey.checked && refs.apiKeyInput) {
      inlineKey = (refs.apiKeyInput.value || "").trim();
    }
    var query = inlineKey
      ? "api_key=" + encodeURIComponent(inlineKey)
      : "";
    var button = document.querySelector(
      '[data-model-discovery][data-prefix="' + prefix + '"] [data-discover-button]'
    );
    var label = document.querySelector(
      '[data-model-discovery][data-prefix="' + prefix + '"] [data-discover-label]'
    );
    if (button) button.disabled = true;
    if (label) label.textContent = "Discovering…";
    _showDiscoveryStatus(prefix, "Fetching models for " + provider + "…", "info");

    fetch(_providerEndpoint(provider, "/models", query), {
      method: "GET",
      headers: { "Accept": "application/json" },
    })
      .then(function (resp) {
        return resp.json().then(function (data) {
          return { status: resp.status, data: data };
        });
      })
      .then(function (obj) {
        if (button) button.disabled = false;
        if (label) label.textContent = "Discover models";
        if (obj.status !== 200) {
          _showDiscoveryStatus(
            prefix,
            (obj.data && obj.data.error) || "Discovery failed.",
            "error"
          );
          return;
        }
        var data = obj.data || {};
        if (data.error) {
          _showDiscoveryStatus(prefix, data.error, "error");
          return;
        }
        var models = Array.isArray(data.models) ? data.models : [];
        var list = document.getElementById(prefix + "-model-suggestions-list");
        if (list) {
          list.innerHTML = "";
          models.forEach(function (modelId) {
            var opt = document.createElement("option");
            opt.value = modelId;
            list.appendChild(opt);
          });
        }
        if (models.length === 0) {
          _showDiscoveryStatus(
            prefix,
            "Provider returned no models. You can still enter a custom model string above.",
            "info"
          );
        } else {
          _showDiscoveryStatus(
            prefix,
            "Found " + models.length + " model" + (models.length === 1 ? "" : "s") + ". Pick one or type a custom string above.",
            "success"
          );
        }
      })
      .catch(function (err) {
        if (button) button.disabled = false;
        if (label) label.textContent = "Discover models";
        _showDiscoveryStatus(prefix, "Request failed: " + err.message, "error");
      });
  }

  /**
   * Run a small generation request against the currently selected provider
   * to verify connectivity. The result is rendered as a data-URL image (or
   * an error message) inside the dialog's test-result container.
   *
   * @param {string} prefix - DOM id prefix for the model dialog.
   */
  function testProviderConnection(prefix) {
    var refs = _resolveModelDialogElements(prefix);
    if (!refs.provider || !refs.modelInput) {
      _showTestResult(prefix, "Provider or model input not found.", null, "error");
      return;
    }
    var provider = refs.provider.value;
    var model = (refs.modelInput.value || "").trim();
    if (!provider) {
      _showTestResult(prefix, "Select a provider first.", null, "error");
      return;
    }
    if (!model) {
      _showTestResult(prefix, "Enter a model string first (or discover models).", null, "error");
      return;
    }
    var inlineKey = "";
    if (refs.useCustomKey && refs.useCustomKey.checked && refs.apiKeyInput) {
      inlineKey = (refs.apiKeyInput.value || "").trim();
    }
    var button = document.querySelector(
      '[data-model-discovery][data-prefix="' + prefix + '"] [data-test-button]'
    );
    var label = document.querySelector(
      '[data-model-discovery][data-prefix="' + prefix + '"] [data-test-label]'
    );
    if (button) button.disabled = true;
    if (label) label.textContent = "Testing…";
    _showTestResult(prefix, "Sending test request to " + provider + "…", null, "info");

    fetch(_providerEndpoint(provider, "/test"), {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ model: model, api_key: inlineKey }),
    })
      .then(function (resp) {
        return resp.json().then(function (data) {
          return { status: resp.status, data: data };
        });
      })
      .then(function (obj) {
        if (button) button.disabled = false;
        if (label) label.textContent = "Test connection";
        var data = obj.data || {};
        if (data.error) {
          _showTestResult(prefix, data.error, null, "error");
          return;
        }
        if (data.image && data.image.data_url) {
          _showTestResult(
            prefix,
            "Test image received (" + data.image.width + "x" + data.image.height + ", " + data.image.mime + ").",
            data.image,
            "success"
          );
        } else {
          _showTestResult(prefix, "Test returned no image.", null, "error");
        }
      })
      .catch(function (err) {
        if (button) button.disabled = false;
        if (label) label.textContent = "Test connection";
        _showTestResult(prefix, "Request failed: " + err.message, null, "error");
      });
  }

  /**
   * Render the test-result container of a model dialog.
   * @param {string} prefix - DOM id prefix.
   * @param {string} message - Status text.
   * @param {object|null} image - Image payload from the server (or null).
   * @param {"info"|"success"|"error"} kind - Style variant.
   */
  function _showTestResult(prefix, message, image, kind) {
    var box = document.getElementById(prefix + "-model-test-result");
    if (!box) return;
    box.classList.remove(
      "hidden",
      "border-slate-300/60",
      "bg-white/90",
      "text-slate-800",
      "border-emerald-300/40",
      "bg-emerald-500/10",
      "text-emerald-100",
      "border-rose-300/40",
      "bg-rose-500/10",
      "text-rose-100"
    );
    if (kind === "success") {
      box.classList.add("border-emerald-300/40", "bg-emerald-500/10", "text-emerald-100");
    } else if (kind === "error") {
      box.classList.add("border-rose-300/40", "bg-rose-500/10", "text-rose-100");
    } else {
      box.classList.add("border-slate-300/60", "bg-white/90", "text-slate-800");
    }
    var preview = box.querySelector("[data-test-preview]");
    box.textContent = message;
    if (preview && preview.parentNode) preview.parentNode.removeChild(preview);
    if (image && image.data_url && kind === "success") {
      var newPreview = document.createElement("div");
      newPreview.setAttribute("data-test-preview", "");
      newPreview.className = "mt-2";
      var imgEl = document.createElement("img");
      imgEl.src = image.data_url;
      imgEl.alt = "Test image";
      imgEl.className =
        "max-h-40 rounded-lg border border-emerald-300/40 bg-white/90 dark:bg-slate-950/40";
      newPreview.appendChild(imgEl);
      box.appendChild(newPreview);
    }
  }

  /**
   * When the user picks a model from the suggestions datalist, copy the
   * value into the "Model" input so it actually gets submitted.
   * @param {string} prefix - DOM id prefix.
   */
  function copyDiscoveredModelToInput(prefix) {
    var refs = _resolveModelDialogElements(prefix);
    var suggestions = document.getElementById(prefix + "-model-suggestions");
    if (!refs.modelInput || !suggestions) return;
    if (suggestions.value) {
      refs.modelInput.value = suggestions.value;
    }
  }

  window.discoverProviderModels = discoverProviderModels;
  window.testProviderConnection = testProviderConnection;
  window.copyDiscoveredModelToInput = copyDiscoveredModelToInput;
})();
