(function () {
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
    var menuToggles = Array.from(document.querySelectorAll("[data-session-menu-toggle]"));
    var renameForm = document.getElementById("rename-session-form");
    var renameTokenInput = renameForm ? renameForm.querySelector("[name='session_token']") : null;
    var renameTitleInput = renameForm ? renameForm.querySelector("[name='title']") : null;

    function closeAllMenus() {
      document.querySelectorAll("[data-session-menu]").forEach(function (menu) {
        menu.classList.add("hidden");
      });
    }

    menuToggles.forEach(function (toggle) {
      toggle.addEventListener("click", function (event) {
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
      });
    });

    document.addEventListener("click", function () {
      closeAllMenus();
    });

    document.querySelectorAll("[data-session-rename]").forEach(function (button) {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        var token = button.getAttribute("data-session-token") || "";
        var currentTitle = button.getAttribute("data-session-title") || "";
        var nextTitle = window.prompt("Rename session", currentTitle);
        if (nextTitle === null) return;
        var trimmed = nextTitle.trim();
        if (!trimmed || !renameForm || !renameTokenInput || !renameTitleInput) return;
        renameTokenInput.value = token;
        renameTitleInput.value = trimmed;
        renameForm.submit();
      });
    });
  }

  window.addEventListener("DOMContentLoaded", function () {
    setupOverlayObservers();
    setupSessionMenus();
    setupChatAutoScroll();
    scrollChatToBottom();
  });

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
        btn.classList.remove("border-white/10", "bg-white/6", "text-slate-300");
        btn.classList.add("border-sky-300/60", "bg-sky-300/20", "text-sky-100");
      } else {
        btn.classList.remove("border-sky-300/60", "bg-sky-300/20", "text-sky-100");
        btn.classList.add("border-white/10", "bg-white/6", "text-slate-300");
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

  function setupLoadMoreSessions() {
    var loadMoreBtn = document.querySelector("[data-load-more-sessions]");
    if (!loadMoreBtn) return;

    loadMoreBtn.addEventListener("click", function () {
      var offset = parseInt(loadMoreBtn.getAttribute("data-offset") || "0", 10);
      var currentUrl = new URL(window.location.href);
      currentUrl.searchParams.set("session_offset", offset);
      window.location.href = currentUrl.toString();
    });
  }

  function setupUserMenu() {
    var toggle = document.querySelector("[data-user-menu-toggle]");
    var menu = document.querySelector("[data-user-menu]");
    var chevron = document.querySelector("[data-user-menu-chevron]");
    if (!toggle || !menu) return;

    function openMenu() {
      menu.classList.remove("hidden");
      toggle.setAttribute("aria-expanded", "true");
      if (chevron) chevron.textContent = "expand_more";
    }

    function closeMenu() {
      menu.classList.add("hidden");
      toggle.setAttribute("aria-expanded", "false");
      if (chevron) chevron.textContent = "expand_less";
    }

    var container = document.querySelector("[data-user-menu-container]");

    toggle.addEventListener("click", function (event) {
      event.stopPropagation();
      if (menu.classList.contains("hidden")) {
        openMenu();
      } else {
        closeMenu();
      }
    });

    document.addEventListener("click", function (event) {
      if (container && !container.contains(event.target)) {
        closeMenu();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeMenu();
      }
    });
  }

  setupLoadMoreSessions();
  setupUserMenu();
})();