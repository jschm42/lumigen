(function () {
  var THEME_STORAGE_KEY = "lumigen_theme";

  function getActiveConversationToken() {
    var conversationInput = document.querySelector('[name="conversation"]');
    if (!conversationInput) return "";
    return String(conversationInput.value || "").trim();
  }

  function getSavedThemeMode() {
    try {
      var saved = localStorage.getItem(THEME_STORAGE_KEY);
      if (saved === "light" || saved === "dark" || saved === "system") {
        return saved;
      }
    } catch (_error) {
      // Ignore storage access errors and fall back to system.
    }
    return "system";
  }

  function getEffectiveThemeMode(mode) {
    if (mode !== "system") return mode;
    if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      return "dark";
    }
    return "light";
  }

  function syncWorkspaceThemeClass() {
    var root = document.documentElement;
    if (!root) return;
    var effective = getEffectiveThemeMode(getSavedThemeMode());
    root.classList.toggle("dark", effective === "dark");
    root.style.colorScheme = effective;
  }

  function syncOverlayOffsets() {
    var history = document.getElementById("chat-history");
    var topPanel = document.querySelector("[data-chat-top-panel]");
    var bottomPanel = document.querySelector("[data-chat-bottom-panel]");
    if (!history) return;

    var topHeight = topPanel ? Math.ceil(topPanel.getBoundingClientRect().height) : 0;
    var bottomHeight = bottomPanel ? Math.ceil(bottomPanel.getBoundingClientRect().height) : 0;

    history.style.paddingTop = String(Math.max(topHeight + 8, 56)) + "px";
    history.style.paddingBottom = String(Math.max(bottomHeight + 12, 140)) + "px";
  }

  function scrollChatToBottom() {
    var chat = document.getElementById("chat-history");
    if (!chat) return;
    chat.scrollTop = chat.scrollHeight;
  }

  function setupChatAutoScroll() {
    var chat = document.getElementById("chat-history");
    if (!chat) return;
    chat.addEventListener(
      "load",
      function (event) {
        var target = event.target;
        if (target && target.tagName === "IMG") {
          scrollChatToBottom();
        }
      },
      true
    );
  }

  function setupOverlayObservers() {
    var topPanel = document.querySelector("[data-chat-top-panel]");
    var bottomPanel = document.querySelector("[data-chat-bottom-panel]");

    syncOverlayOffsets();

    if (window.ResizeObserver) {
      var observer = new ResizeObserver(function () {
        syncOverlayOffsets();
      });
      if (topPanel) observer.observe(topPanel);
      if (bottomPanel) observer.observe(bottomPanel);
    }

    window.addEventListener("resize", syncOverlayOffsets);
  }

  function setupSessionMenus() {
    var renameForm = document.getElementById("rename-session-form");
    var renameTokenInput = renameForm ? renameForm.querySelector("[name='session_token']") : null;
    var renameTitleInput = renameForm ? renameForm.querySelector("[name='title']") : null;

    function closeAllMenus() {
      document.querySelectorAll("[data-session-menu]").forEach(function (menu) {
        menu.classList.add("hidden");
      });
    }

    document.addEventListener("click", function (event) {
      var target = event.target;
      if (!(target instanceof Element)) {
        closeAllMenus();
        return;
      }

      var toggle = target.closest("[data-session-menu-toggle]");
      if (toggle) {
        event.preventDefault();
        event.stopPropagation();
        var container = toggle.parentElement;
        if (!container) return;
        var menu = container.querySelector("[data-session-menu]");
        if (!menu) return;
        var wasHidden = menu.classList.contains("hidden");
        closeAllMenus();
        if (wasHidden) {
          menu.classList.remove("hidden");
        }
        return;
      }

      var renameButton = target.closest("[data-session-rename]");
      if (renameButton) {
        event.preventDefault();
        event.stopPropagation();
        var token = renameButton.getAttribute("data-session-token") || "";
        var currentTitle = renameButton.getAttribute("data-session-title") || "";
        var nextTitle = window.prompt("Rename session", currentTitle);
        if (nextTitle === null) return;
        var trimmed = nextTitle.trim();
        if (!trimmed || !renameForm || !renameTokenInput || !renameTitleInput) return;
        renameTokenInput.value = token;
        renameTitleInput.value = trimmed;
        renameForm.submit();
        return;
      }

      if (!target.closest("[data-session-menu]")) {
        closeAllMenus();
      }
    });
  }

  function setupWorkspaceNavigation() {
    var workspaceLinks = document.querySelectorAll("[data-workspace-nav][data-workspace-view]");
    var workspaceShell = document.querySelector("[data-chat-shell]");
    if (!workspaceLinks.length || !workspaceShell) return;

    var activeClasses = ["bg-sky-300/30", "text-sky-900", "dark:bg-sky-300/20", "dark:text-sky-100"];
    var inactiveClasses = [
      "bg-white",
      "text-slate-700",
      "hover:bg-sky-50",
      "dark:bg-white/10",
      "dark:text-slate-200",
      "dark:hover:bg-white/20",
    ];

    function setActiveWorkspaceLink(activeView) {
      workspaceLinks.forEach(function (link) {
        var view = link.getAttribute("data-workspace-view") || "";
        var isActive = view === activeView;
        if (isActive) {
          inactiveClasses.forEach(function (className) {
            link.classList.remove(className);
          });
          activeClasses.forEach(function (className) {
            link.classList.add(className);
          });
        } else {
          activeClasses.forEach(function (className) {
            link.classList.remove(className);
          });
          inactiveClasses.forEach(function (className) {
            link.classList.add(className);
          });
        }
      });
    }

    // Removed iframe-related functions as we're now using HTMX for workspace navigation

    // Workspace links now use HTMX attributes, so we don't need to handle clicks manually
    // We still need to update the active link styling
    workspaceLinks.forEach(function (link) {
      link.addEventListener("click", function (event) {
        if (
          event.defaultPrevented ||
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey
        ) {
          return;
        }

        // Update active link styling
        var view = link.getAttribute("data-workspace-view") || "";
        if (view) {
          setActiveWorkspaceLink(view);
        }
      });
    });

    // Handle browser back/forward navigation
    window.addEventListener("popstate", function () {
      var currentUrl = new URL(window.location.href);
      var view = (currentUrl.searchParams.get("workspace_view") || "chat").toLowerCase();
      var targetUrl = "";
      
      // Update active link styling
      setActiveWorkspaceLink(view);
      
      // Load content via HTMX if needed
      if (view !== "chat") {
        if (view === "profiles") targetUrl = "/workspace/profiles";
        else if (view === "gallery") targetUrl = "/workspace/gallery";
        else if (view === "admin") targetUrl = "/workspace/admin";
        
        if (targetUrl) {
          // Trigger HTMX load
          var workspaceContent = document.getElementById("workspace-content");
          if (workspaceContent) {
            workspaceContent.setAttribute("hx-get", targetUrl);
            htmx.process(workspaceContent);
            htmx.trigger(workspaceContent, "load");
          }
        }
      }
    });
  }

  window.addEventListener("DOMContentLoaded", function () {
    syncWorkspaceThemeClass();
    setupOverlayObservers();
    setupSessionMenus();
    setupWorkspaceNavigation();
    setupChatAutoScroll();
    scrollChatToBottom();
    syncRetryProfileIds();
  });

  if (typeof window.addEventListener === "function") {
    window.addEventListener("focus", syncWorkspaceThemeClass);
    window.addEventListener("storage", function (event) {
      if (!event || event.key !== THEME_STORAGE_KEY) return;
      syncWorkspaceThemeClass();
    });
  }

  if (window.matchMedia) {
    var media = window.matchMedia("(prefers-color-scheme: dark)");
    var syncIfSystemTheme = function () {
      if (getSavedThemeMode() === "system") {
        syncWorkspaceThemeClass();
      }
    };
    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", syncIfSystemTheme);
    } else if (typeof media.addListener === "function") {
      media.addListener(syncIfSystemTheme);
    }
  }

  var body = document.body;
  if (body) {
    body.addEventListener("htmx:afterSwap", function (event) {
      var chat = document.getElementById("chat-history");
      if (!chat) return;
      var target = event.target;
      var detailTarget = event.detail && event.detail.target ? event.detail.target : null;
      var inChat = false;
      if (target && (target.id === "chat-history" || chat.contains(target))) {
        inChat = true;
      }
      if (!inChat && detailTarget && (detailTarget.id === "chat-history" || chat.contains(detailTarget))) {
        inChat = true;
      }
      if (inChat) {
        syncOverlayOffsets();
        scrollChatToBottom();
        if (currentThumbSize) {
          applyThumbSize(currentThumbSize);
        }
        syncRetryProfileIds();
      }
    });
  }

  function saveSessionPreference(data) {
    var chatSessionId = getActiveConversationToken();
    
    // Always store in localStorage for global persistence/fallback
    if (data.profile_id !== undefined) {
      localStorage.setItem("lumigen_last_profile_id", data.profile_id);
    }
    if (data.thumb_size !== undefined) {
      localStorage.setItem("lumigen_thumb_size", data.thumb_size);
    }

    // Save to server only for established sessions
    if (!chatSessionId || chatSessionId === "all" || chatSessionId === "new") return;

    var payload = { chat_session_id: chatSessionId };
    if (data.profile_id !== undefined) {
      payload.last_profile_id = data.profile_id;
    }
    if (data.thumb_size !== undefined) {
      payload.last_thumb_size = data.thumb_size;
    }
    if (data.selected_style_ids !== undefined) {
      payload.selected_style_ids = data.selected_style_ids;
    }
    var csrfMeta = document.querySelector('meta[name="csrf-token"]');
    var csrfToken = csrfMeta ? String(csrfMeta.getAttribute('content') || '').trim() : '';

    fetch("/api/session-preferences", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify(payload)
    }).catch(function (err) {
      console.error("Failed to save session preference:", err);
    });
  }

  var profileSelect = document.querySelector("[data-generation-profile]");

  function syncRetryProfileIds() {
    /**
     * Synchronize the currently selected profile ID into all retry form
     * hidden inputs, so that clicking Retry re-runs with the active profile
     * rather than the profile from the original failed request.
     */
    if (!profileSelect) return;
    var profileId = profileSelect.value || "";
    var inputs = document.querySelectorAll("[data-retry-profile-id]");
    inputs.forEach(function (input) {
      input.value = profileId;
    });
  }

  if (profileSelect) {
    // Restore profile from localStorage if not set by server
    var chatSessionId = getActiveConversationToken();
    if (chatSessionId === "new" || !profileSelect.value) {
      var localProfileId = localStorage.getItem("lumigen_last_profile_id");
      if (localProfileId) {
        // Only set if the option exists
        var exists = Array.from(profileSelect.options).some(function(opt) { return opt.value === localProfileId; });
        if (exists) {
          profileSelect.value = localProfileId;
          // Trigger change to update UI dependencies (dimension panels etc)
          profileSelect.dispatchEvent(new Event("change"));
        }
      }
    }

    profileSelect.addEventListener("change", function () {
      var profileId = parseInt(profileSelect.value, 10);
      if (!isNaN(profileId) && profileId > 0) {
        saveSessionPreference({ profile_id: profileId });
      }
      syncRetryProfileIds();
    });
  }

  var thumbSizeButtons = document.querySelectorAll("[data-thumb-size-btn]");
  var chatShell = document.querySelector("[data-chat-shell]");
  var currentThumbSize = "";
  if (chatShell) {
    currentThumbSize = chatShell.dataset && chatShell.dataset.lastThumbSize ? chatShell.dataset.lastThumbSize : "";
  }
  
  // Fallback to localStorage if server didn't provide a size
  if (!currentThumbSize || currentThumbSize === "undefined") {
    currentThumbSize = localStorage.getItem("lumigen_thumb_size") || "md";
  }

  function applyThumbSize(size) {
    var chatHistory = document.getElementById("chat-history");
    if (!chatHistory) return;

    chatHistory.classList.remove("thumb-size-sm", "thumb-size-md", "thumb-size-lg");
    chatHistory.classList.add("thumb-size-" + size);

    thumbSizeButtons.forEach(function (btn) {
      var btnSize = btn.getAttribute("data-thumb-size-btn");
      if (btnSize === size) {
        btn.classList.remove("border-slate-300/80", "bg-white", "text-slate-700", "dark:border-white/10", "dark:bg-white/10", "dark:text-slate-300");
        btn.classList.add("border-sky-300/60", "bg-sky-300/30", "text-sky-900", "dark:bg-sky-300/20", "dark:text-sky-100");
      } else {
        btn.classList.remove("border-sky-300/60", "bg-sky-300/30", "text-sky-900", "dark:bg-sky-300/20", "dark:text-sky-100");
        btn.classList.add("border-slate-300/80", "bg-white", "text-slate-700", "dark:border-white/10", "dark:bg-white/10", "dark:text-slate-300");
      }
    });
  }

  thumbSizeButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var size = btn.getAttribute("data-thumb-size-btn");
      if (size && (size === "sm" || size === "md" || size === "lg")) {
        currentThumbSize = size;
        applyThumbSize(size);
        saveSessionPreference({ thumb_size: size });
      }
    });
  });

  if (currentThumbSize) {
    applyThumbSize(currentThumbSize);
  }

  // Re-apply on HTMX swaps (important if chat-history is swapped)
  document.body.addEventListener('htmx:afterSwap', function(evt) {
    if (evt.detail.target.id === 'chat-history' || evt.detail.target.querySelector('#chat-history')) {
      if (currentThumbSize) {
        applyThumbSize(currentThumbSize);
      }
    }
  });

  // ---- Styles picker ----

  function parseSelectedStyleIdsCsv(value) {
    return String(value || "")
      .split(",")
      .map(function (item) {
        return parseInt(item.trim(), 10);
      })
      .filter(function (item) {
        return !isNaN(item) && item > 0;
      });
  }

  var initialStyleIdsValue = "";
  var initialStyleInput = document.getElementById("style_ids_input");
  initialStyleIdsValue = initialStyleInput ? initialStyleInput.value : "";
  var selectedStyleIds = parseSelectedStyleIdsCsv(initialStyleIdsValue);

  function renderSelectedStyles(syncSessionPreference) {
    var row = document.getElementById("selected-styles-row");
    var hiddenInput = document.getElementById("style_ids_input");
    if (!row) return;

    if (hiddenInput) {
      hiddenInput.value = selectedStyleIds.join(",");
    }

    if (syncSessionPreference !== false) {
      saveSessionPreference({ selected_style_ids: selectedStyleIds.join(",") });
    }

    if (selectedStyleIds.length === 0) {
      row.innerHTML = "";
      return;
    }

    var chips = selectedStyleIds.map(function (id) {
      var btn = document.querySelector(".styles-picker-item[data-style-id='" + id + "']");
      var name = btn ? (btn.getAttribute("data-style-name") || String(id)) : String(id);
      var imgEl = btn ? btn.querySelector("img") : null;
      var imgSrc = imgEl ? imgEl.getAttribute("src") : "";

      return (
        '<span class="inline-flex items-center gap-1.5 rounded-xl border border-sky-300/60 bg-sky-50 px-2 py-1 text-xs font-semibold text-sky-800 dark:border-sky-300/30 dark:bg-sky-300/10 dark:text-sky-100">' +
        (imgSrc
          ? '<img src="' + imgSrc + '" alt="" class="h-5 w-5 rounded object-cover">'
          : "") +
        '<span>' + escapeHtml(name) + "</span>" +
        '<button type="button" class="ml-0.5 flex h-4 w-4 items-center justify-center rounded-full text-sky-600 hover:bg-sky-200 hover:text-sky-900 dark:text-sky-300 dark:hover:bg-sky-300/20" data-remove-style-id="' + id + '" aria-label="Remove style">×</button>' +
        "</span>"
      );
    });

    row.innerHTML =
      '<div class="subtle-scrollbar flex flex-nowrap gap-1.5 overflow-x-auto pb-1 pt-0.5">' +
      chips.join("") +
      "</div>";

    row.querySelectorAll("[data-remove-style-id]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var removeId = parseInt(btn.getAttribute("data-remove-style-id"), 10);
        selectedStyleIds = selectedStyleIds.filter(function (id) { return id !== removeId; });
        // Sync the picker button state
        var pickerBtn = document.querySelector(".styles-picker-item[data-style-id='" + removeId + "']");
        if (pickerBtn) {
          pickerBtn.setAttribute("aria-pressed", "false");
          pickerBtn.classList.remove("ring-2", "ring-sky-400", "border-sky-400");
        }
        renderSelectedStyles();
      });
    });
  }

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
  }

  function initStylesPicker() {
    var pickerBtn = document.getElementById("styles-picker-btn");
    var dialog = document.getElementById("styles-picker-dialog");
    if (!pickerBtn || !dialog) return;

    pickerBtn.addEventListener("click", function () {
      dialog.showModal();
    });

    dialog.querySelectorAll(".styles-picker-item").forEach(function (item) {
      var initialId = parseInt(item.getAttribute("data-style-id"), 10);
      if (!isNaN(initialId) && selectedStyleIds.indexOf(initialId) !== -1) {
        item.setAttribute("aria-pressed", "true");
        item.classList.add("ring-2", "ring-sky-400", "border-sky-400");
      }

      item.addEventListener("click", function () {
        var id = parseInt(item.getAttribute("data-style-id"), 10);
        if (isNaN(id)) return;
        var idx = selectedStyleIds.indexOf(id);
        if (idx === -1) {
          selectedStyleIds.push(id);
          item.setAttribute("aria-pressed", "true");
          item.classList.add("ring-2", "ring-sky-400", "border-sky-400");
        } else {
          selectedStyleIds.splice(idx, 1);
          item.setAttribute("aria-pressed", "false");
          item.classList.remove("ring-2", "ring-sky-400", "border-sky-400");
        }
        renderSelectedStyles();
      });
    });
  }

  // Clear selected styles when the input-clear button is clicked
  var inputClearBtn = document.querySelector("[data-input-clear]");
  if (inputClearBtn) {
    inputClearBtn.addEventListener("click", function () {
      selectedStyleIds = [];
      document.querySelectorAll(".styles-picker-item").forEach(function (item) {
        item.setAttribute("aria-pressed", "false");
        item.classList.remove("ring-2", "ring-sky-400", "border-sky-400");
      });
      renderSelectedStyles();
    });
  }

  // ---- Prompt Enhancement ----

  window.closeEnhancementPreview = function() {
    var dialog = document.getElementById('enhancement-preview-dialog');
    if (dialog) dialog.close();
  };

  window.applyEnhancedPrompt = function() {
    var resultArea = document.getElementById('enhanced-prompt-result');
    var promptInput = document.getElementById('prompt_user');
    if (resultArea && promptInput) {
      promptInput.value = resultArea.value;
      // Trigger auto-resize if any
      promptInput.dispatchEvent(new Event('input'));
    }
    window.closeEnhancementPreview();
  };

  var enhanceBtn = document.querySelector('[data-enhance-prompt]');
  if (enhanceBtn) {
    enhanceBtn.addEventListener('click', function() {
      var promptInput = document.getElementById('prompt_user');
      var profileSelect = document.getElementById('profile_id');
      var dialog = document.getElementById('enhancement-preview-dialog');
      var content = document.getElementById('enhancement-preview-content');

      if (!promptInput || !promptInput.value.trim()) {
        alert("Please enter a prompt first.");
        return;
      }
      if (!dialog || !content) return;

      // Show loader
      content.innerHTML = 
        '<div class="flex flex-col items-center justify-center py-12">' +
            '<div class="h-8 w-8 animate-spin rounded-full border-4 border-sky-300 border-t-transparent"></div>' +
            '<p class="mt-4 text-sm font-medium text-slate-600 dark:text-slate-400">Enhancing prompt...</p>' +
        '</div>';
      
      dialog.showModal();

      var profileId = profileSelect ? profileSelect.value : null;

      if (!profileId || profileId === "" || profileId === "null") {
        alert("Please select a profile first to enhance the prompt for that specific model.");
        dialog.close();
        return;
      }
      
      var csrfMeta = document.querySelector('meta[name="csrf-token"]');
      var csrfToken = csrfMeta ? String(csrfMeta.getAttribute('content') || '').trim() : '';

      var formData = new FormData();
      formData.append('prompt', promptInput.value);
      formData.append('profile_id', profileId);

      fetch('/api/enhance-prompt', {
        method: 'POST',
        headers: {
          'X-CSRF-Token': csrfToken
        },
        body: formData
      })
      .then(function(response) {
        if (!response.ok) return response.text().then(function(text) { throw new Error(text || 'Failed to enhance prompt'); });
        return response.text();
      })
      .then(function(html) {
        content.innerHTML = html;
        if (window.htmx) htmx.process(content);
      })
      .catch(function(err) {
        content.innerHTML = 
          '<div class="p-6 text-center">' +
            '<h4 class="text-lg font-semibold text-rose-500 mb-2">Enhancement Failed</h4>' +
            '<p class="text-sm text-slate-600 dark:text-slate-400 mb-6">' + escapeHtml(err.message) + '</p>' +
            '<button type="button" class="inline-flex items-center justify-center rounded-xl border border-slate-300/80 bg-white px-4 py-2 text-sm font-semibold text-slate-800 transition hover:bg-slate-50 dark:border-0 dark:bg-white/10 dark:text-slate-100" onclick="closeEnhancementPreview()">Close</button>' +
          '</div>';
      });
    });
  }

  initStylesPicker();
  renderSelectedStyles(false);

})();