(function () {
  var popovers = Array.from(document.querySelectorAll("[data-category-popover]"));
  if (!popovers.length) return;

  function closeAll(exceptRoot) {
    popovers.forEach(function (root) {
      if (exceptRoot && root === exceptRoot) return;
      var toggle = root.querySelector("[data-category-popover-toggle]");
      var panel = root.querySelector("[data-category-popover-panel]");
      if (!toggle || !panel) return;
      panel.classList.add("hidden");
      toggle.setAttribute("aria-expanded", "false");
    });
  }

  popovers.forEach(function (root) {
    var toggle = root.querySelector("[data-category-popover-toggle]");
    var panel = root.querySelector("[data-category-popover-panel]");
    if (!toggle || !panel) return;

    toggle.addEventListener("click", function (event) {
      event.preventDefault();
      var willOpen = panel.classList.contains("hidden");
      closeAll(root);
      panel.classList.toggle("hidden", !willOpen);
      toggle.setAttribute("aria-expanded", willOpen ? "true" : "false");
    });
  });

  document.addEventListener("click", function (event) {
    var clickedInside = popovers.some(function (root) {
      return root.contains(event.target);
    });
    if (!clickedInside) {
      closeAll();
    }
  });
})();

(function () {
  var STORAGE_KEY = "lumigen_gallery_filters";
  var form = document.querySelector('form[action="/gallery"]');
  if (!form) return;

  function readState() {
    var state = {};
    var data = new FormData(form);

    data.forEach(function (value, key) {
      if (key === "category_ids") {
        if (!state[key]) state[key] = [];
        state[key].push(String(value));
        return;
      }
      state[key] = String(value);
    });

    if (!state.thumb_size) {
      var thumbInput = form.querySelector('input[name="thumb_size"]');
      state.thumb_size = thumbInput ? String(thumbInput.value || "md") : "md";
    }

    return state;
  }

  function writeState() {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(readState()));
    } catch (_error) {
      // Ignore storage errors.
    }
  }

  function applyState(state) {
    if (!state || typeof state !== "object") return;

    form.querySelectorAll("input, select").forEach(function (element) {
      if (!element.name) return;
      if (element.name === "category_ids") return;

      if (element.type === "checkbox") {
        element.checked = state[element.name] === "1" || state[element.name] === true;
        return;
      }

      if (Object.prototype.hasOwnProperty.call(state, element.name)) {
        element.value = state[element.name] || "";
      }
    });

    var selectedCategories = Array.isArray(state.category_ids) ? state.category_ids : [];
    form.querySelectorAll('input[name="category_ids"]').forEach(function (checkbox) {
      checkbox.checked = selectedCategories.indexOf(String(checkbox.value)) !== -1;
    });
  }

  var urlParams = new URLSearchParams(window.location.search);
  var hasRelevantParams = ["profile_name", "provider", "q", "min_rating", "unrated", "time_preset", "date_from", "date_to", "thumb_size", "category_ids"].some(function (key) {
    return urlParams.has(key);
  });

  if (hasRelevantParams) {
    writeState();
  } else {
    try {
      var raw = sessionStorage.getItem(STORAGE_KEY);
      if (raw) {
        applyState(JSON.parse(raw));
      }
    } catch (_error) {
      // Ignore storage errors.
    }
  }

  form.addEventListener("submit", writeState);
  form.addEventListener("change", writeState);
  form.addEventListener("input", function (event) {
    var target = event.target;
    if (!target || !target.name) return;
    if (target.name === "q" || target.name === "date_from" || target.name === "date_to") {
      writeState();
    }
  });

  document.querySelectorAll("[data-gallery-thumb-size]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var thumbInput = form.querySelector('input[name="thumb_size"]');
      if (thumbInput) {
        thumbInput.value = String(btn.getAttribute("data-gallery-thumb-size") || "md");
      }
      writeState();
    });
  });

  var resetLink = form.querySelector("[data-gallery-reset]");
  if (resetLink) {
    resetLink.addEventListener("click", function () {
      try {
        sessionStorage.removeItem(STORAGE_KEY);
      } catch (_error) {
        // Ignore storage errors.
      }
    });
  }
})();