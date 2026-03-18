(function () {
  'use strict';

  var THEME_STORAGE_KEY = 'lumigen_theme';

  function getSavedTheme() {
    try {
      var saved = localStorage.getItem(THEME_STORAGE_KEY);
      if (saved === 'light' || saved === 'dark' || saved === 'system') {
        return saved;
      }
    } catch (_error) {
      // localStorage can be blocked in strict browser modes.
    }
    return 'system';
  }

  function getSystemTheme() {
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    return 'light';
  }

  function applyEarlyTheme(themeMode) {
    var effective = themeMode === 'system' ? getSystemTheme() : themeMode;
    var normalized = effective === 'light' ? 'light' : 'dark';
    var root = document.documentElement;
    var colorSchemeMeta = document.querySelector('meta[name="color-scheme"]');

    root.classList.toggle('dark', normalized === 'dark');
    root.style.colorScheme = normalized;

    if (colorSchemeMeta) {
      colorSchemeMeta.setAttribute('content', normalized === 'light' ? 'light dark' : 'dark light');
    }

    function syncBodyTheme() {
      if (!document.body) return false;
      document.body.style.colorScheme = normalized;
      return true;
    }

    function syncBodyThemeSoon() {
      if (syncBodyTheme()) return;
      var attempts = 0;
      function trySync() {
        attempts += 1;
        if (syncBodyTheme() || attempts > 30) return;
        requestAnimationFrame(trySync);
      }
      requestAnimationFrame(trySync);
    }

    if (document.readyState === 'loading') {
      syncBodyThemeSoon();
      document.addEventListener('DOMContentLoaded', syncBodyTheme, { once: true });
      return;
    }

    syncBodyTheme();
  }

  applyEarlyTheme(getSavedTheme());
})();
