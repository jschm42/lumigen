(function () {
  var THEME_STORAGE_KEY = "lumigen_theme";

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

    function setWorkspaceIframe(targetUrl) {
      var iframe = workspaceShell.querySelector("iframe[data-workspace-iframe]");
      if (!iframe) {
        iframe = document.createElement("iframe");
        iframe.setAttribute("data-workspace-iframe", "1");
        iframe.setAttribute("title", "workspace");
        iframe.className = "h-full w-full border-0";
        workspaceShell.replaceChildren(iframe);
      }
      if (iframe.getAttribute("src") !== targetUrl) {
        iframe.setAttribute("src", targetUrl);
      }
    }

    function resolveIframeUrl(view) {
      if (view === "profiles") return "/profiles?embedded=1";
      if (view === "gallery") return "/gallery?embedded=1";
      if (view === "admin") return "/admin?embedded=1";
      return "";
    }

    function applyWorkspaceView(view, url, pushHistory) {
      var iframeUrl = resolveIframeUrl(view);
      if (!iframeUrl) return false;

      setWorkspaceIframe(iframeUrl);
      setActiveWorkspaceLink(view);

      if (pushHistory && url) {
        window.history.pushState({ workspace_view: view }, "", url);
      }
      return true;
    }

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

        event.preventDefault();

        var view = link.getAttribute("data-workspace-view") || "";
        var href = link.getAttribute("href") || "";
        if (!view || !href) return;

        var absoluteUrl = new URL(href, window.location.origin);
        applyWorkspaceView(view, absoluteUrl.toString(), true);
      });
    });

    window.addEventListener("popstate", function () {
      var currentUrl = new URL(window.location.href);
      var view = (currentUrl.searchParams.get("workspace_view") || "chat").toLowerCase();
      if (!applyWorkspaceView(view, "", false)) {
        window.location.reload();
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
      }
    });
  }

  function saveSessionPreference(data) {
    var conversationInput = document.querySelector('[name="conversation"]');
    if (!conversationInput) return;
    var chatSessionId = conversationInput.value.trim();
    if (!chatSessionId || chatSessionId === "all" || chatSessionId === "new") return;

    var payload = { chat_session_id: chatSessionId };
    if (data.profile_id !== undefined) {
      payload.last_profile_id = data.profile_id;
    }
    if (data.thumb_size !== undefined) {
      payload.last_thumb_size = data.thumb_size;
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
  if (profileSelect) {
    profileSelect.addEventListener("change", function () {
      var profileId = parseInt(profileSelect.value, 10);
      if (!isNaN(profileId) && profileId > 0) {
        saveSessionPreference({ profile_id: profileId });
      }
    });
  }

  var thumbSizeButtons = document.querySelectorAll("[data-thumb-size-btn]");
  var chatShell = document.querySelector("[data-chat-shell]");
  var currentThumbSize = "";
  if (chatShell) {
    currentThumbSize = chatShell.dataset && chatShell.dataset.lastThumbSize ? chatShell.dataset.lastThumbSize : "";
  }

  function applyThumbSize(size) {
    var chatHistory = document.getElementById("chat-history");
    if (!chatHistory) return;

    chatHistory.classList.remove("thumb-size-sm", "thumb-size-md", "thumb-size-lg");
    chatHistory.classList.add("thumb-size-" + size);

    thumbSizeButtons.forEach(function (btn) {
      var btnSize = btn.getAttribute("data-thumb-size-btn");
      if (btnSize === size) {
        btn.classList.remove("border-white/10", "bg-white/10", "text-slate-300");
        btn.classList.add("border-sky-300/60", "bg-sky-300/20", "text-sky-100");
      } else {
        btn.classList.remove("border-sky-300/60", "bg-sky-300/20", "text-sky-100");
        btn.classList.add("border-white/10", "bg-white/10", "text-slate-300");
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

})();