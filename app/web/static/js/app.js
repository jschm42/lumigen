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
    } catch (error) {
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
    var dimensionControls = form.querySelector('[data-dimension-controls]');
    var inputImages = form.querySelector('[data-input-images]');
    var inputPreview = form.querySelector('[data-input-preview]');
    var inputClear = form.querySelector('[data-input-clear]');
    var inputTrigger = form.querySelector('[data-input-trigger]');
    var inputFileState = [];
    var enhanceBtn = form.querySelector('[data-enhance-prompt]');
    var promptInput = form.querySelector('[name="prompt_user"]');
    var upscaleEnable = form.querySelector('[data-upscale-enable]');
    var upscaleModel = form.querySelector('[data-upscale-model]');
    var advancedToggle = form.querySelector('[data-advanced-toggle]');
    var advancedPanel = form.querySelector('[data-advanced-panel]');

    function syncProviderSpecificOptions(selected) {
      var provider = selected ? String(selected.dataset.provider || '').trim().toLowerCase() : '';
      var isOpenRouter = provider === 'openrouter';
      if (dimensionControls) {
        dimensionControls.classList.toggle('hidden', isOpenRouter);
      }
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

    if (upscaleEnable && upscaleModel) {
      function syncUpscaleToggle() {
        upscaleModel.disabled = !upscaleEnable.checked;
        if (!upscaleEnable.checked) {
          upscaleModel.value = '';
        }
      }
      upscaleEnable.addEventListener('change', syncUpscaleToggle);
      syncUpscaleToggle();
    }

    function syncInputFiles() {
      if (!inputImages) return;
      var dataTransfer = new DataTransfer();
      inputFileState.forEach(function (file) {
        dataTransfer.items.add(file);
      });
      inputImages.files = dataTransfer.files;
    }

    function renderInputPreviews() {
      if (!inputImages || !inputPreview) return;
      inputPreview.innerHTML = '';

      if (inputFileState.length > 5) {
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
        removeBtn.addEventListener('click', function () {
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
        addSelectedFiles(inputImages.files);
        inputImages.value = '';
      });
      renderInputPreviews();
    }

    if (inputTrigger && inputImages) {
      inputTrigger.addEventListener('click', function () {
        inputImages.click();
      });
    }

    if (inputClear) {
      inputClear.addEventListener('click', function () {
        inputFileState = [];
        syncInputFiles();
        renderInputPreviews();
      });
    }

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
        var enhanceIcon = enhanceBtn.querySelector('.material-symbols-outlined');
        if (enhanceIcon) {
          enhanceIcon.textContent = 'auto_fix_high';
          enhanceIcon.classList.add('animate-pulse');
        }

        try {
          var response = await fetch('/api/enhance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
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
        } catch (error) {
          alert('Enhancement failed.');
        } finally {
          enhanceBtn.disabled = false;
          enhanceBtn.removeAttribute('aria-busy');
          if (enhanceIcon) {
            enhanceIcon.textContent = 'auto_fix_high';
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
  // Gallery Selection
  // ==========================================================================

  function setupGallerySelection() {
    var bulkForm = document.getElementById('bulk-action-form');
    if (!bulkForm) return;

    var checkboxes = Array.from(document.querySelectorAll('[data-gallery-select]'));
    var selectAll = document.querySelector('[data-gallery-select-all]');
    var countLabel = document.querySelector('[data-gallery-selection-count]');
    var actionButtons = Array.from(document.querySelectorAll('[data-bulk-action]'));

    function updateState() {
      var selected = 0;
      checkboxes.forEach(function (checkbox) {
        var card = checkbox.closest('[data-gallery-card]');
        if (checkbox.checked) {
          selected += 1;
        }
        if (card) {
          card.classList.toggle('ring-2', checkbox.checked);
          card.classList.toggle('ring-sky-300', checkbox.checked);
          card.classList.toggle('border-sky-300/70', checkbox.checked);
        }
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
        } else if (selected === checkboxes.length) {
          selectAll.checked = true;
          selectAll.indeterminate = false;
        } else {
          selectAll.checked = false;
          selectAll.indeterminate = true;
        }
      }
    }

    checkboxes.forEach(function (checkbox) {
      checkbox.addEventListener('change', updateState);
    });

    if (selectAll) {
      selectAll.addEventListener('change', function () {
        checkboxes.forEach(function (checkbox) {
          checkbox.checked = selectAll.checked;
        });
        updateState();
      });
    }

    updateState();
  }

  // ==========================================================================
  // Initialization
  // ==========================================================================

  function init() {
    setupSeedButtons();
    setupModelSelects();
    setupGenerationForms();
    setupProfileForms();
    setupGallerySelection();
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
