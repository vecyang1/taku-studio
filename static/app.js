/**
 * Taku Studio Frontend Client Application (`app.js`)
 * 
 * Implements:
 * - Unidirectional Data Flow (Read = API -> State -> Render; Write = UI -> API -> Re-fetch -> Render)
 * - Single Source of Truth (SSOT)
 * - Interactive Multi-Format Device Simulator (Modals, Popups, Announcement Banners, Snippets)
 * - OpenAPI-Compliant Rule Evaluation Inspector
 * - Realtime SSE stream integration with activity ledger
 * - Full Campaign Lifecycle (List, Inspect, Toggle, Create, Delete, Preview)
 */

(function () {
  'use strict';

  // Global Application State
  const state = {
    currentSpaceId: null,
    spaces: [],
    popups: [],
    selectedPopupId: null,
    selectedPopup: null,
    activeTab: 'inspector',
    viewport: 'desktop',
    eventSource: null,
  };

  // DOM Elements Cache
  const el = {};

  function initElements() {
    el.spaceSelector = document.getElementById('spaceSelector');
    el.currentSpaceName = document.getElementById('currentSpaceName');
    el.currentSpaceMeta = document.getElementById('currentSpaceMeta');
    el.campaignSearch = document.getElementById('campaignSearch');
    el.campaignListContainer = document.getElementById('campaignListContainer');
    el.deviceFrame = document.getElementById('deviceFrame');
    el.frameUrlBar = document.getElementById('frameUrlBar');
    
    // Preview Elements
    el.bannerBar = document.getElementById('bannerBar');
    el.bannerContent = document.getElementById('bannerContent');
    el.bannerCloseBtn = document.getElementById('bannerCloseBtn');
    el.popupOverlay = document.getElementById('popupOverlay');
    el.popupCard = document.getElementById('popupCard');
    el.popupCloseBtn = document.getElementById('popupCloseBtn');
    el.popupMediaImage = document.getElementById('popupMediaImage');
    el.popupHeadline = document.getElementById('popupHeadline');
    el.interactivePopupForm = document.getElementById('interactivePopupForm');
    el.popupFormInputsContainer = document.getElementById('popupFormInputsContainer');
    el.popupSubmitBtn = document.getElementById('popupSubmitBtn');
    el.popupSuccessBanner = document.getElementById('popupSuccessBanner');
    
    // Top Bar Action Buttons
    el.btnOpenFeed = document.getElementById('btnOpenFeed');
    el.btnSync = document.getElementById('btnSync');
    el.syncIcon = document.getElementById('syncIcon');
    el.btnDiagnose = document.getElementById('btnDiagnose');
    el.btnNewCampaign = document.getElementById('btnNewCampaign');
    el.diagnosticModal = document.getElementById('diagnosticModal');
    el.diagModalBody = document.getElementById('diagModalBody');
    el.btnCloseDiagModal = document.getElementById('btnCloseDiagModal');
    el.btnDismissDiag = document.getElementById('btnDismissDiag');
    el.toastContainer = document.getElementById('toastContainer');

    // Create Campaign Modal Elements
    el.createCampaignModal = document.getElementById('createCampaignModal');
    el.btnCloseCreateModal = document.getElementById('btnCloseCreateModal');
    el.btnCancelCreateModal = document.getElementById('btnCancelCreateModal');
    el.btnSubmitCreateCampaign = document.getElementById('btnSubmitCreateCampaign');
    el.newCampaignName = document.getElementById('newCampaignName');
    el.newDisplayType = document.getElementById('newDisplayType');
    el.newDisplayDelay = document.getElementById('newDisplayDelay');
    el.newHeadlineContent = document.getElementById('newHeadlineContent');
    el.newIncludeForm = document.getElementById('newIncludeForm');
    el.newTargetUrl = document.getElementById('newTargetUrl');

    // Tab elements
    el.tabButtons = document.querySelectorAll('.tab-btn');
    el.tabInspector = document.getElementById('tabInspector');
    el.tabSimulator = document.getElementById('tabSimulator');
    el.tabSnippet = document.getElementById('tabSnippet');
    el.tabStream = document.getElementById('tabStream');
    
    // Inspector elements
    el.inspectorPopupId = document.getElementById('inspectorPopupId');
    el.inspectorName = document.getElementById('inspectorName');
    el.inspectorDisplayType = document.getElementById('inspectorDisplayType');
    el.inspectorDelay = document.getElementById('inspectorDelay');
    el.inspectorWebhook = document.getElementById('inspectorWebhook');
    el.inspectorEnabledToggle = document.getElementById('inspectorEnabledToggle');
    el.btnSaveInspector = document.getElementById('btnSaveInspector');
    el.btnDeleteCampaign = document.getElementById('btnDeleteCampaign');
    el.inspectorConditionsList = document.getElementById('inspectorConditionsList');

    // Simulator elements
    el.simTestUrl = document.getElementById('simTestUrl');
    el.simTestDevice = document.getElementById('simTestDevice');
    el.simPastCount = document.getElementById('simPastCount');
    el.simIgnorePaused = document.getElementById('simIgnorePaused');
    el.simLocation = document.getElementById('simLocation');
    el.simExitIntent = document.getElementById('simExitIntent');
    el.btnRunSimulation = document.getElementById('btnRunSimulation');
    el.simResultContainer = document.getElementById('simResultContainer');

    // Snippet elements
    el.embedSnippetCode = document.getElementById('embedSnippetCode');
    el.displayProjectKey = document.getElementById('displayProjectKey');
    el.btnCopySnippet = document.getElementById('btnCopySnippet');

    // SSE container
    el.eventLogContainer = document.getElementById('eventLogContainer');
  }

  // Toast Notification
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = 'toast';
    const strokeColor = type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#38bdf8';
    toast.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="${strokeColor}" stroke-width="2">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
        <polyline points="22 4 12 14.01 9 11.01"></polyline>
      </svg>
      <span>${escapeHtml(message)}</span>
    `;
    el.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(8px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>"']/g, function (m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
  }

  function logEvent(eventType, message) {
    const now = new Date().toTimeString().split(' ')[0];
    const item = document.createElement('div');
    item.className = 'log-entry';
    item.innerHTML = `
      <span class="log-time">${now}</span>
      <span class="log-event">${escapeHtml(eventType)}</span>
      <span>${escapeHtml(message)}</span>
    `;
    if (el.eventLogContainer) {
      el.eventLogContainer.prepend(item);
    }
  }

  // API Call Helper
  async function apiFetch(url, options = {}) {
    try {
      const res = await fetch(url, options);
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || `HTTP ${res.status}: ${res.statusText}`);
      }
      return await res.json();
    } catch (e) {
      showToast(e.message, 'error');
      throw e;
    }
  }

  // 1. Fetch Spaces
  async function loadSpaces() {
    try {
      const data = await apiFetch('/api/spaces');
      state.spaces = data.spaces || [];
      if (!state.currentSpaceId && state.spaces.length > 0) {
        state.currentSpaceId = state.spaces[0].space_id;
      }
      renderSpacesDropdown();
      updateSpaceHeader();
    } catch (err) {
      console.error('Failed to load spaces', err);
    }
  }

  function renderSpacesDropdown() {
    el.spaceSelector.innerHTML = '';
    state.spaces.forEach((s) => {
      const opt = document.createElement('option');
      opt.value = s.space_id;
      opt.textContent = `Space ${s.space_id} · ${s.name}`;
      if (s.space_id === state.currentSpaceId) opt.selected = true;
      el.spaceSelector.appendChild(opt);
    });
  }

  function updateSpaceHeader() {
    const cur = state.spaces.find((s) => s.space_id === state.currentSpaceId);
    if (!cur) return;
    el.currentSpaceName.textContent = cur.name;
    const domain = cur.primary_domain || window.location.hostname || 'localhost';
    el.currentSpaceMeta.textContent = `Key: ${(cur.project_key || '').slice(0, 10)}... | Domain: ${domain}`;
    el.displayProjectKey.textContent = cur.project_key || '—';
    el.embedSnippetCode.textContent = cur.embed_snippet || '';
    el.frameUrlBar.textContent = `https://${domain}/`;
    el.simTestUrl.value = `https://${domain}/demo`;
  }

  // 2. Fetch Popups for Space
  async function loadPopups() {
    el.campaignListContainer.innerHTML = `
      <div style="padding: 2rem 1rem; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
        Refreshing campaigns from Taku API...
      </div>
    `;
    try {
      const res = await apiFetch(`/api/spaces/${state.currentSpaceId}/popups`);
      state.popups = res.popups || [];
      renderCampaignList();

      if (state.popups.length > 0) {
        const existing = state.popups.find((p) => String(p.id) === String(state.selectedPopupId));
        selectPopup(existing ? existing.id : state.popups[0].id);
      } else {
        state.selectedPopup = null;
        state.selectedPopupId = null;
        clearPreview();
        clearInspector();
      }
      logEvent('DATA_SYNC', `Loaded ${state.popups.length} campaigns for Space ${state.currentSpaceId}`);
    } catch (err) {
      el.campaignListContainer.innerHTML = `
        <div style="padding: 2rem 1rem; text-align: center; color: var(--color-danger); font-size: 0.85rem;">
          Failed to load campaigns from Taku API.
        </div>
      `;
    }
  }

  function renderCampaignList() {
    const filter = (el.campaignSearch.value || '').toLowerCase();
    const filtered = state.popups.filter((p) => {
      const title = (p.extracted_title || p.name || '').toLowerCase();
      const id = String(p.id);
      return title.includes(filter) || id.includes(filter);
    });

    el.campaignListContainer.innerHTML = '';
    if (filtered.length === 0) {
      el.campaignListContainer.innerHTML = `
        <div style="padding: 2rem 1rem; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
          No matching campaigns found.
        </div>
      `;
      return;
    }

    filtered.forEach((p) => {
      const isSelected = String(p.id) === String(state.selectedPopupId);
      const isEnabled = Boolean(p.display_enabled);
      const card = document.createElement('div');
      card.className = `campaign-card ${isSelected ? 'selected' : ''}`;
      card.setAttribute('data-id', p.id);

      card.innerHTML = `
        <div class="campaign-card-header">
          <div class="campaign-card-title">${escapeHtml(p.extracted_title || p.name || 'Untitled Campaign')}</div>
          <label class="toggle-switch" onclick="event.stopPropagation()">
            <input type="checkbox" ${isEnabled ? 'checked' : ''} data-toggle-id="${p.id}">
            <span class="toggle-slider"></span>
          </label>
        </div>
        <div class="campaign-badges">
          <span class="badge ${isEnabled ? 'badge-active' : 'badge-paused'}">
            ${isEnabled ? 'Active' : 'Paused'}
          </span>
          <span class="badge badge-type">${escapeHtml(p.display_type || 'popup')}</span>
          <span class="badge" style="background: var(--bg-surface-elevated); color: var(--text-secondary);">#${p.id}</span>
        </div>
        <div class="campaign-card-footer">
          <span class="views-count">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
            ${p.views_count || 0} views
          </span>
          <span>${(p.created_at || '').slice(0, 10)}</span>
        </div>
      `;

      card.addEventListener('click', () => selectPopup(p.id));

      const toggle = card.querySelector(`[data-toggle-id="${p.id}"]`);
      if (toggle) {
        toggle.addEventListener('change', async (e) => {
          e.stopPropagation();
          await handleTogglePopup(p.id, toggle.checked);
        });
      }

      el.campaignListContainer.appendChild(card);
    });
  }

  // 3. Select & Inspect Popup
  async function selectPopup(popupId) {
    state.selectedPopupId = popupId;
    renderCampaignList();

    try {
      const data = await apiFetch(`/api/popups/${popupId}`);
      state.selectedPopup = data;
      renderPreview(data);
      populateInspector(data);
      if (state.activeTab === 'simulator') {
        runSimulation();
      }
    } catch (err) {
      console.error('Failed to load popup details', err);
    }
  }

  // 4. Unidirectional Toggle Handler
  async function handleTogglePopup(popupId, newState) {
    try {
      showToast(`Syncing ${newState ? 'Activation' : 'Pausing'} with Taku API...`);
      const fresh = await apiFetch(`/api/popups/${popupId}/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_enabled: newState }),
      });

      const idx = state.popups.findIndex((p) => String(p.id) === String(popupId));
      if (idx !== -1) {
        state.popups[idx] = fresh;
      }
      if (String(state.selectedPopupId) === String(popupId)) {
        state.selectedPopup = fresh;
        populateInspector(fresh);
      }
      renderCampaignList();
      showToast(`Popup #${popupId} is now ${fresh.display_enabled ? 'ACTIVE' : 'PAUSED'} (Authoritative)`, 'success');
      logEvent('MUTATION', `Toggled Popup #${popupId} display_enabled -> ${fresh.display_enabled}`);
    } catch (err) {
      showToast(`Toggle failed: ${err.message}`, 'error');
      renderCampaignList();
    }
  }

  // 5. Populate Inspector Tab
  function populateInspector(p) {
    if (!p) return;
    el.inspectorPopupId.value = p.id;
    el.inspectorName.value = p.extracted_title || p.name || '';
    el.inspectorDisplayType.value = p.display_type || 'modal';
    const delay = (p.trigger_configuration && p.trigger_configuration.display_delay) !== undefined
      ? p.trigger_configuration.display_delay
      : 7000;
    el.inspectorDelay.value = delay;
    el.inspectorEnabledToggle.checked = Boolean(p.display_enabled);

    const integrations = p.integrations || [];
    const wh = integrations.find((i) => i.type === 'webhook');
    el.inspectorWebhook.value = wh ? wh.url : 'None configured';

    // Conditions list
    const conditions =
      (p.trigger_configuration && p.trigger_configuration.conditions) ||
      (p.configuration && p.configuration.conditions) ||
      [];
    el.inspectorConditionsList.innerHTML = '';
    if (conditions.length === 0) {
      el.inspectorConditionsList.innerHTML = '<span style="font-size: 0.75rem; color: var(--text-muted);">Matches all pages (no conditions)</span>';
    } else {
      conditions.forEach((c) => {
        const item = document.createElement('div');
        item.style.padding = '0.35rem 0.5rem';
        item.style.background = 'var(--bg-base)';
        item.style.border = '1px solid var(--border-subtle)';
        item.style.borderRadius = '4px';
        item.style.fontSize = '0.75rem';
        const targetVal = c.value || c.device || '';
        item.innerHTML = `<strong>${escapeHtml(c.type || 'page_url')}</strong> ${escapeHtml(c.operator || 'eq')} <code style="color: #38bdf8;">"${escapeHtml(targetVal)}"</code>`;
        el.inspectorConditionsList.appendChild(item);
      });
    }

    // Update standalone feed button
    const space = state.spaces.find((s) => s.space_id === state.currentSpaceId);
    if (space) {
      el.btnOpenFeed.href = `https://ui.taku.cool/feed/${space.project_key}/${p.id}`;
    }
  }

  function clearInspector() {
    el.inspectorPopupId.value = '';
    el.inspectorName.value = '';
    el.inspectorDelay.value = '0';
    el.inspectorWebhook.value = '';
    el.inspectorEnabledToggle.checked = false;
    el.inspectorConditionsList.innerHTML = '<span style="font-size: 0.75rem; color: var(--text-muted);">No campaign selected</span>';
    el.btnOpenFeed.href = '#';
  }

  // 6. Save Inspector Changes
  async function saveInspectorChanges() {
    if (!state.selectedPopup) return;
    const popupId = state.selectedPopup.id;
    const payload = {
      name: el.inspectorName.value,
      display_type: el.inspectorDisplayType.value,
      display_enabled: el.inspectorEnabledToggle.checked,
    };

    try {
      showToast('Saving changes to Taku API...');
      const fresh = await apiFetch(`/api/popups/${popupId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      state.selectedPopup = fresh;
      const idx = state.popups.findIndex((p) => String(p.id) === String(popupId));
      if (idx !== -1) {
        state.popups[idx] = fresh;
      }
      renderCampaignList();
      renderPreview(fresh);
      populateInspector(fresh);
      showToast('Campaign successfully updated & re-synced!', 'success');
      logEvent('UPDATE', `Updated Popup #${popupId} successfully`);
    } catch (err) {
      showToast(`Save failed: ${err.message}`, 'error');
    }
  }

  // 7. Delete Campaign
  async function handleDeleteCampaign() {
    if (!state.selectedPopup) return;
    const popupId = state.selectedPopup.id;
    const confirmed = window.confirm(`Permanently delete Popup #${popupId} from Taku Space ${state.currentSpaceId}?\nThis action writes directly to the authoritative Taku API.`);
    if (!confirmed) return;

    try {
      showToast(`Deleting Popup #${popupId}...`);
      await apiFetch(`/api/popups/${popupId}`, { method: 'DELETE' });
      showToast(`Popup #${popupId} deleted successfully`, 'success');
      logEvent('DELETE', `Deleted Popup #${popupId}`);
      await loadPopups();
    } catch (err) {
      showToast(`Delete failed: ${err.message}`, 'error');
    }
  }

  // 8. Create Campaign Modal & Handler
  function openCreateModal() {
    el.newCampaignName.value = '';
    el.newHeadlineContent.value = '';
    el.newDisplayType.value = 'modal';
    el.newDisplayDelay.value = '0';
    el.newIncludeForm.checked = true;
    const cur = state.spaces.find((s) => s.space_id === state.currentSpaceId);
    const domain = cur ? (cur.primary_domain || window.location.hostname || 'localhost') : (window.location.hostname || 'localhost');
    el.newTargetUrl.value = `https://${domain}/`;
    el.createCampaignModal.style.display = 'flex';
  }

  function closeCreateModal() {
    el.createCampaignModal.style.display = 'none';
  }

  async function submitCreateCampaign() {
    const name = el.newCampaignName.value.trim();
    const content = el.newHeadlineContent.value.trim();
    if (!name || !content) {
      showToast('Please provide both Campaign Name and Content', 'error');
      return;
    }

    const displayType = el.newDisplayType.value;
    const delayMs = parseInt(el.newDisplayDelay.value, 10) || 0;
    const hasForm = el.newIncludeForm.checked;
    const targetUrl = el.newTargetUrl.value.trim();

    const conditions = [];
    if (targetUrl) {
      conditions.push({
        type: 'page_url',
        operator: 'startsWith',
        value: targetUrl,
      });
    }

    const payload = {
      name: name,
      display_type: displayType,
      display_enabled: true,
      trigger_configuration: {
        display_delay: delayMs,
        conditions: conditions,
        conditions_match: 'all',
      },
      variations: [
        {
          blocks: [
            {
              block_type: 'rich_text',
              content: content,
            },
            ...(hasForm
              ? [
                  {
                    block_type: 'form',
                    submit_mode: 'single',
                    submit_button: {
                      text: 'Subscribe',
                      color: '#3345EE',
                      text_color: '#ffffff',
                    },
                    inputs: [
                      {
                        key: 'email',
                        type: 'user_email',
                        placeholder: 'Your email address',
                        required: true,
                      },
                    ],
                    complete: {
                      text: 'Thank you for subscribing!',
                    },
                  },
                ]
              : []),
          ],
          ...(displayType === 'banner'
            ? {
                banner_configuration: {
                  position: 'top',
                  background_color: '#313131',
                  text_color: '#ffffff',
                  floating: false,
                },
              }
            : {}),
        },
      ],
    };

    try {
      showToast('Creating new campaign on Taku API...');
      const created = await apiFetch(`/api/spaces/${state.currentSpaceId}/popups`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      closeCreateModal();
      showToast(`Campaign #${created.id} created successfully!`, 'success');
      logEvent('CREATE', `Created new campaign #${created.id} in Space ${state.currentSpaceId}`);
      await loadPopups();
      selectPopup(created.id);
    } catch (err) {
      showToast(`Creation failed: ${err.message}`, 'error');
    }
  }

  // 9. Interactive Preview Rendering (Multi-Format)
  function renderPreview(p) {
    if (!p) {
      clearPreview();
      return;
    }

    const displayType = (p.display_type || 'modal').toLowerCase();
    const variations = p.variations || [];
    let imageSrc = null;
    let headlineText = p.extracted_title || p.name || 'Special Offer';
    let bannerConfig = { background_color: '#313131', text_color: '#ffffff', position: 'top' };
    let hasForm = false;
    let inputs = [];
    let submitBtnConfig = { text: 'Subscribe', color: '#3345EE', text_color: '#ffffff' };
    let completeText = 'Thank you for subscribing!';

    if (variations.length > 0) {
      if (variations[0].banner_configuration) {
        bannerConfig = Object.assign(bannerConfig, variations[0].banner_configuration);
      }
      const blocks = variations[0].blocks || [];
      blocks.forEach((b) => {
        if (b.block_type === 'media' && b.url) {
          imageSrc = b.url;
        } else if (b.block_type === 'rich_text' && b.content) {
          headlineText = b.content
            .replace(/\\n/g, '<br>')
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        } else if (b.block_type === 'form') {
          hasForm = true;
          inputs = b.inputs || [];
          if (b.submit_button) submitBtnConfig = b.submit_button;
          if (b.complete && b.complete.text) completeText = b.complete.text;
        }
      });
    }

    if (displayType === 'banner') {
      // Banner format: top or bottom announcement notification bar
      if (el.popupOverlay) el.popupOverlay.style.display = 'none';
      if (el.bannerBar) {
        el.bannerBar.style.display = 'flex';
        el.bannerBar.style.backgroundColor = bannerConfig.background_color || '#313131';
        el.bannerBar.style.color = bannerConfig.text_color || '#ffffff';
        if (bannerConfig.position === 'bottom') {
          el.bannerBar.style.top = 'auto';
          el.bannerBar.style.bottom = '0';
        } else {
          el.bannerBar.style.top = '0';
          el.bannerBar.style.bottom = 'auto';
        }
        if (el.bannerContent) el.bannerContent.innerHTML = headlineText;
      }
    } else {
      // Modal or Popup format: centered card with backdrop overlay
      if (el.bannerBar) el.bannerBar.style.display = 'none';
      if (el.popupOverlay) el.popupOverlay.style.display = 'flex';
      if (el.popupSuccessBanner) el.popupSuccessBanner.style.display = 'none';

      // Media Image
      if (imageSrc && el.popupMediaImage) {
        el.popupMediaImage.src = imageSrc;
        el.popupMediaImage.style.display = 'block';
      } else if (el.popupMediaImage) {
        el.popupMediaImage.style.display = 'none';
      }

      // Headline
      if (el.popupHeadline) el.popupHeadline.innerHTML = headlineText;

      // Form Handling
      if (hasForm && inputs.length > 0) {
        el.interactivePopupForm.style.display = 'flex';
        el.popupFormInputsContainer.innerHTML = '';
        inputs.forEach((inp) => {
          const inputEl = document.createElement('input');
          inputEl.className = 'popup-input';
          inputEl.type = inp.type === 'user_email' ? 'email' : 'text';
          inputEl.placeholder = inp.placeholder || inp.key;
          inputEl.required = Boolean(inp.required);
          inputEl.id = `input_${inp.key}`;
          el.popupFormInputsContainer.appendChild(inputEl);
        });

        el.popupSubmitBtn.textContent = submitBtnConfig.text || 'Submit';
        el.popupSubmitBtn.style.backgroundColor = submitBtnConfig.color || '#3345EE';
        el.popupSubmitBtn.style.color = submitBtnConfig.text_color || '#ffffff';

        el.interactivePopupForm.onsubmit = (e) => {
          e.preventDefault();
          el.interactivePopupForm.style.display = 'none';
          el.popupSuccessBanner.textContent = completeText;
          el.popupSuccessBanner.style.display = 'block';
          showToast('Form submission verified (interactive simulation)', 'success');
          logEvent('SUBMIT', `Simulated form submit on Popup #${p.id}`);
        };
      } else {
        // No form block: informational modal (clean presentation, zero hallucinated inputs)
        el.interactivePopupForm.style.display = 'none';
        el.popupFormInputsContainer.innerHTML = '';
      }
    }
  }

  function clearPreview() {
    if (el.popupOverlay) el.popupOverlay.style.display = 'none';
    if (el.bannerBar) el.bannerBar.style.display = 'none';
  }

  // 10. Audience & Trigger Simulator
  async function runSimulation() {
    if (!state.selectedPopup) return;
    const testUrl = el.simTestUrl.value.trim();
    const testDevice = el.simTestDevice.value;
    const pastCount = parseInt(el.simPastCount.value, 10) || 0;
    const ignorePaused = el.simIgnorePaused ? el.simIgnorePaused.checked : false;
    const exitIntent = el.simExitIntent ? el.simExitIntent.checked : false;
    const location = el.simLocation && el.simLocation.value.trim() ? el.simLocation.value.trim() : null;

    el.simResultContainer.innerHTML = '<div style="font-size: 0.75rem; color: var(--text-muted);">Evaluating rules...</div>';

    try {
      const res = await apiFetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          popup: state.selectedPopup,
          url: testUrl,
          device: testDevice,
          past_triggers_count: pastCount,
          ignore_paused: ignorePaused,
          exit_intent: exitIntent,
          location: location,
        }),
      });

      renderSimulationReport(res);
      logEvent('SIMULATOR', `Evaluated Popup #${state.selectedPopup.id}: ${res.status_code}`);
    } catch (err) {
      el.simResultContainer.innerHTML = `<div style="color: var(--color-danger); font-size: 0.75rem;">Simulation failed: ${err.message}</div>`;
    }
  }

  function renderSimulationReport(report) {
    const isPassed = report.will_trigger;
    const card = document.createElement('div');
    card.className = `sim-result-card ${isPassed ? 'passed' : 'failed'}`;

    let rulesHtml = '';
    (report.conditions_evaluated || []).forEach((c) => {
      rulesHtml += `
        <div class="sim-rule-item">
          <span>${escapeHtml(c.condition_type)} [${escapeHtml(c.operator)}] "${escapeHtml(c.target_value)}"</span>
          <span style="font-weight: 600; color: ${c.matched ? 'var(--color-success)' : 'var(--color-danger)'};">
            ${c.matched ? 'PASSED' : 'FAILED'}
          </span>
        </div>
      `;
    });

    card.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between;">
        <span style="font-weight: 700; font-size: 0.85rem; color: ${isPassed ? 'var(--color-success)' : 'var(--color-danger)'};">
          ${isPassed ? 'TRIGGER GRANTED' : 'TRIGGER SUPPRESSED'}
        </span>
        <span class="badge" style="background: rgba(0,0,0,0.3); font-size: 0.7rem;">${report.status_code}</span>
      </div>
      <p style="font-size: 0.78rem; line-height: 1.4;">${escapeHtml(report.summary)}</p>
      ${rulesHtml ? `<div style="margin-top: 0.4rem;">${rulesHtml}</div>` : ''}
    `;

    el.simResultContainer.innerHTML = '';
    el.simResultContainer.appendChild(card);
  }

  // 11. System Health Check Diagnostic
  async function runDiagnostic() {
    el.diagnosticModal.style.display = 'flex';
    el.diagModalBody.innerHTML = `
      <div style="text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.85rem;">
        Testing live connection to api.taku.cool/v1 across customer spaces...
      </div>
    `;

    try {
      const report = await apiFetch('/api/diagnose');
      let spacesHtml = '';
      Object.entries(report.spaces || {}).forEach(([spaceId, s]) => {
        const isConn = s.status === 'connected';
        spacesHtml += `
          <div style="background: var(--bg-base); padding: 0.75rem; border-radius: 6px; border: 1px solid var(--border-subtle); margin-bottom: 0.5rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
              <strong style="font-size: 0.85rem;">Space ${spaceId} (${escapeHtml(s.name)})</strong>
              <span class="badge ${isConn ? 'badge-active' : 'badge-paused'}">${s.status.toUpperCase()}</span>
            </div>
            <div style="font-size: 0.75rem; color: var(--text-secondary); font-family: var(--font-mono);">
              Key: ${s.project_key ? s.project_key.slice(0, 16) + '...' : 'N/A'} | Popups: ${s.popup_count || 0}
            </div>
          </div>
        `;
      });

      el.diagModalBody.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
          <span style="font-size: 0.85rem; font-weight: 600;">Overall Status:</span>
          <span class="badge badge-active">${report.status.toUpperCase()}</span>
        </div>
        <div style="font-size: 0.78rem; color: var(--text-secondary); margin-bottom: 1rem;">
          Auth Source: <code>${report.credential_source}</code> | Key: <code>${report.api_key_suffix}</code>
        </div>
        <div>${spacesHtml}</div>
      `;
      logEvent('DIAGNOSE', `Diagnostic report completed: status=${report.status}`);
    } catch (err) {
      el.diagModalBody.innerHTML = `<div style="color: var(--color-danger); padding: 1rem;">Health check failed: ${err.message}</div>`;
    }
  }

  // 12. Server-Sent Events (SSE) Live Stream
  function initSSE() {
    try {
      const es = new EventSource('/api/events');
      es.addEventListener('connected', () => {
        logEvent('SSE_CONNECT', 'Live stream connection established');
      });
      es.addEventListener('popup_toggled', (e) => {
        const data = JSON.parse(e.data);
        logEvent('SSE_EVENT', `Popup #${data.popup_id} toggled to ${data.display_enabled}`);
      });
      es.addEventListener('popup_updated', (e) => {
        const data = JSON.parse(e.data);
        logEvent('SSE_EVENT', `Popup #${data.popup_id} updated: ${data.title}`);
      });
      es.addEventListener('popup_created', (e) => {
        const data = JSON.parse(e.data);
        logEvent('SSE_EVENT', `Popup #${data.popup_id} created in Space ${data.space_id}`);
      });
      es.addEventListener('popup_deleted', (e) => {
        const data = JSON.parse(e.data);
        logEvent('SSE_EVENT', `Popup #${data.popup_id} deleted`);
      });
      state.eventSource = es;
    } catch (e) {
      console.warn('SSE not supported or failed to initialize', e);
    }
  }

  // 13. Event Listeners Setup
  function setupListeners() {
    // Space selector
    el.spaceSelector.addEventListener('change', async (e) => {
      state.currentSpaceId = parseInt(e.target.value, 10);
      updateSpaceHeader();
      await loadPopups();
    });

    // Sync button
    el.btnSync.addEventListener('click', async () => {
      el.syncIcon.style.animation = 'spin 0.6s linear infinite';
      await loadPopups();
      el.syncIcon.style.animation = '';
      showToast('Live synchronization complete', 'success');
    });

    // Search
    el.campaignSearch.addEventListener('input', () => {
      renderCampaignList();
    });

    // Viewport switchers
    document.querySelectorAll('.viewport-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.viewport-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        const vp = btn.getAttribute('data-viewport');
        state.viewport = vp;
        el.deviceFrame.className = `device-frame ${vp}`;
      });
    });

    // Popup Close button in frame
    el.popupCloseBtn.addEventListener('click', () => {
      el.popupCard.style.animation = 'scaleDown 0.2s forwards';
      setTimeout(() => {
        el.popupOverlay.style.display = 'none';
        el.popupCard.style.animation = '';
        showToast('Popup dismissed. Click a campaign to preview again.');
      }, 200);
    });

    // Banner Close button
    if (el.bannerCloseBtn) {
      el.bannerCloseBtn.addEventListener('click', () => {
        el.bannerBar.style.display = 'none';
        showToast('Banner dismissed. Click a campaign to preview again.');
      });
    }

    // Tabs switchers
    el.tabButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        el.tabButtons.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        const tab = btn.getAttribute('data-tab');
        state.activeTab = tab;

        el.tabInspector.style.display = tab === 'inspector' ? 'flex' : 'none';
        el.tabSimulator.style.display = tab === 'simulator' ? 'flex' : 'none';
        el.tabSnippet.style.display = tab === 'snippet' ? 'flex' : 'none';
        el.tabStream.style.display = tab === 'stream' ? 'flex' : 'none';

        if (tab === 'simulator') runSimulation();
      });
    });

    // Inspector Save & Delete buttons
    el.btnSaveInspector.addEventListener('click', saveInspectorChanges);
    if (el.btnDeleteCampaign) {
      el.btnDeleteCampaign.addEventListener('click', handleDeleteCampaign);
    }

    // New Campaign Modal buttons
    if (el.btnNewCampaign) {
      el.btnNewCampaign.addEventListener('click', openCreateModal);
    }
    if (el.btnCloseCreateModal) {
      el.btnCloseCreateModal.addEventListener('click', closeCreateModal);
    }
    if (el.btnCancelCreateModal) {
      el.btnCancelCreateModal.addEventListener('click', closeCreateModal);
    }
    if (el.btnSubmitCreateCampaign) {
      el.btnSubmitCreateCampaign.addEventListener('click', submitCreateCampaign);
    }

    // Simulator Run button
    el.btnRunSimulation.addEventListener('click', runSimulation);

    // Copy embed snippet
    el.btnCopySnippet.addEventListener('click', () => {
      navigator.clipboard.writeText(el.embedSnippetCode.textContent).then(() => {
        showToast('Embed snippet copied to clipboard!', 'success');
      });
    });

    // Diagnostic modal
    el.btnDiagnose.addEventListener('click', runDiagnostic);
    el.btnCloseDiagModal.addEventListener('click', () => {
      el.diagnosticModal.style.display = 'none';
    });
    el.btnDismissDiag.addEventListener('click', () => {
      el.diagnosticModal.style.display = 'none';
    });
  }

  // Application Entry Point
  async function init() {
    initElements();
    setupListeners();
    initSSE();
    await loadSpaces();
    await loadPopups();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
