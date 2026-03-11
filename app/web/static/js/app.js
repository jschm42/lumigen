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

    root.setAttribute('data-theme', normalized);
    root.setAttribute('data-theme-mode', theme === 'system' ? 'system' : normalized);
    if (body) {
      body.setAttribute('data-theme', normalized);
      body.setAttribute('data-theme-mode', theme === 'system' ? 'system' : normalized);
    }
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

  function reloadAfterThemeChange() {
    var targetWindow = window;
    try {
      if (window.top && window.top !== window && window.top.location.origin === window.location.origin) {
        targetWindow = window.top;
      }
    } catch (_error) {
      // Cross-origin frame access is blocked; fallback to current window.
    }

    // Use replace to force a full navigation of the active shell URL.
    targetWindow.location.replace(targetWindow.location.pathname + targetWindow.location.search);
  }

  function initTheme() {
    applyTheme(getSavedTheme());

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

    function syncProviderSpecificOptions(selected) {
      var provider = selected ? String(selected.dataset.provider || '').trim().toLowerCase() : '';
      var isOpenRouter = provider === 'openrouter';
      
      var dimensionControls = form.querySelector('[data-dimension-controls]');
      var standardDimensions = form.querySelector('[data-standard-dimensions]');
      var openrouterControls = form.querySelector('[data-openrouter-controls]');
      var aspectRatioInput = form.querySelector('[name="aspect_ratio"]');
      var imageSizeInput = form.querySelector('[name="image_size"]');
      
      // Toggle visibility based on provider
      if (dimensionControls) {
        dimensionControls.classList.toggle('hidden', isOpenRouter);
      }
      if (standardDimensions) {
        standardDimensions.classList.toggle('hidden', isOpenRouter);
      }
      if (openrouterControls) {
        openrouterControls.classList.toggle('hidden', !isOpenRouter);
      }
      
      // Disable/enable and clear values based on provider
      if (widthInput) {
        widthInput.disabled = isOpenRouter;
        if (isOpenRouter) widthInput.value = '';
      }
      if (heightInput) {
        heightInput.disabled = isOpenRouter;
        if (isOpenRouter) heightInput.value = '';
      }
      if (dimensionPreset) {
        dimensionPreset.disabled = isOpenRouter;
        if (isOpenRouter) {
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
    }

    function applyProfileDefaults() {
      var selected = profileSelect.options[profileSelect.selectedIndex];
      if (!selected) return;

      if (widthInput) widthInput.value = selected.dataset.width || '';
      if (heightInput) heightInput.value = selected.dataset.height || '';
      if (imagesInput) imagesInput.value = selected.dataset.nImages || '';
      if (seedInput) seedInput.value = selected.dataset.seed || '';
      syncProviderSpecificOptions(selected);

      syncDimensionPreset(widthInput, heightInput, dimensionPreset);
    }

    profileSelect.addEventListener('change', applyProfileDefaults);
    
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
      });

      widthInput.addEventListener('input', function () {
        syncDimensionPreset(widthInput, heightInput, dimensionPreset);
      });
      heightInput.addEventListener('input', function () {
        syncDimensionPreset(widthInput, heightInput, dimensionPreset);
      });
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
        wrapper.className = 'preview-image-wrapper';
        var img = document.createElement('img');
        img.src = objectUrl;
        img.alt = file.name || 'input image';
        img.className = 'preview-image';
        img.addEventListener('load', function () {
          URL.revokeObjectURL(objectUrl);
        });
        var removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'preview-image-remove';
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

    function syncProfileProviderState() {
      var selected = modelSelect.options[modelSelect.selectedIndex];
      var provider = selected ? String(selected.dataset.provider || '').trim().toLowerCase() : '';
      var isOpenRouter = provider === 'openrouter';

      if (dimensionsSection) {
        dimensionsSection.classList.toggle('hidden', isOpenRouter);
      }
      if (widthInput) {
        widthInput.disabled = isOpenRouter;
        if (isOpenRouter) widthInput.value = '';
      }
      if (heightInput) {
        heightInput.disabled = isOpenRouter;
        if (isOpenRouter) heightInput.value = '';
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
  var bulkForm = document.getElementById('bulk-action-form');
  if (!bulkForm) return;

  var cards = Array.from(document.querySelectorAll('[data-gallery-card][data-gallery-select]'));
  var selectAll = document.querySelector('[data-gallery-select-all]');
  var countLabel = document.querySelector('[data-gallery-selection-count]');
  var actionButtons = Array.from(document.querySelectorAll('[data-bulk-action]'));

  // Create hidden inputs for form submission
  var hiddenInputsContainer = bulkForm;
  var hiddenInputs = {};

  function createOrUpdateHiddenInput(assetId, checked) {
    var inputName = 'asset_ids';
    if (checked) {
      if (!hiddenInputs[assetId]) {
        var input = document.createElement('input');
        input.type = 'hidden';
        input.name = inputName;
        input.value = assetId;
        hiddenInputsContainer.appendChild(input);
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
    var selected = 0;
    cards.forEach(function (card) {
      var isSelected = card.dataset.selected === 'true';
      if (isSelected) {
        selected += 1;
      }
      // Toggle ring styling for selected cards
      card.classList.toggle('ring-sky-300', isSelected);
      card.classList.toggle('ring-2', isSelected);
    });

    if (countLabel) {
      countLabel.textContent = selected + ' selected';
    }

    actionButtons.forEach(function (button) {
      button.disabled = selected === 0;
    });

    if (selectAll) {
      if (selected === 0) {
        selectAll.checked = false;
        selectAll.indeterminate = false;
      } else if (selected === cards.length) {
        selectAll.checked = true;
        selectAll.indeterminate = false;
      } else {
        selectAll.checked = false;
        selectAll.indeterminate = true;
      }
    }
  }

  // Click on card to toggle selection
  cards.forEach(function (card) {
    var clickArea = card.querySelector('[data-gallery-card-click]');
    if (!clickArea) return;

    clickArea.addEventListener('click', function (e) {
      // Don't toggle if clicking on a link or button or form
      var target = e.target;
      if (target.closest('a') || target.closest('button') || target.closest('form')) {
        // Let default behavior happen for links (navigation) and buttons (actions)
        return;
      }

      // Toggle selection on click on the image area
      var assetId = card.dataset.assetId;
      var isSelected = card.dataset.selected === 'true';
      card.dataset.selected = (!isSelected).toString();
      createOrUpdateHiddenInput(assetId, !isSelected);
      updateState();
    });

    clickArea.addEventListener('dblclick', function (e) {
      var target = e.target;
      if (target.closest('a') || target.closest('button') || target.closest('form')) {
        return;
      }

      var detailUrl = card.dataset.assetDetailUrl;
      if (!detailUrl) {
        return;
      }
      window.location.href = detailUrl;
    });
  });

  // Select all toggle
  if (selectAll) {
    selectAll.addEventListener('change', function () {
      var shouldSelect = selectAll.checked;
      cards.forEach(function (card) {
        card.dataset.selected = shouldSelect.toString();
        var assetId = card.dataset.assetId;
        createOrUpdateHiddenInput(assetId, shouldSelect);
      });
      updateState();
    });
  }

  updateState();
}

function setupGalleryRatings() {
  var ratingForms = Array.from(document.querySelectorAll('[data-rating-form]'));
  if (ratingForms.length === 0) return;

  ratingForms.forEach(function (form) {
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
        star.classList.toggle('text-amber-300', isActive);
        star.classList.toggle('text-slate-600', !isActive);
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
        var previous = getSavedTheme();
        var selected = 'system';
        if (themeSelect.value === 'light' || themeSelect.value === 'dark') {
          selected = themeSelect.value;
        }
        applyTheme(selected);
        persistTheme(selected);
        if (selected !== previous) {
          reloadAfterThemeChange();
        }
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
    setupConfirmDialog();
    setupSeedButtons();
    setupModelSelects();
    setupGenerationForms();
    setupProfileForms();
    setupChatAddToInput();
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
  });

})();
