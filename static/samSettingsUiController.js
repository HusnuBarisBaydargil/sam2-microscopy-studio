(() => {
    const settingsController = window.SAM2SettingsController;
    const projectSettingsClient = window.SAM2ProjectSettingsClient;
    if (!settingsController) {
        throw new Error('SAM2SettingsController must be loaded before samSettingsUiController.js.');
    }
    if (!projectSettingsClient) {
        throw new Error('SAM2ProjectSettingsClient must be loaded before samSettingsUiController.js.');
    }

    function openModal(refs, renderPanel, rootDocument = document) {
        const returnFocus = rootDocument.activeElement;
        renderPanel({ keepInputs: true });
        refs.samSettingsModal.classList.remove('hidden');
        refs.closeSamSettingsBtn.focus();
        return returnFocus;
    }

    function closeModal(refs, returnFocus) {
        refs.samSettingsModal.classList.add('hidden');
        if (returnFocus && typeof returnFocus.focus === 'function') {
            returnFocus.focus();
        }
        return null;
    }

    function renderPresetOptions(refs, state) {
        const selectedPreset = state.projectSettings.samSettings.preset;
        refs.samPresetSelect.innerHTML = '';

        state.samPresets.forEach(preset => {
            const option = document.createElement('option');
            option.value = preset.key;
            option.textContent = preset.label;
            refs.samPresetSelect.appendChild(option);
        });

        const customOption = document.createElement('option');
        customOption.value = 'custom';
        customOption.textContent = 'Custom';
        refs.samPresetSelect.appendChild(customOption);
        refs.samPresetSelect.value = settingsController.findSamPreset(state.samPresets, selectedPreset)
            ? selectedPreset
            : 'custom';
    }

    function renderSettingsPanel(refs, state, { keepInputs = false, currentImage = null } = {}) {
        if (!keepInputs) {
            renderPresetOptions(refs, state);
            settingsController.syncSamSettingsInputs(refs, settingsController.currentSamParams(state));
        } else {
            refs.samPresetSelect.value = state.projectSettings.samSettings.preset === 'custom'
                ? 'custom'
                : state.projectSettings.samSettings.preset;
        }

        const params = settingsController.currentSamParams(state);
        const areaSuffix = params.area_mode === 'percent' ? '% image area' : 'px';
        refs.samMinObjectAreaInput.title = areaSuffix;
        refs.samMaxObjectAreaInput.title = areaSuffix;
        refs.samPresetSummary.textContent = settingsController.currentSamPresetLabel(state);
        renderDevicePanel(refs, state.projectSettings.samDevice);
        renderRiskText(refs, state, currentImage);
    }

    function renderDevicePanel(refs, samDevice) {
        const device = samDevice || projectSettingsClient.normalizeSamDeviceForClient();
        refs.samDeviceSelect.value = ['auto', 'cuda', 'cpu'].includes(device.mode) ? device.mode : 'auto';
        refs.samDeviceStatus.textContent = projectSettingsClient.samDeviceLabel(device);
        refs.samDeviceStatus.title = projectSettingsClient.samDeviceTitle(device);
        refs.samDeviceStatus.classList.toggle('warning', !device.ready || device.active === 'cpu' || Boolean(device.error));
        refs.samDeviceStatus.classList.toggle('ready', device.ready && device.active === 'cuda');
        renderReadinessText(refs, device);
    }

    function renderReadinessText(refs, samDevice) {
        const readiness = projectSettingsClient.samDeviceReadiness(samDevice);
        refs.samReadinessText.textContent = readiness.text;
        refs.samReadinessText.classList.toggle('error', readiness.level === 'error');
        refs.samReadinessText.classList.toggle('warning', readiness.level === 'warning');
        refs.samReadinessText.classList.toggle('ready', readiness.level === 'ready');
        return readiness;
    }

    function renderRiskText(refs, state, currentImage) {
        const riskState = settingsController.samRiskState(
            settingsController.currentSamParams(state),
            currentImage,
            state.projectSettings.samSettings.warnings || []
        );
        refs.samRiskText.textContent = riskState.text;
        refs.samRiskText.classList.toggle('warning', riskState.warning);
        return riskState;
    }

    function readSamSettingsFromInputs(refs) {
        return settingsController.readSamSettingsFromInputs(refs);
    }

    function currentSamSettingsPayload(state, refs) {
        return settingsController.currentSamSettingsPayload(state, readSamSettingsFromInputs(refs));
    }

    function samDeviceLabel(device) {
        return projectSettingsClient.samDeviceLabel(device);
    }

    window.SAM2SamSettingsUiController = {
        openModal,
        closeModal,
        renderPresetOptions,
        renderSettingsPanel,
        renderDevicePanel,
        renderReadinessText,
        renderRiskText,
        readSamSettingsFromInputs,
        currentSamSettingsPayload,
        samDeviceLabel
    };
})();
