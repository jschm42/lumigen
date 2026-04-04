/**
 * Lumigen App - Main JavaScript
 * 
 * Contains all global JavaScript functionality:
 * - Random seed generation
 * - Model loading
 * - Generation form handling
 * - Profile form handling
 * - Gallery selection
 */

(function () {
  'use strict';

  var THEME_STORAGE_KEY = 'lumigen_theme';
  var mediaThemeListenerBound = false;

  // ==========================================================================
  // Utility Functions
  // ==========================================================================

  /**
   * Generate a random integer between min and max (inclusive)
   */
  function randomInt(min, max) {
    var span = (max - min + 1);
    return Math.floor(Math.random() * span) + min;
  }

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (!meta) return '';
    return String(meta.getAttribute('content') || '').trim();
  }

  function getSavedTheme() {
    try {
      var saved = localStorage.getItem(THEME_STORAGE_KEY);
      if (saved === 'light' || saved === 'dark' || saved === 'system') {
        return saved;
      }
    } catch (_error) {
      // localStorage can be unavailable in strict browser modes.
    }
    return 'system';
  }

  function getSystemTheme() {
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    return 'light';
  }

  function applyTheme(theme) {
    var effective = theme === 'system' ? getSystemTheme() : theme;
    var normalized = effective === 'light' ? 'light' : 'dark';
    var root = document.documentElement;
    var body = document.body;
    var colorSchemeMeta = document.querySelector('meta[name="color-scheme"]');

    root.classList.toggle('dark', normalized === 'dark');
    root.style.colorScheme = normalized;
    if (body) {
      body.style.colorScheme = normalized;
    }
    if (colorSchemeMeta) {
      colorSchemeMeta.setAttribute('content', normalized === 'light' ? 'light dark' : 'dark light');
    }
  }

  function persistTheme(theme) {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch (_error) {
      // Ignore persistence failures and keep runtime state only.
    }
  }

  function initTheme() {
    applyTheme(getSavedTheme());

    if (typeof window.addEventListener === 'function') {
      window.addEventListener('storage', function (event) {
        if (!event || event.key !== THEME_STORAGE_KEY) return;
        applyTheme(getSavedTheme());
      });

      // Fallback for contexts where storage events are not delivered as expected.
      window.addEventListener('focus', function () {
        applyTheme(getSavedTheme());
      });
    }

    if (mediaThemeListenerBound || !window.matchMedia) return;
    var query = window.matchMedia('(prefers-color-scheme: dark)');
    var syncFromSystem = function () {
      if (getSavedTheme() === 'system') {
        applyTheme('system');
      }
    };
    if (typeof query.addEventListener === 'function') {
      query.addEventListener('change', syncFromSystem);
      mediaThemeListenerBound = true;
      return;
    }
    if (typeof query.addListener === 'function') {
      query.addListener(syncFromSystem);
      mediaThemeListenerBound = true;
    }
  }

  function ensurePostFormCsrfTokens() {
    var token = getCsrfToken();
    if (!token) return;
    document.querySelectorAll('form[method="post"], form[method="POST"]').forEach(function (form) {
      var existing = form.querySelector('input[name="csrf_token"]');
      if (existing) {
        existing.value = token;
        return;
      }
      var input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'csrf_token';
      input.value = token;
      form.appendChild(input);
    });
  }

  function setupHtmxCsrf() {
    if (typeof document.body.addEventListener !== 'function') return;
    document.body.addEventListener('htmx:configRequest', function (event) {
      if (!event || !event.detail || !event.detail.headers) return;
      var token = getCsrfToken();
      if (!token) return;
      event.detail.headers['X-CSRF-Token'] = token;
    });
  }

  function setupHtmxDebugLogging() {
    if (typeof document.body.addEventListener !== 'function') return;
    document.body.addEventListener('htmx:targetError', function (event) {
      if (!event) return;
      var detail = event.detail || {};
      var issue = detail.target || detail.targetSpec || detail.elt || 'unknown target';
      var sourceEl = detail.elt || event.target || null;
      var requestPath = sourceEl && sourceEl.getAttribute ? sourceEl.getAttribute('hx-get') || sourceEl.getAttribute('hx-post') || sourceEl.getAttribute('hx-put') || sourceEl.getAttribute('hx-delete') || '' : '';

      console.error('[htmx:targetError] Swap target not found.', {
        issue: issue,
        requestPath: requestPath,
        sourceElement: sourceEl,
        detail: detail
      });
    });
  }

  function setupConfirmDialog() {
    var dialog = document.querySelector('[data-confirm-dialog]');
    if (!dialog) return;

    var messageNode = dialog.querySelector('[data-confirm-dialog-message]');
    var confirmButton = dialog.querySelector('[data-confirm-dialog-confirm]');
    var cancelButton = dialog.querySelector('[data-confirm-dialog-cancel]');
    if (!messageNode || !confirmButton || !cancelButton) return;

    var pendingAction = null;

    function clearPending() {
      pendingAction = null;
    }

    function openConfirm(message, onConfirm) {
      messageNode.textContent = message || 'Are you sure?';
      pendingAction = onConfirm;
      if (!dialog.open) {
        dialog.showModal();
      }
    }

    confirmButton.addEventListener('click', function () {
      var action = pendingAction;
      clearPending();
      dialog.close();
      if (typeof action === 'function') {
        action();
      }
    });

    cancelButton.addEventListener('click', function () {
      clearPending();
      dialog.close();
    });

    dialog.addEventListener('close', function () {
      clearPending();
    });

    document.addEventListener('click', function (event) {
      var submitter = event.target.closest('button[type="submit"][data-confirm-message], input[type="submit"][data-confirm-message]');
      if (!submitter) return;

      var form = submitter.form;
      if (!form) return;

      if (form.dataset.confirmBypass === '1') {
        form.dataset.confirmBypass = '0';
        return;
      }

      event.preventDefault();
      var message = submitter.getAttribute('data-confirm-message') || form.getAttribute('data-confirm-message') || 'Are you sure?';
      openConfirm(message, function () {
        form.dataset.confirmBypass = '1';
        if (typeof form.requestSubmit === 'function') {
          form.requestSubmit(submitter);
        } else {
          form.submit();
        }
      });
    });

    document.addEventListener('submit', function (event) {
      var form = event.target;
      if (!form || form.tagName !== 'FORM') return;
      if (!form.hasAttribute('data-confirm-message')) return;

      if (form.dataset.confirmBypass === '1') {
        form.dataset.confirmBypass = '0';
        return;
      }

      event.preventDefault();
      var message = form.getAttribute('data-confirm-message') || 'Are you sure?';
      openConfirm(message, function () {
        form.dataset.confirmBypass = '1';
        if (typeof form.requestSubmit === 'function') {
          form.requestSubmit();
        } else {
          form.submit();
        }
      });
    }, true);
  }

  // ==========================================================================
  // Seed Generation
  // ==========================================================================

  function setupSeedButtons() {
    document.querySelectorAll('[data-random-seed-btn]').forEach(function (button) {
      button.addEventListener('click', function () {
        var targetId = button.getAttribute('data-seed-target');
        if (!targetId) return;
        var input = document.getElementById(targetId);
        if (!input) return;
        input.value = String(randomInt(1, 2147483646));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      });
    });
  }

  // ==========================================================================
  // Model Loading
  // ==========================================================================

  /**
   * Load models from API for a given provider
   */
  async function loadModels(providerSelect) {
    if (!providerSelect) return;
    var provider = providerSelect.value;
    var modelInputId = providerSelect.getAttribute('data-model-input-id');
    var modelListId = providerSelect.getAttribute('data-model-list-id');
    var modelStatusId = providerSelect.getAttribute('data-model-status-id');
    var modelInput = modelInputId ? document.getElementById(modelInputId) : null;
    var modelList = modelListId ? document.getElementById(modelListId) : null;
    var modelStatus = modelStatusId ? document.getElementById(modelStatusId) : null;
    if (!provider || !modelList) return;

    if (modelStatus) {
      modelStatus.textContent = 'Loading models...';
    }
    modelList.innerHTML = '';

    try {
      var response = await fetch('/api/providers/' + encodeURIComponent(provider) + '/models');
      var payload = await response.json();
      var models = Array.isArray(payload.models) ? payload.models : [];

      models.forEach(function (item) {
        var option = document.createElement('option');
        option.value = String(item);
        modelList.appendChild(option);
      });

      if (modelInput && !modelInput.value.trim() && models.length > 0) {
        modelInput.value = String(models[0]);
      }

      if (modelStatus) {
        if (payload.error) {
          modelStatus.textContent = 'Model API error: ' + payload.error;
        } else {
          modelStatus.textContent = models.length > 0
            ? 'Loaded ' + models.length + ' model(s) from API.'
            : 'No models returned by API. Free input remains possible.';
        }
      }
    } catch (_error) {
      if (modelStatus) {
        modelStatus.textContent = 'Failed to load models. Free input remains possible.';
      }
    }
  }

  function setupModelSelects() {
    document.querySelectorAll('[data-provider-select]').forEach(function (select) {
      select.addEventListener('change', function () {
        loadModels(select);
      });
      loadModels(select);
    });

    document.querySelectorAll('[data-load-models-btn]').forEach(function (button) {
      button.addEventListener('click', function () {
        var selectId = button.getAttribute('data-provider-select-id');
        var providerSelect = selectId ? document.getElementById(selectId) : null;
        loadModels(providerSelect);
      });
    });
  }

  // ==========================================================================
  // Generation Form
  // ==========================================================================

  // Module-level reference to the active generation form's addImageFromAsset handler,
  // set by setupGenerationForm so the document-level listener can call it.
  var _addImageFromAsset = null;

  /**
   * Sync dimension preset with width/height inputs
   */
  function syncDimensionPreset(widthInput, heightInput, dimensionPreset) {
    if (!widthInput || !heightInput || !dimensionPreset) return;
    var width = widthInput.value.trim();
    var height = heightInput.value.trim();
    if (!width || !height) {
      dimensionPreset.value = '';
      return;
    }
    var combined = width + 'x' + height;
    var hasMatch = Array.from(dimensionPreset.options).some(function (option) {
      return option.value === combined;
    });
    dimensionPreset.value = hasMatch ? combined : '';
  }

  /**
   * Setup generation form functionality
   */
  function setupGenerationForm(form) {
    var profileSelect = form.querySelector('[data-generation-profile]');
    if (!profileSelect) return;
    var conversationInput = form.querySelector('[name="conversation"]');

    var widthInput = form.querySelector('[name="width"]');
    var heightInput = form.querySelector('[name="height"]');
    var imagesInput = form.querySelector('[name="n_images"]');
    var seedInput = form.querySelector('[name="seed"]');
    var dimensionPreset = form.querySelector('[data-dimension-preset]');
    var inputImages = form.querySelector('[data-input-images]');
    var inputPreview = form.querySelector('[data-input-preview]');
    var inputClear = form.querySelector('[data-input-clear]');
    var inputTrigger = form.querySelector('[data-input-trigger]');
    var inputFileState = [];
    var canUseDataTransfer = false;
    try {
      canUseDataTransfer = typeof DataTransfer !== 'undefined' && !!new DataTransfer();
    } catch (_error) {
      canUseDataTransfer = false;
    }
    var enhanceBtn = form.querySelector('[data-enhance-prompt]');
    var promptInput = form.querySelector('[name="prompt_user"]');
    var advancedToggle = form.querySelector('[data-advanced-toggle]');
    var advancedPanel = form.querySelector('[data-advanced-panel]');
    var submitBtn = form.querySelector('[data-generate-submit]');
    var _generationLocked = false;
    var PROFILE_SESSION_KEY_PREFIX = 'lumigen_selected_profile:';

    function getConversationKey() {
      if (!conversationInput) return '';
      return String(conversationInput.value || '').trim();
    }

    function getProfileSessionStorageKey() {
      var conversationKey = getConversationKey();
      if (!conversationKey) return '';
      return PROFILE_SESSION_KEY_PREFIX + conversationKey;
    }

    function saveSelectedProfileToSession() {
      var storageKey = getProfileSessionStorageKey();
      if (!storageKey) return;
      var profileId = String(profileSelect.value || '').trim();
      if (!profileId) return;
      try {
        sessionStorage.setItem(storageKey, profileId);
      } catch (_error) {
        // Ignore storage write failures in restricted browser modes.
      }
    }

    function restoreSelectedProfileFromSession() {
      var storageKey = getProfileSessionStorageKey();
      if (!storageKey) return false;
      var storedProfileId = '';
      try {
        storedProfileId = String(sessionStorage.getItem(storageKey) || '').trim();
      } catch (_error) {
        return false;
      }
      if (!storedProfileId || profileSelect.value === storedProfileId) {
        return false;
      }
      var hasOption = Array.from(profileSelect.options).some(function (option) {
        return option.value === storedProfileId;
      });
      if (!hasOption) return false;
      profileSelect.value = storedProfileId;
      return true;
    }

    function lockGenerationForm() {
      /* Disable the submit button, show a loading spinner, and set the
         textarea to readonly to prevent duplicate submissions while a
         generation request is in flight. */
      _generationLocked = true;
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.setAttribute('aria-busy', 'true');
        var icon = submitBtn.querySelector('.bi');
        if (icon) {
          icon.classList.remove('bi-arrow-up');
          icon.classList.add('bi-hourglass-split', 'animate-spin');
        }
      }
      if (promptInput) {
        promptInput.setAttribute('readonly', '');
      }
    }

    function unlockGenerationForm() {
      /* Re-enable the submit button, restore the arrow-up icon, and remove
         readonly from the textarea after a generation request completes
         (whether it succeeded or failed). */
      _generationLocked = false;
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.removeAttribute('aria-busy');
        var icon = submitBtn.querySelector('.bi');
        if (icon) {
          icon.classList.remove('bi-hourglass-split', 'animate-spin');
          icon.classList.add('bi-arrow-up');
        }
      }
      if (promptInput) {
        promptInput.removeAttribute('readonly');
      }
    }

    function syncProviderSpecificOptions(selected) {
      var provider = selected ? String(selected.dataset.provider || '').trim().toLowerCase() : '';
      var isOpenRouter = provider === 'openrouter';
      var isFal = provider === 'fal';
      var isGoogle = provider === 'google';
      var useCustomDimensions = !isOpenRouter && !isFal && !isGoogle;
      
      var dimensionControls = form.querySelector('[data-dimension-controls]');
      var standardDimensions = form.querySelector('[data-standard-dimensions]');
      var openrouterControls = form.querySelector('[data-openrouter-controls]');
      var falControls = form.querySelector('[data-fal-controls]');
      var googleControls = form.querySelector('[data-google-controls]');
      var aspectRatioInput = form.querySelector('[name="aspect_ratio"]');
      var imageSizeInput = form.querySelector('[name="image_size"]');
      var falAspectRatioInput = form.querySelector('[name="fal_aspect_ratio"]');
      var falResolutionInput = form.querySelector('[name="fal_resolution"]');
      var googleAspectRatioInput = form.querySelector('[name="google_aspect_ratio"]');
      var googleResolutionInput = form.querySelector('[name="google_resolution"]');
      
      // Toggle visibility based on provider
      if (dimensionControls) {
        dimensionControls.classList.toggle('hidden', !useCustomDimensions);
      }
      if (standardDimensions) {
        standardDimensions.classList.toggle('hidden', !useCustomDimensions);
      }
      if (openrouterControls) {
        openrouterControls.classList.toggle('hidden', !isOpenRouter);
      }
      if (falControls) {
        falControls.classList.toggle('hidden', !isFal);
      }
      if (googleControls) {
        googleControls.classList.toggle('hidden', !isGoogle);
      }
      
      // Disable/enable and clear values based on provider
      if (widthInput) {
        widthInput.disabled = !useCustomDimensions;
        if (!useCustomDimensions) widthInput.value = '';
      }
      if (heightInput) {
        heightInput.disabled = !useCustomDimensions;
        if (!useCustomDimensions) heightInput.value = '';
      }
      if (dimensionPreset) {
        dimensionPreset.disabled = !useCustomDimensions;
        if (!useCustomDimensions) {
          dimensionPreset.value = '';
        }
      }
      if (aspectRatioInput) {
        aspectRatioInput.disabled = !isOpenRouter;
        if (!isOpenRouter) aspectRatioInput.value = '';
      }
      if (imageSizeInput) {
        imageSizeInput.disabled = !isOpenRouter;
        if (!isOpenRouter) imageSizeInput.value = '';
      }
      if (falAspectRatioInput) {
        falAspectRatioInput.disabled = !isFal;
        if (!isFal) falAspectRatioInput.value = '';
      }
      if (falResolutionInput) {
        falResolutionInput.disabled = !isFal;
        if (!isFal) falResolutionInput.value = '';
      }
      if (googleAspectRatioInput) {
        googleAspectRatioInput.disabled = !isGoogle;
        if (!isGoogle) googleAspectRatioInput.value = '';
      }
      if (googleResolutionInput) {
        googleResolutionInput.disabled = !isGoogle;
        if (!isGoogle) googleResolutionInput.value = '';
      }
      updateGenerationFrame();
    }

    function legacyFalImageSizeToRatio(value) {
      var map = {
        square_hd: '1:1',
        square: '1:1',
        portrait_4_3: '3:4',
        portrait_16_9: '9:16',
        landscape_4_3: '4:3',
        landscape_16_9: '16:9'
      };
      return map[String(value || '').trim()] || '';
    }

    /**
     * Parse a ratio string in "W:H" or "WxH" format.
     * Returns [width, height] as numbers, or null if invalid.
     */
    function parseRatioString(str) {
      if (!str || typeof str !== 'string') return null;
      var parts;
      if (str.indexOf(':') !== -1) {
        parts = str.split(':');
      } else if (str.indexOf('x') !== -1) {
        parts = str.split('x');
      } else {
        return null;
      }
      if (parts.length !== 2) return null;
      var w = parseFloat(parts[0]);
      var h = parseFloat(parts[1]);
      if (isNaN(w) || isNaN(h) || w <= 0 || h <= 0) return null;
      return [w, h];
    }

    /**
     * Derive the active aspect ratio [w, h] from whichever control set is
     * currently visible (FAL, OpenRouter, or standard width/height).
     * Falls back to [1, 1] when no explicit ratio is set.
     */
    function getActiveRatio() {
      var selected = profileSelect.options[profileSelect.selectedIndex];
      var provider = selected ? String(selected.dataset.provider || '').trim().toLowerCase() : '';
      var isFal = provider === 'fal';
      var isOpenRouter = provider === 'openrouter';
      var isGoogle = provider === 'google';

      if (isFal) {
        var falAspectRatioInput = form.querySelector('[name="fal_aspect_ratio"]');
        var falVal = falAspectRatioInput ? falAspectRatioInput.value.trim() : '';
        if (falVal && falVal !== 'auto') {
          return parseRatioString(falVal) || [1, 1];
        }
        return [1, 1];
      }

      if (isOpenRouter) {
        var aspectRatioInput = form.querySelector('[name="aspect_ratio"]');
        var orVal = aspectRatioInput ? aspectRatioInput.value.trim() : '';
        if (orVal) {
          return parseRatioString(orVal) || [1, 1];
        }
        return [1, 1];
      }

      if (isGoogle) {
        var googleAspectRatioInput = form.querySelector('[name="google_aspect_ratio"]');
        var gVal = googleAspectRatioInput ? googleAspectRatioInput.value.trim() : '';
        if (gVal) {
          return parseRatioString(gVal) || [1, 1];
        }
        return [1, 1];
      }

      var wVal = widthInput ? parseFloat(widthInput.value) : 0;
      var hVal = heightInput ? parseFloat(heightInput.value) : 0;
      if (wVal > 0 && hVal > 0) return [wVal, hVal];
      return [1, 1];
    }

    /**
     * Update the generation frame element to reflect the currently active
     * aspect ratio.  The frame is constrained to a 112 px maximum in either
     * dimension so extreme ratios (e.g. 21:9 or 1:8) stay within their
     * container.
     */
    function updateGenerationFrame() {
      var frame = form.querySelector('[data-generation-frame]');
      if (!frame) return;
      var MAX = 112;
      var ratio = getActiveRatio();
      var w = ratio[0];
      var h = ratio[1];
      if (w <= 0 || h <= 0) { w = 1; h = 1; }
      var displayW, displayH;
      if (w >= h) {
        displayW = MAX;
        displayH = Math.max(1, Math.round(MAX * h / w));
      } else {
        displayH = MAX;
        displayW = Math.max(1, Math.round(MAX * w / h));
      }
      frame.style.width = displayW + 'px';
      frame.style.height = displayH + 'px';
      frame.style.aspectRatio = w + ' / ' + h;
    }

    function applyProfileDefaults() {
      var selected = profileSelect.options[profileSelect.selectedIndex];
      if (!selected) return;

      if (widthInput) widthInput.value = selected.dataset.width || '';
      if (heightInput) heightInput.value = selected.dataset.height || '';
      if (imagesInput) imagesInput.value = selected.dataset.nImages || '';
      if (seedInput) seedInput.value = selected.dataset.seed || '';

      var falAspectRatioInput = form.querySelector('[name="fal_aspect_ratio"]');
      var falResolutionInput = form.querySelector('[name="fal_resolution"]');
      if (falAspectRatioInput) {
        var ratio = String(selected.dataset.falAspectRatio || '').trim();
        if (!ratio) {
          ratio = legacyFalImageSizeToRatio(selected.dataset.falImageSize || '');
        }
        falAspectRatioInput.value = ratio;
      }
      if (falResolutionInput) {
        falResolutionInput.value = String(selected.dataset.falResolution || '').trim();
      }
      var googleAspectRatioInput = form.querySelector('[name="google_aspect_ratio"]');
      var googleResolutionInput = form.querySelector('[name="google_resolution"]');
      if (googleAspectRatioInput) {
        googleAspectRatioInput.value = String(selected.dataset.googleAspectRatio || '').trim();
      }
      if (googleResolutionInput) {
        googleResolutionInput.value = String(selected.dataset.googleResolution || '').trim();
      }

      syncProviderSpecificOptions(selected);

      syncDimensionPreset(widthInput, heightInput, dimensionPreset);
      saveSelectedProfileToSession();
    }

    profileSelect.addEventListener('change', applyProfileDefaults);

    if (!profileSelect.dataset.restoreBound) {
      profileSelect.dataset.restoreBound = '1';
      var restoreProfileSelection = function () {
        if (restoreSelectedProfileFromSession()) {
          applyProfileDefaults();
        }
      };
      window.addEventListener('focus', restoreProfileSelection);
      window.addEventListener('pageshow', restoreProfileSelection);
      document.addEventListener('visibilitychange', function () {
        if (!document.hidden) {
          restoreProfileSelection();
        }
      });
    }
    
    restoreSelectedProfileFromSession();
    // Call on initial page load to ensure correct visibility
    applyProfileDefaults();

    if (dimensionPreset && widthInput && heightInput) {
      dimensionPreset.addEventListener('change', function () {
        var value = dimensionPreset.value.trim();
        if (!value) return;
        var parts = value.split('x');
        if (parts.length !== 2) return;
        widthInput.value = parts[0].trim();
        heightInput.value = parts[1].trim();
        syncDimensionPreset(widthInput, heightInput, dimensionPreset);
        updateGenerationFrame();
      });

      widthInput.addEventListener('input', function () {
        syncDimensionPreset(widthInput, heightInput, dimensionPreset);
        updateGenerationFrame();
      });
      heightInput.addEventListener('input', function () {
        syncDimensionPreset(widthInput, heightInput, dimensionPreset);
        updateGenerationFrame();
      });
    }

    var aspectRatioSelect = form.querySelector('[name="aspect_ratio"]');
    if (aspectRatioSelect) {
      aspectRatioSelect.addEventListener('change', updateGenerationFrame);
    }

    var falAspectRatioSelect = form.querySelector('[name="fal_aspect_ratio"]');
    if (falAspectRatioSelect) {
      falAspectRatioSelect.addEventListener('change', updateGenerationFrame);
    }

    var googleAspectRatioSelect = form.querySelector('[name="google_aspect_ratio"]');
    if (googleAspectRatioSelect) {
      googleAspectRatioSelect.addEventListener('change', updateGenerationFrame);
    }

    function syncInputFiles() {
      if (!inputImages) return;
      if (!canUseDataTransfer) {
        return false;
      }
      try {
        var dataTransfer = new DataTransfer();
        inputFileState.forEach(function (file) {
          dataTransfer.items.add(file);
        });
        inputImages.files = dataTransfer.files;
        return true;
      } catch (_error) {
        canUseDataTransfer = false;
        return false;
      }
    }

    function renderInputPreviews() {
      if (!inputImages || !inputPreview) return;
      inputPreview.innerHTML = '';

      var selectedCount = canUseDataTransfer
        ? inputFileState.length
        : Array.from(inputImages.files || []).length;

      if (selectedCount > 5) {
        inputImages.setCustomValidity('Max 5 images allowed.');
      } else {
        inputImages.setCustomValidity('');
      }

      if (inputClear) {
        inputClear.disabled = inputFileState.length === 0;
      }

      inputFileState.slice(0, 5).forEach(function (file, index) {
        var objectUrl = URL.createObjectURL(file);
        var wrapper = document.createElement('div');
        wrapper.className = 'relative h-20 w-20 overflow-hidden rounded-xl border border-slate-300/55 bg-white/95 shadow-md shadow-slate-200/60 dark:border-white/15 dark:bg-slate-900/80 dark:shadow-slate-950/60';
        var img = document.createElement('img');
        img.src = objectUrl;
        img.alt = file.name || 'input image';
        img.className = 'h-full w-full object-cover';
        img.addEventListener('load', function () {
          URL.revokeObjectURL(objectUrl);
        });
        var removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'absolute right-1 top-1 inline-flex h-5 w-5 items-center justify-center rounded-full border border-slate-300/85 bg-rose-500/90 text-[11px] font-bold text-slate-900 transition hover:border-rose-200 hover:bg-rose-500/80 dark:border-white/35 dark:bg-slate-900/90 dark:text-white dark:hover:border-rose-200 dark:hover:bg-rose-500/80';
        removeBtn.textContent = 'x';
        if (!canUseDataTransfer) {
          removeBtn.disabled = true;
          removeBtn.title = 'Use clear button to remove images';
          removeBtn.classList.add('opacity-40', 'cursor-not-allowed');
        }
        removeBtn.addEventListener('click', function () {
          if (!canUseDataTransfer) return;
          inputFileState.splice(index, 1);
          syncInputFiles();
          renderInputPreviews();
        });
        wrapper.appendChild(img);
        wrapper.appendChild(removeBtn);
        inputPreview.appendChild(wrapper);
      });
    }

    function addSelectedFiles(fileList) {
      var incoming = Array.from(fileList || []);
      if (incoming.length === 0) return;

      incoming.forEach(function (file) {
        var isDuplicate = inputFileState.some(function (existing) {
          return existing.name === file.name
            && existing.size === file.size
            && existing.lastModified === file.lastModified;
        });
        if (!isDuplicate) {
          inputFileState.push(file);
        }
      });

      if (inputFileState.length > 5) {
        inputFileState = inputFileState.slice(0, 5);
      }

      syncInputFiles();
      renderInputPreviews();
    }

    if (inputImages) {
      inputImages.addEventListener('change', function () {
        if (!canUseDataTransfer) {
          inputFileState = Array.from(inputImages.files || []).slice(0, 5);
          renderInputPreviews();
          return;
        }
        var nativeSelectedFiles = Array.from(inputImages.files || []);
        addSelectedFiles(nativeSelectedFiles);

        if (canUseDataTransfer) {
          // Keep files assigned to the input for submit.
        } else {
          inputFileState = nativeSelectedFiles.slice(0, 5);
          renderInputPreviews();
        }
      });
      renderInputPreviews();
    }

    if (inputTrigger && inputImages) {
      inputTrigger.addEventListener('click', function () {
        if (canUseDataTransfer) {
          inputImages.value = '';
        }
        inputImages.click();
      });
    }

    if (inputClear) {
      inputClear.addEventListener('click', function () {
        inputFileState = [];
        if (canUseDataTransfer) {
          syncInputFiles();
        } else if (inputImages) {
          inputImages.value = '';
        }
        renderInputPreviews();
      });
    }

    async function addImageFromAsset(assetId) {
      if (inputFileState.length >= 5) return;
      try {
        var response = await fetch('/assets/' + encodeURIComponent(assetId) + '/file');
        if (!response.ok) return;
        var blob = await response.blob();
        var mime = blob.type || 'image/webp';
        var mimeToExt = { 'image/webp': 'webp', 'image/png': 'png', 'image/jpeg': 'jpg', 'image/gif': 'gif' };
        var ext = mimeToExt[mime] || 'webp';
        var filename = 'asset_' + assetId + '.' + ext;
        var isDuplicate = inputFileState.some(function (f) { return f.name === filename; });
        if (isDuplicate) return;
        var file = new File([blob], filename, { type: mime });
        inputFileState.push(file);
        if (inputFileState.length > 5) {
          inputFileState = inputFileState.slice(0, 5);
        }
        syncInputFiles();
        renderInputPreviews();
      } catch (_error) {
        // Silently ignore fetch errors
      }
    }

    _addImageFromAsset = addImageFromAsset;

    if (advancedToggle && advancedPanel) {
      function syncAdvancedState() {
        var expanded = !advancedPanel.classList.contains('hidden');
        advancedToggle.textContent = expanded ? '-' : '+';
        advancedToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
      }
      advancedToggle.addEventListener('click', function () {
        advancedPanel.classList.toggle('hidden');
        syncAdvancedState();
      });
      syncAdvancedState();
    }

    if (promptInput) {
      promptInput.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter') return;
        if (event.shiftKey) return;
        if (event.isComposing || event.keyCode === 229) return;
        if (_generationLocked) {
          event.preventDefault();
          return;
        }
        event.preventDefault();
        if (typeof form.requestSubmit === 'function') {
          form.requestSubmit();
        } else {
          form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        }
      });
    }

    if (enhanceBtn && promptInput) {
      enhanceBtn.addEventListener('click', async function () {
        var selected = profileSelect.options[profileSelect.selectedIndex];
        var modelConfigId = selected ? selected.dataset.modelConfigId : '';
        var promptValue = promptInput.value.trim();
        if (!promptValue) return;

        enhanceBtn.disabled = true;
        enhanceBtn.setAttribute('aria-busy', 'true');
        var enhanceIcon = enhanceBtn.querySelector('.bi');
        if (enhanceIcon) {
          enhanceIcon.classList.add('animate-pulse');
        }

        try {
          var response = await fetch('/api/enhance', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRF-Token': getCsrfToken()
            },
            body: JSON.stringify({
              prompt: promptValue,
              model_config_id: modelConfigId ? Number(modelConfigId) : null
            })
          });
          var payload = await response.json();
          if (payload && payload.prompt) {
            promptInput.value = payload.prompt;
          } else if (payload && payload.error) {
            alert(payload.error);
          }
        } catch (_error) {
          alert('Enhancement failed.');
        } finally {
          enhanceBtn.disabled = false;
          enhanceBtn.removeAttribute('aria-busy');
          if (enhanceIcon) {
            enhanceIcon.classList.remove('animate-pulse');
          }
        }
      });
    }

    form.addEventListener('submit', function (event) {
      if (_generationLocked) {
        event.preventDefault();
        event.stopImmediatePropagation();
        return;
      }
      lockGenerationForm();
    });

    form.addEventListener('htmx:afterRequest', function () {
      unlockGenerationForm();
    });

    applyProfileDefaults();
  }

  function setupGenerationForms() {
    document.querySelectorAll('[data-generation-form]').forEach(setupGenerationForm);
  }

  // ==========================================================================
  // Profile Form
  // ==========================================================================

  function setupProfileForm(form) {
    if (!form) return;
    var modelSelect = form.querySelector('[data-profile-model-select]');
    if (!modelSelect) return;

    var dimensionsSection = form.querySelector('[data-profile-dimensions]');
    var widthInput = form.querySelector('[name="width"]');
    var heightInput = form.querySelector('[name="height"]');
    var openrouterSection = form.querySelector('[data-profile-openrouter]');
    var openrouterRatio = form.querySelector('[data-profile-openrouter-ratio]');
    var openrouterSize = form.querySelector('[data-profile-openrouter-size]');
    var falSection = form.querySelector('[data-profile-fal]');
    var falAspectRatio = form.querySelector('[name="fal_aspect_ratio"]');
    var falResolution = form.querySelector('[name="fal_resolution"]');

    function syncProfileProviderState() {
      var selected = modelSelect.options[modelSelect.selectedIndex];
      var provider = selected ? String(selected.dataset.provider || '').trim().toLowerCase() : '';
      var isOpenRouter = provider === 'openrouter';
      var isFal = provider === 'fal';
      var showDimensions = !isOpenRouter && !isFal;

      if (dimensionsSection) {
        dimensionsSection.classList.toggle('hidden', !showDimensions);
      }
      if (widthInput) {
        widthInput.disabled = !showDimensions;
        if (!showDimensions) widthInput.value = '';
      }
      if (heightInput) {
        heightInput.disabled = !showDimensions;
        if (!showDimensions) heightInput.value = '';
      }

      if (openrouterSection) {
        openrouterSection.classList.toggle('hidden', !isOpenRouter);
      }
      if (openrouterRatio) {
        openrouterRatio.disabled = !isOpenRouter;
        if (!isOpenRouter) openrouterRatio.value = '';
      }
      if (openrouterSize) {
        openrouterSize.disabled = !isOpenRouter;
        if (!isOpenRouter) openrouterSize.value = '';
      }

      if (falSection) {
        falSection.classList.toggle('hidden', !isFal);
      }
      if (falAspectRatio) {
        falAspectRatio.disabled = !isFal;
        if (!isFal) falAspectRatio.value = '';
      }
      if (falResolution) {
        falResolution.disabled = !isFal;
        if (!isFal) falResolution.value = '';
      }
    }

    modelSelect.addEventListener('change', syncProfileProviderState);
    syncProfileProviderState();
  }

  function setupProfileForms() {
    document.querySelectorAll('[data-profile-form]').forEach(setupProfileForm);
  }

  // ==========================================================================
  // Gallery Filter Persistence (localStorage)
  // ==========================================================================

  var GALLERY_FILTER_KEY = 'lumigen_gallery_filters';
  var GALLERY_THUMB_SIZE_KEY = 'lumigen_gallery_thumb_size';

  /**
   * Load gallery filters from localStorage and apply to form
   */
  function loadGalleryFilters() {
    try {
      var stored = localStorage.getItem(GALLERY_FILTER_KEY);
      if (!stored) return;
      var filters = JSON.parse(stored);
      if (!filters || typeof filters !== 'object') return;

      // Apply to select inputs
      ['profile_name', 'provider', 'q', 'time_preset', 'date_from', 'date_to', 'min_rating'].forEach(function (name) {
        var selectEl = document.querySelector('form[action="/gallery"] [name="' + name + '"]');
        if (selectEl && filters[name]) {
          selectEl.value = filters[name];
        }
      });

      var unrated = document.querySelector('form[action="/gallery"] [name="unrated"]');
      if (unrated) {
        unrated.checked = filters.unrated === true || filters.unrated === '1';
      }

      // Apply to category checkboxes
      if (filters.category_ids && Array.isArray(filters.category_ids)) {
        filters.category_ids.forEach(function (catId) {
          var checkbox = document.querySelector('form[action="/gallery"] input[name="category_ids"][value="' + catId + '"]');
          if (checkbox) {
            checkbox.checked = true;
          }
        });
      }

    } catch (_e) {
      // Ignore localStorage errors
    }
  }

  /**
   * Save current gallery filters to localStorage
   */
  function saveGalleryFilters() {
    try {
      var form = document.querySelector('form[action="/gallery"]');
      if (!form) return;

      var filters = {};

      // Save select inputs
      ['profile_name', 'provider', 'q', 'time_preset', 'date_from', 'date_to', 'min_rating'].forEach(function (name) {
        var selectEl = form.querySelector('[name="' + name + '"]');
        if (selectEl && selectEl.value) {
          filters[name] = selectEl.value;
        }
      });

      var unrated = form.querySelector('[name="unrated"]');
      if (unrated && unrated.checked) {
        filters.unrated = '1';
      }

      // Save category checkboxes
      var checkedCategories = [];
      form.querySelectorAll('input[name="category_ids"]:checked').forEach(function (checkbox) {
        var val = parseInt(checkbox.value, 10);
        if (!isNaN(val)) {
          checkedCategories.push(val);
        }
      });
      if (checkedCategories.length > 0) {
        filters.category_ids = checkedCategories;
      }

      localStorage.setItem(GALLERY_FILTER_KEY, JSON.stringify(filters));
    } catch (_e) {
      // Ignore localStorage errors
    }
  }

  /**
   * Save thumb size preference to localStorage
   */
  function saveGalleryThumbSize(size) {
    try {
      if (size && ['sm', 'md', 'lg'].indexOf(size) !== -1) {
        localStorage.setItem(GALLERY_THUMB_SIZE_KEY, size);
      }
    } catch (_e) {
      // Ignore localStorage errors
    }
  }

  /**
   * Update the category filter label to show selection count
   */
  function updateCategoryLabel() {
    var form = document.querySelector('form[action="/gallery"]');
    if (!form) return;

    var checkedCount = form.querySelectorAll('input[name="category_ids"]:checked').length;
    var labelSpan = form.querySelector('[data-category-popover-toggle] span:nth-child(2)');
    if (labelSpan) {
      if (checkedCount > 0) {
        labelSpan.textContent = checkedCount + ' selected';
      } else {
        labelSpan.textContent = 'All categories';
      }
    }
  }

  /**
   * Setup gallery filter persistence
   */
  function setupGalleryFilters() {
    var form = document.querySelector('form[action="/gallery"]');
    if (!form) return;
    var params = new URLSearchParams(window.location.search);
    var autoSubmitTimer = null;

    function hasAnyExplicitFilter() {
      var filterKeys = [
        'profile_name',
        'provider',
        'q',
        'category_ids',
        'min_rating',
        'unrated',
        'time_preset',
        'date_from',
        'date_to'
      ];
      return filterKeys.some(function (key) {
        return params.has(key);
      });
    }

    // If no timeframe is explicitly present in the URL, restore and apply stored timeframe.
    try {
      var hasExplicitTime = params.has('time_preset') || params.has('date_from') || params.has('date_to');
      if (!hasExplicitTime) {
        var storedRaw = localStorage.getItem(GALLERY_FILTER_KEY);
        if (storedRaw) {
          var stored = JSON.parse(storedRaw);
          if (stored && typeof stored === 'object') {
            var shouldRedirect = false;

            if (stored.time_preset) {
              params.set('time_preset', stored.time_preset);
              shouldRedirect = true;
            }
            if (stored.date_from) {
              params.set('date_from', stored.date_from);
              shouldRedirect = true;
            }
            if (stored.date_to) {
              params.set('date_to', stored.date_to);
              shouldRedirect = true;
            }

            if (shouldRedirect) {
              var qs = params.toString();
              window.location.href = window.location.pathname + (qs ? '?' + qs : '');
              return;
            }
          }
        }
      }
    } catch (_e) {
      // Ignore localStorage/query parsing errors
    }

    // Only hydrate from localStorage when URL does not already carry explicit filters.
    if (!hasAnyExplicitFilter()) {
      loadGalleryFilters();
    }
    updateCategoryLabel();

    var resetLink = form.querySelector('[data-gallery-reset]');
    if (resetLink) {
      resetLink.addEventListener('click', function () {
        try {
          localStorage.removeItem(GALLERY_FILTER_KEY);
        } catch (_e) {
          // Ignore localStorage errors
        }
      });
    }

    var preset = form.querySelector('[name="time_preset"]');
    var dateFrom = form.querySelector('[name="date_from"]');
    var dateTo = form.querySelector('[name="date_to"]');
    var customFields = form.querySelector('[data-time-custom-fields]');

    function syncTimeFilterUi() {
      if (!preset || !dateFrom || !dateTo) return;
      var isCustom = preset.value === 'custom';
      if (customFields) {
        customFields.classList.toggle('hidden', !isCustom);
      }
      if (!isCustom) {
        if (dateFrom.value || dateTo.value) {
          dateFrom.value = '';
          dateTo.value = '';
        }
      }
      if (!preset.value) {
        preset.value = 'today';
      }
    }

    if (preset && dateFrom && dateTo) {
      preset.addEventListener('change', syncTimeFilterUi);

      dateFrom.addEventListener('change', function () {
        if (dateFrom.value || dateTo.value) {
          preset.value = 'custom';
        }
        syncTimeFilterUi();
      });
      dateTo.addEventListener('change', function () {
        if (dateFrom.value || dateTo.value) {
          preset.value = 'custom';
        }
        syncTimeFilterUi();
      });
      syncTimeFilterUi();
    }

    function submitGalleryFilters() {
      saveGalleryFilters();
      if (typeof form.requestSubmit === 'function') {
        form.requestSubmit();
      } else {
        form.submit();
      }
    }

    function submitGalleryFiltersDebounced(delayMs) {
      if (autoSubmitTimer) {
        clearTimeout(autoSubmitTimer);
      }
      autoSubmitTimer = setTimeout(function () {
        submitGalleryFilters();
      }, delayMs);
    }

    var autoApplyOnChange = ['profile_name', 'provider', 'min_rating', 'time_preset', 'unrated', 'date_from', 'date_to'];
    autoApplyOnChange.forEach(function (name) {
      var field = form.querySelector('[name="' + name + '"]');
      if (!field) return;
      field.addEventListener('change', function () {
        submitGalleryFilters();
      });
    });

    var promptQueryInput = form.querySelector('[name="q"]');
    if (promptQueryInput) {
      promptQueryInput.addEventListener('input', function () {
        submitGalleryFiltersDebounced(350);
      });
    }

    // Save filters on form submit
    form.addEventListener('submit', function () {
      saveGalleryFilters();
    });

    // Save filters when category checkboxes change
    form.querySelectorAll('input[name="category_ids"]').forEach(function (checkbox) {
      checkbox.addEventListener('change', function () {
        updateCategoryLabel();
        submitGalleryFilters();
      });
    });

    // Save thumb size when size buttons are clicked
    form.querySelectorAll('[data-gallery-thumb-size]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var size = btn.getAttribute('data-gallery-thumb-size');
        saveGalleryThumbSize(size);
      });
    });
  }

  // ==========================================================================
  // Gallery Selection
  // ==========================================================================

function setupGallerySelection() {
  var panel = document.querySelector('[data-gallery-selection-panel]');
  var bulkForm = document.getElementById('bulk-action-form');
  if (!panel || !bulkForm) return;

  var countLabel = document.querySelector('[data-gallery-selection-count]');
  var actionButtons = Array.from(document.querySelectorAll('[data-bulk-action]'));
  var deselectAllBtn = document.querySelector('[data-gallery-deselect-all]');

  // Map of assetId -> hidden input element for form submission
  var hiddenInputs = {};

  function createOrUpdateHiddenInput(assetId, checked) {
    var inputName = 'asset_ids';
    if (checked) {
      if (!hiddenInputs[assetId]) {
        var input = document.createElement('input');
        input.type = 'hidden';
        input.name = inputName;
        input.value = assetId;
        bulkForm.appendChild(input);
        hiddenInputs[assetId] = input;
      }
    } else {
      if (hiddenInputs[assetId]) {
        hiddenInputs[assetId].remove();
        delete hiddenInputs[assetId];
      }
    }
  }

  function updateState() {
    var selected = Object.keys(hiddenInputs).length;

    if (countLabel) {
      countLabel.textContent = selected + ' selected';
    }

    // Show or hide the floating panel
    panel.classList.toggle('hidden', selected === 0);

    actionButtons.forEach(function (button) {
      button.disabled = selected === 0;
    });
  }

  // Use event delegation so newly loaded cards (infinite scroll) are handled automatically
  document.addEventListener('click', function (e) {
    var clickArea = e.target.closest('[data-gallery-card-click]');
    if (!clickArea) return;

    var target = e.target;
    if (target.closest('a') || target.closest('button') || target.closest('form')) {
      return;
    }

    var card = clickArea.closest('[data-gallery-card]');
    if (!card) return;

    var assetId = card.dataset.assetId;
    var isSelected = card.dataset.selected === 'true';
    card.dataset.selected = (!isSelected).toString();
    createOrUpdateHiddenInput(assetId, !isSelected);
    updateState();
  });

  document.addEventListener('dblclick', function (e) {
    var clickArea = e.target.closest('[data-gallery-card-click]');
    if (!clickArea) return;

    var target = e.target;
    if (target.closest('a') || target.closest('button') || target.closest('form')) {
      return;
    }

    var card = clickArea.closest('[data-gallery-card]');
    if (!card) return;

    var detailTrigger = card.querySelector('[data-asset-detail-trigger]');
    if (detailTrigger) {
      // Reuse the existing HTMX-backed trigger so the standard asset dialog opens.
      detailTrigger.click();
      return;
    }

    var detailUrl = card.dataset.assetDetailUrl;
    if (!detailUrl) return;
    window.location.href = detailUrl;
  });

  // Deselect all button clears selection and hides the panel
  if (deselectAllBtn && deselectAllBtn.dataset.bound !== '1') {
    deselectAllBtn.dataset.bound = '1';
    deselectAllBtn.addEventListener('click', function () {
      document.querySelectorAll('[data-gallery-card][data-selected="true"]').forEach(function (card) {
        card.dataset.selected = 'false';
        createOrUpdateHiddenInput(card.dataset.assetId, false);
      });
      updateState();
    });
  }

  updateState();
}

function setupGalleryRatings() {
  var ratingForms = Array.from(document.querySelectorAll('[data-rating-form]:not([data-ratings-bound])'));
  if (ratingForms.length === 0) return;

  ratingForms.forEach(function (form) {
    form.setAttribute('data-ratings-bound', '1');
    var stars = Array.from(form.querySelectorAll('[data-rating-star]'));
    var ratingInput = form.querySelector('[data-rating-input]');
    if (!ratingInput || stars.length === 0) return;

    var currentRating = parseInt(form.getAttribute('data-current-rating') || '0', 10);
    if (!Number.isFinite(currentRating) || currentRating < 0) {
      currentRating = 0;
    }

    function paintStars(activeRating) {
      stars.forEach(function (star) {
        var value = parseInt(star.getAttribute('data-rating-value') || '0', 10);
        var isActive = Number.isFinite(value) && value <= activeRating;
        star.classList.toggle('text-amber-500', isActive);
        star.classList.toggle('dark:text-amber-300', isActive);
        star.classList.toggle('text-slate-500', !isActive);
        star.classList.toggle('dark:text-slate-600', !isActive);
      });
    }

    paintStars(currentRating);

    stars.forEach(function (star) {
      star.addEventListener('mouseenter', function () {
        var hoverRating = parseInt(star.getAttribute('data-rating-value') || '0', 10);
        if (Number.isFinite(hoverRating)) {
          paintStars(hoverRating);
        }
      });

      star.addEventListener('click', async function () {
        var clickedValue = parseInt(star.getAttribute('data-rating-value') || '0', 10);
        if (!Number.isFinite(clickedValue)) return;

        var nextRating = clickedValue;
        if (clickedValue === 1 && currentRating === 1) {
          nextRating = 0;
        }

        var previousRating = currentRating;
        ratingInput.value = String(nextRating);
        currentRating = nextRating;
        form.setAttribute('data-current-rating', String(currentRating));
        paintStars(currentRating);

        try {
          var formData = new FormData(form);
          var response = await fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
              'X-Requested-With': 'XMLHttpRequest',
              'X-CSRF-Token': getCsrfToken()
            }
          });

          if (!response.ok) {
            throw new Error('Rating update failed');
          }
        } catch (_error) {
          currentRating = previousRating;
          form.setAttribute('data-current-rating', String(currentRating));
          ratingInput.value = String(currentRating);
          paintStars(currentRating);
        }
      });
    });

    form.addEventListener('mouseleave', function () {
      paintStars(currentRating);
    });
  });
}

  // ==========================================================================
  // Chat: Add generated image to prompt input panel
  // ==========================================================================

  function setupChatAddToInput() {
    document.addEventListener('click', function (event) {
      var btn = event.target.closest('[data-add-to-input]');
      if (!btn || !_addImageFromAsset) return;
      var assetId = btn.getAttribute('data-add-to-input');
      if (!assetId) return;
      _addImageFromAsset(assetId);
    });
  }

  // ==========================================================================
  // Chat: Re-Generate from prompt bubble
  // ==========================================================================

  /**
   * Set up the Re-Generate hover button on user prompt bubbles.
   *
   * Uses event delegation so buttons injected via HTMX are handled automatically.
   * On click, fills the generation form textarea with the prompt text and
   * submits the form to start a new generation with the current profile.
   */
  function setupChatRegenerate() {
    document.addEventListener('click', function (event) {
      var btn = event.target.closest('[data-regenerate-prompt]');
      if (!btn) return;
      var promptText = btn.getAttribute('data-regenerate-prompt');
      if (promptText === null) return;

      var form = document.querySelector('[data-generation-form]');
      if (!form) return;

      var promptInput = form.querySelector('[name="prompt_user"]');
      if (!promptInput) return;

      promptInput.value = promptText;
      promptInput.focus();

      if (typeof form.requestSubmit === 'function') {
        form.requestSubmit();
      } else {
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      }
    });
  }

  // ==========================================================================
  // User Menu Popup
  // ==========================================================================

  function setupUserMenu() {
    var settingsDialog = document.querySelector('[data-user-settings-dialog]');
    var settingsCloseButton = settingsDialog ? settingsDialog.querySelector('[data-user-settings-close]') : null;
    var themeSelect = settingsDialog ? settingsDialog.querySelector('[data-user-theme-select]') : null;

    function closeSettingsDialog() {
      if (settingsDialog && settingsDialog.open) {
        settingsDialog.close();
      }
    }

    function openSettingsDialog() {
      if (settingsDialog && !settingsDialog.open) {
        settingsDialog.showModal();
      }
    }

    if (settingsCloseButton && settingsCloseButton.dataset.bound !== '1') {
      settingsCloseButton.dataset.bound = '1';
      settingsCloseButton.addEventListener('click', closeSettingsDialog);
    }

    if (settingsDialog && settingsDialog.dataset.bound !== '1') {
      settingsDialog.dataset.bound = '1';
      settingsDialog.addEventListener('click', function (event) {
        var rect = settingsDialog.getBoundingClientRect();
        var isOutside =
          event.clientX < rect.left ||
          event.clientX > rect.right ||
          event.clientY < rect.top ||
          event.clientY > rect.bottom;
        if (isOutside) {
          closeSettingsDialog();
        }
      });
    }

    if (themeSelect && themeSelect.dataset.bound !== '1') {
      themeSelect.dataset.bound = '1';
      themeSelect.value = getSavedTheme();
      themeSelect.addEventListener('change', function () {
        var selected = 'system';
        if (themeSelect.value === 'light' || themeSelect.value === 'dark') {
          selected = themeSelect.value;
        }
        applyTheme(selected);
        persistTheme(selected);
      });
    }

    document.querySelectorAll('[data-user-menu-container]').forEach(function (container) {
      var settingsButton = container.querySelector('[data-user-settings-open]');

      // Close on Escape key
      document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
          if (container && container.open) {
            container.open = false;
          }
          closeSettingsDialog();
        }
      });

      if (settingsButton && settingsButton.dataset.bound !== '1') {
        settingsButton.dataset.bound = '1';
        settingsButton.addEventListener('click', function (event) {
          event.preventDefault();
          event.stopPropagation();
          if (container && container.open) {
            container.open = false;
          }
          openSettingsDialog();
        });
      }
    });
  }

  // ==========================================================================
  // Initialization
  // ==========================================================================

  function init() {
    initTheme();
    ensurePostFormCsrfTokens();
    setupHtmxCsrf();
    setupHtmxDebugLogging();
    setupConfirmDialog();
    setupSeedButtons();
    setupModelSelects();
    setupGenerationForms();
    setupProfileForms();
    setupChatAddToInput();
    setupChatRegenerate();
    setupUserMenu();
    setupGalleryFilters();
    setupGallerySelection();
    setupGalleryRatings();
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  document.body.addEventListener('htmx:afterSwap', function () {
    ensurePostFormCsrfTokens();
    setupGalleryRatings();
  });

})();
