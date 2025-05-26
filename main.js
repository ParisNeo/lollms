// --- Localization State ---
let currentTranslations = {};
let currentLang = 'en';
let availableLanguages = { 'en': 'English' };

// --- Global State ---
let currentUser = null;
let currentDiscussionId = null;
let discussions = {}; // Enhanced: { discId: { title, is_starred, rag_datastore_id, last_activity_at, branches: { branchId: [messages] }, activeBranchId, messages_loaded_fully: {branchId: bool} } }
let currentMessages = []; // Points to discussions[currentDiscussionId].branches[activeBranchId]
let aiMessageStreaming = false;
let currentAiMessageDomContainer = null; // Actual DOM element for streaming AI message's container
let currentAiMessageDomBubble = null;   // Actual DOM element for streaming AI message's bubble
let currentAiMessageContentAccumulator = "";
let currentAiMessageId = null; // ID of the AI message being streamed
let currentAiMessageData = null; // Data object for the AI message being streamed
let pyodide = null;
let pyodideLoading = false;
let isRagActive = false;
let availableLollmsModels = [];
let availableVectorizers = [];
let userDefaultVectorizer = null;
let ownedDataStores = [];
let sharedDataStores = [];
let availableDataStoresForRag = [];
let uploadedImageServerPaths = []; // { filename, server_path, file_obj (client-side File object) }
let tempLoginUsername = null;
let tempLoginPassword = null;
let generationInProgress = false;
let activeGenerationAbortController = null;
let currentTheme = localStorage.getItem('theme') || 'dark';
let activeBranchId = 'main'; // Global active branch ID for the current discussion

const backendCapabilities = {
    supportsBranches: false, // Will be updated based on API responses
    checked: false
};

// --- DOM Elements (Assuming all your const declarations are correct) ---
// ... (All your document.getElementById calls remain here) ...
const languageSelector = document.getElementById('languageSelector');
const appLoadingMessage = document.getElementById('appLoadingMessage');
const appLoadingProgress = document.getElementById('appLoadingProgress');
const appLoadingStatus = document.getElementById('appLoadingStatus');
const appContainer = document.getElementById('app-container');
const loginModal = document.getElementById('loginModal');
const loginUsernameInput = document.getElementById('loginUsername');
const loginPasswordInput = document.getElementById('loginPassword');
const loginSubmitBtn = document.getElementById('loginSubmitBtn');
const loginStatus = document.getElementById('loginStatus');
const discussionSearchInput = document.getElementById('discussionSearchInput');
const discussionListContainer = document.getElementById('discussionListContainer');
const newDiscussionBtn = document.getElementById('newDiscussionBtn');
const usernameDisplay = document.getElementById('usernameDisplay');
const adminBadge = document.getElementById('adminBadge');
const userMenuToggleBtn = document.getElementById('userMenuToggleBtn');
const userMenuDropdown = document.getElementById('userMenuDropdown');
const userMenuArrow = document.getElementById('userMenuArrow');
const adminLink = document.getElementById('adminLink');
const settingsBtn = document.getElementById('settingsBtn');
const dataStoresBtn = document.getElementById('dataStoresBtn');
const exportDataBtn = document.getElementById('exportDataBtn');
const importDataBtn = document.getElementById('importDataBtn');
const logoutBtn = document.getElementById('logoutBtn');
const chatHeader = document.getElementById('chatHeader'); // Assuming you have an ID for the chat header area
const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendMessageBtn = document.getElementById('sendMessageBtn');
const stopGenerationBtn = document.getElementById('stopGenerationBtn');
const discussionTitle = document.getElementById('discussionTitle');
const ragToggleBtn = document.getElementById('ragToggleBtn');
const ragDataStoreSelect = document.getElementById('ragDataStoreSelect');
const imageUploadInput = document.getElementById('imageUploadInput');
const imageUploadPreviewContainer = document.getElementById('imageUploadPreviewContainer');
const statusMessage = document.getElementById('statusMessage');
const pyodideStatus = document.getElementById('pyodideStatus');
const renameModal = document.getElementById('renameModal');
const renameInput = document.getElementById('renameInput');
const confirmRenameBtn = document.getElementById('confirmRenameBtn');
const renameStatus = document.getElementById('renameStatus');
const renameDiscussionIdInput = document.getElementById('renameDiscussionIdInput');
const sendDiscussionModal = document.getElementById('sendDiscussionModal');
const sendTargetUsernameInput = document.getElementById('sendTargetUsername');
const confirmSendDiscussionBtn = document.getElementById('confirmSendDiscussionBtn');
const sendDiscussionStatus = document.getElementById('sendDiscussionStatus');
const sendDiscussionIdInput = document.getElementById('sendDiscussionIdInput');
const editMessageModal = document.getElementById('editMessageModal');
const editMessageInput = document.getElementById('editMessageInput');
const confirmEditMessageBtn = document.getElementById('confirmEditMessageBtn');
const editMessageStatus = document.getElementById('editMessageStatus');
const editMessageIdInput = document.getElementById('editMessageIdInput');
const editMessageBranchIdInput = document.getElementById('editMessageBranchIdInput'); // For editing specific branch message
const exportModal = document.getElementById('exportModal');
const exportDiscussionList = document.getElementById('exportDiscussionList');
const confirmExportBtn = document.getElementById('confirmExportBtn');
const importModal = document.getElementById('importModal');
const importFile = document.getElementById('importFile');
const importPreviewArea = document.getElementById('importPreviewArea');
const importDiscussionList = document.getElementById('importDiscussionList');
const confirmImportBtn = document.getElementById('confirmImportBtn');
const importStatus = document.getElementById('importStatus');
const settingsModal = document.getElementById('settingsModal');
const settingsLollmsModelSelect = document.getElementById('settingsLollmsModelSelect');
const saveModelAndVectorizerBtn = document.getElementById('saveModelAndVectorizerBtn');
const settingsTemperature = document.getElementById('settingsTemperature');
const settingsTopK = document.getElementById('settingsTopK');
const settingsTopP = document.getElementById('settingsTopP');
const settingsRepeatPenalty = document.getElementById('settingsRepeatPenalty');
const settingsRepeatLastN = document.getElementById('settingsRepeatLastN');
const saveLLMParamsBtn = document.getElementById('saveLLMParamsBtn');
const settingsStatus_llmConfig = document.getElementById('settingsStatus_llmConfig');
const settingsStatus_llmParams = document.getElementById('settingsStatus_llmParams');
const settingsCurrentPassword = document.getElementById('settingsCurrentPassword');
const settingsNewPassword = document.getElementById('settingsNewPassword');
const settingsConfirmPassword = document.getElementById('settingsConfirmPassword');
const changePasswordBtn = document.getElementById('changePasswordBtn');
const passwordChangeStatus = document.getElementById('passwordChangeStatus');
const dataStoresModal = document.getElementById('dataStoresModal');
const createDataStoreForm = document.getElementById('createDataStoreForm');
const newDataStoreNameInput = document.getElementById('newDataStoreName');
const newDataStoreDescriptionInput = document.getElementById('newDataStoreDescription');
const createDataStoreStatus = document.getElementById('createDataStoreStatus');
const ownedDataStoresList = document.getElementById('ownedDataStoresList');
const sharedDataStoresList = document.getElementById('sharedDataStoresList');
const shareDataStoreModal = document.getElementById('shareDataStoreModal');
const shareDataStoreTitle = document.getElementById('shareDataStoreTitle');
const shareTargetUsernameDSInput = document.getElementById('shareTargetUsernameDS');
const confirmShareDataStoreBtn = document.getElementById('confirmShareDataStoreBtn');
const shareDataStoreStatus = document.getElementById('shareDataStoreStatus');
const shareDataStoreIdInput = document.getElementById('shareDataStoreIdInput');
const fileManagementModal = document.getElementById('fileManagementModal');
const fileManagerDataStoreName = document.getElementById('fileManagerDataStoreName');
const fileManagerCurrentDataStoreId = document.getElementById('fileManagerCurrentDataStoreId');
const fileVectorizerSelect = document.getElementById('fileVectorizerSelect');
const fileUploadInputFS = document.getElementById('fileUploadInputFS');
const confirmUploadBtn = document.getElementById('confirmUploadBtn');
const uploadStatus = document.getElementById('uploadStatus');
const indexedFileList = document.getElementById('indexedFileList');
const fileListStatus = document.getElementById('fileListStatus');
const imageViewerModal = document.getElementById('imageViewerModal');
const imageViewerSrc = document.getElementById('imageViewerSrc');
const themeToggleBtn = document.getElementById('themeToggleBtn');
const themeIconSun = document.getElementById('themeIconSun');
const themeIconMoon = document.getElementById('themeIconMoon');


// --- Helper: Check if element is in DOM ---
function isElementInDocument(element) {
    return element && document.body.contains(element);
}

// --- Localization Functions (translate, updateUIText, etc.) ---
// These functions are assumed to be mostly correct from your existing code.
// Ensure `translate` is robust for missing keys and uses fallbacks.
// `updateUIText` will need to be called after major UI changes or language load.
function translate(key, fallback = null, vars = {}) {
    let translation = currentTranslations[key];
    if (translation === undefined) {
        const parts = key.split('.');
        if (parts.length > 1) {
            parts.pop();
            const genericKey = parts.join('.');
            if (currentTranslations && currentTranslations[genericKey]) {
                translation = currentTranslations[genericKey];
            }
        }
    }
    if (translation === undefined) {
        return fallback !== null ? fallback : key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
    for (const varKey in vars) {
        translation = translation.replace(new RegExp(`{{${varKey}}}`, 'g'), vars[varKey]);
    }
    return translation;
}

function updateUIText() { // As provided, potentially needs to call renderDiscussionList, renderMessages etc.
    document.querySelectorAll('[data-translate-key]').forEach(el => {
        const key = el.dataset.translateKey;
        const fallback = el.dataset.fallback || el.textContent || el.placeholder || el.title || el.alt || ''; // More comprehensive fallback
        const translatedText = translate(key, fallback);

        if (el.dataset.translateAttr) {
            const attr = el.dataset.translateAttr;
            if (attr === 'placeholder') el.placeholder = translatedText;
            else if (attr === 'title') el.title = translatedText;
            else el.setAttribute(attr, translatedText);
        } else if (el.tagName === 'IMG' && el.alt !== undefined) { // Check specifically for alt on IMG
            el.alt = translatedText;
        } else if (el.childNodes.length === 1 && el.childNodes[0].nodeType === Node.TEXT_NODE) {
            el.textContent = translatedText; // Simple text content
        } else { // Handle elements with mixed content (text and other elements)
            let textNode = Array.from(el.childNodes).find(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim() !== '');
            if (textNode) textNode.textContent = translatedText;
            else if (el.firstChild && el.firstChild.nodeType !== Node.ELEMENT_NODE) { // If first child is text-like
                el.firstChild.textContent = translatedText;
            } else { // Fallback: Set textContent, might overwrite child elements if not careful
                 // Check if it's a button and only update the text part
                if (el.tagName === 'BUTTON') {
                    const textSpan = el.querySelector('span[data-btn-text="true"]'); // Add this span to buttons if needed
                    if (textSpan) textSpan.textContent = translatedText;
                    else { // Find first text node in button
                        let btnTextNode = Array.from(el.childNodes).find(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim() !== '');
                        if (btnTextNode) btnTextNode.textContent = translatedText;
                        else el.textContent = translatedText; // Last resort
                    }
                } else {
                    el.textContent = translatedText;
                }
            }
        }
    });

    renderDiscussionList();
    if (currentDiscussionId && discussions[currentDiscussionId]) {
        discussionTitle.textContent = discussions[currentDiscussionId].title;
        renderBranchTabsUI(currentDiscussionId); // Update branch tabs if discussion selected
    } else {
        discussionTitle.textContent = translate('default_discussion_title');
        const branchTabsContainer = document.getElementById('branchTabsContainer');
        if (branchTabsContainer) branchTabsContainer.innerHTML = ''; // Clear branch tabs
    }
    updateRagToggleButtonState();
    if (currentMessages.length > 0) {
        renderMessages(currentMessages);
    } else if (currentDiscussionId && discussions[currentDiscussionId] && (!discussions[currentDiscussionId].branches[activeBranchId] || discussions[currentDiscussionId].branches[activeBranchId].length === 0)) {
        chatMessages.innerHTML = `<div class="chat-empty-state"><div class="empty-state-content"><svg class="empty-state-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg><h3 class="empty-state-title">${translate('chat_area_no_messages_yet', 'No messages yet')}</h3><p class="empty-state-description">${translate('chat_area_start_conversation', 'Start a conversation by typing a message below.')}</p></div></div>`;
    } else if (!currentDiscussionId) {
        chatMessages.innerHTML = `<div class="text-center text-gray-500 italic mt-10">${translate('chat_area_empty_placeholder')}</div>`;
    } else { // Loading state for a selected discussion
        chatMessages.innerHTML = `<p class="text-gray-500 text-center italic mt-10">${translate('chat_area_loading_messages')}</p>`;
    }
}
// updateUIWithTranslations and initializeLocalization as before
async function loadLanguage(langCode) {
    appLoadingStatus.textContent = translate('app_loading_status_loading_language', `Loading ${langCode}...`, {lang_code: langCode});
    try {
        const response = await apiRequest(`/locals/${langCode}.json`);
        currentTranslations = await response.json();
        localStorage.setItem('preferredLang', langCode);
        if (languageSelector) languageSelector.value = langCode;
        document.documentElement.lang = langCode.split('-')[0];
        updateUIText(); // This should re-render everything with new translations
        appLoadingStatus.textContent = translate('app_loading_status_ready', "Ready.");
    } catch (error) {
        console.error(`Failed to load language ${langCode}:`, error);
        currentTranslations = {};
        updateUIText();
        appLoadingStatus.textContent = translate('app_loading_status_error_loading_language', `Error loading ${langCode}.`, {lang_code: langCode});
    }
}

async function initializeLocalization() {
    appLoadingStatus.textContent = "Localizing...";
    try {
        const response = await apiRequest('/api/languages/');
        availableLanguages = await response.json();
    } catch (e) {
        availableLanguages = { 'en': 'English' }; // Fallback
    }

    if (languageSelector) {
        languageSelector.innerHTML = '';
        for (const code in availableLanguages) {
            const option = document.createElement('option');
            option.value = code;
            option.textContent = availableLanguages[code];
            languageSelector.appendChild(option);
        }
        languageSelector.addEventListener('change', (e) => {
            loadLanguage(e.target.value);
        });
    }

    let langToLoad = localStorage.getItem('preferredLang');
    if (!langToLoad || !availableLanguages[langToLoad]) {
        const browserLang = navigator.language.split('-')[0];
        if (availableLanguages[browserLang]) {
            langToLoad = browserLang;
        } else {
            const fullBrowserLang = navigator.language;
            if (availableLanguages[fullBrowserLang]) {
                langToLoad = fullBrowserLang;
            } else {
                langToLoad = 'en';
                if (!availableLanguages['en']) {
                    const firstAvailable = Object.keys(availableLanguages)[0];
                    if(firstAvailable) langToLoad = firstAvailable;
                    else {
                        appLoadingStatus.textContent = "No languages available.";
                        return; // Critical error
                    }
                }
            }
        }
    }
    await loadLanguage(langToLoad);
}


// --- API Helper ---
async function apiRequest(url, options = {}) { // Mostly as provided
    if (!options.statusElement && statusMessage) showStatus('', 'info', statusMessage); // Clear global status
    const fetchOptions = { ...options };
    fetchOptions.headers = { ...fetchOptions.headers };

    if (tempLoginUsername && tempLoginPassword && !fetchOptions.headers['Authorization']) {
        const basicAuth = btoa(`${tempLoginUsername}:${tempLoginPassword}`);
        fetchOptions.headers['Authorization'] = `Basic ${basicAuth}`;
    }
    // Use activeGenerationAbortController only for specific cancellable requests (like chat)
    // Not for all POST/PUT requests.
    // if (activeGenerationAbortController && options.method && options.method.toUpperCase() !== 'GET') {
    // fetchOptions.signal = activeGenerationAbortController.signal;
    // }

    try {
        const response = await fetch(url, fetchOptions);
        if (!response.ok) {
            let errorDetail = `HTTP error ${response.status}`;
            try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; }
            catch (e) { /* Ignore if error response is not JSON */ }
            const errorMsg = translate('api_error_prefix', "API Error:") + ` ${errorDetail}`;
            showStatus(errorMsg, "error", options.statusElement || statusMessage);
            const error = new Error(errorMsg); error.status = response.status; throw error;
        }
        if (response.status === 204) return null; // No content
        return response;
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log("API Request Aborted:", url);
            showStatus(translate('api_request_aborted', "Request aborted by user."), "warning", options.statusElement || statusMessage);
        } else {
            console.error("API Request Error:", url, fetchOptions, error);
            // Only show status if it wasn't an AbortError and error.status is not already set (which means HTTP error was handled)
            if (!error.status) {
                 showStatus(translate('api_request_failed_prefix', "Request failed:") + ` ${error.message}`, "error", options.statusElement || statusMessage);
            }
        }
        throw error; // Re-throw to be handled by caller
    } finally {
        // Clear temp credentials after /me attempt if basic auth was used
        if (url === '/api/auth/me' && fetchOptions.headers['Authorization'] && fetchOptions.headers['Authorization'].startsWith('Basic')) {
            tempLoginUsername = null; tempLoginPassword = null;
        }
    }
}

// --- Initialization ---
window.onload = async () => {
    marked.setOptions({
        highlight: function (code, lang) {
            const language = hljs.getLanguage(lang) ? lang : 'plaintext';
            try {
                return hljs.highlight(code, { language, ignoreIllegals: true }).value;
            } catch (e) {
                return hljs.highlight(code, { language: 'plaintext', ignoreIllegals: true }).value;
            }
        },
        gfm: true,
        breaks: true
    });
    hljs.configure({ ignoreUnescapedHTML: true });

    initializeThemeToggle();
    await initializeLocalization();
    await attemptInitialAuthAndLoad();

    if (imageUploadInput) imageUploadInput.addEventListener('change', handleImageFileSelection);

    const settingsTabButtons = document.querySelectorAll('#settingsModal .settings-tab-btn');
    settingsTabButtons.forEach(button => {
        button.addEventListener('click', () => handleSettingsTabSwitch(button.dataset.tab));
    });

    if (userMenuToggleBtn) userMenuToggleBtn.addEventListener('click', toggleUserMenu);
    document.addEventListener('click', handleClickOutsideUserMenu);
    if (discussionSearchInput) discussionSearchInput.addEventListener('input', renderDiscussionList);

    // Event listeners from your original code
    if (confirmRenameBtn) confirmRenameBtn.onclick = confirmInlineRename;
    if (confirmSendDiscussionBtn) confirmSendDiscussionBtn.onclick = confirmSendDiscussion;
    if (confirmEditMessageBtn) confirmEditMessageBtn.onclick = confirmMessageEdit;
    if (logoutBtn) logoutBtn.onclick = handleLogout;
    if (loginSubmitBtn) loginSubmitBtn.onclick = handleLoginAttempt;
    if (loginPasswordInput) loginPasswordInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') handleLoginAttempt(); });
    if (createDataStoreForm) createDataStoreForm.addEventListener('submit', handleCreateDataStore);
    if (changePasswordBtn) changePasswordBtn.onclick = handleChangePassword;
    
    const sidebarLogoutBtn = document.getElementById('sidebarLogoutBtn');
    if (sidebarLogoutBtn) sidebarLogoutBtn.onclick = handleLogout;

    // Message input listeners
    if (messageInput) {
        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
            autoGrowTextarea(messageInput);
        });
        messageInput.addEventListener('input', () => {
            autoGrowTextarea(messageInput);
            if(sendMessageBtn) sendMessageBtn.disabled = !(messageInput.value.trim() || uploadedImageServerPaths.length > 0) || generationInProgress;
        });
    }
    if (sendMessageBtn) sendMessageBtn.onclick = () => sendMessage(); // Ensure it calls with no args for new message
    if (stopGenerationBtn) stopGenerationBtn.onclick = stopGeneration;

    // RAG Toggle
    if (ragToggleBtn) ragToggleBtn.onclick = () => {
        if (availableDataStoresForRag.length === 0) {
            showStatus(translate('rag_cannot_enable_no_stores_warning'), 'warning');
            return;
        }
        isRagActive = !isRagActive;
        updateRagToggleButtonState(); // This function should also handle ragDataStoreSelect visibility

        if (currentDiscussionId && discussions[currentDiscussionId]) {
            const disc = discussions[currentDiscussionId];
            if (isRagActive && !disc.rag_datastore_id && availableDataStoresForRag.length > 0) {
                // If RAG activated and no specific store for discussion, pick first available
                disc.rag_datastore_id = availableDataStoresForRag[0].id;
                if (ragDataStoreSelect) ragDataStoreSelect.value = disc.rag_datastore_id;
            } else if (!isRagActive) {
                // If RAG deactivated, clear discussion's RAG store
                disc.rag_datastore_id = null;
                if (ragDataStoreSelect) ragDataStoreSelect.value = "";
            }
            // Update backend about the change in discussion's RAG datastore
            updateDiscussionRagStoreOnBackend(currentDiscussionId, disc.rag_datastore_id);
        }
        showStatus(translate(isRagActive ? 'status_rag_active' : 'status_rag_inactive', `RAG is now ${isRagActive ? 'ACTIVE' : 'INACTIVE'}.`), 'info');
    };

    // RAG DataStore Select
    if (ragDataStoreSelect) ragDataStoreSelect.onchange = async () => {
        if (!currentDiscussionId || !discussions[currentDiscussionId]) return;
        const selectedDataStoreId = ragDataStoreSelect.value || null;
        discussions[currentDiscussionId].rag_datastore_id = selectedDataStoreId;
        await updateDiscussionRagStoreOnBackend(currentDiscussionId, selectedDataStoreId);
        updateRagToggleButtonState(); // To update tooltip
    };

    // File Management Modal listeners
    if (fileUploadInputFS) fileUploadInputFS.onchange = updateConfirmUploadBtnState;
    if (fileVectorizerSelect) fileVectorizerSelect.onchange = updateConfirmUploadBtnState;
    if (confirmUploadBtn) confirmUploadBtn.onclick = handleRagFileUpload; // Renamed for clarity

    // Export/Import listeners
    if (exportDataBtn) exportDataBtn.onclick = () => openModal('exportModal');
    if (confirmExportBtn) confirmExportBtn.onclick = handleExportData; // Renamed
    if (importDataBtn) importDataBtn.onclick = () => {
        if (importFile) importFile.value = '';
        if (importPreviewArea) importPreviewArea.style.display = 'none';
        if (importDiscussionList) importDiscussionList.innerHTML = '';
        if (confirmImportBtn) confirmImportBtn.disabled = true;
        showStatus('', 'info', importStatus);
        parsedImportData = null;
        openModal('importModal');
    };
    if (importFile) importFile.onchange = handleImportFileChange; // Renamed
    if (confirmImportBtn) confirmImportBtn.onclick = handleConfirmImport; // Renamed

    // Settings modal listeners
    if(settingsBtn) settingsBtn.onclick = () => openModal('settingsModal');
    if(dataStoresBtn) dataStoresBtn.onclick = () => openModal('dataStoresModal');
    // ... other settings listeners if they were missed ...
    if(saveModelAndVectorizerBtn) saveModelAndVectorizerBtn.onclick = handleSaveModelAndVectorizer;
    if(saveLLMParamsBtn) saveLLMParamsBtn.onclick = handleSaveLLMParams;


    // Initial render of empty chat area (if applicable)
    if (!currentDiscussionId && chatMessages) {
        chatMessages.innerHTML = `<div class="text-center text-gray-500 italic mt-10">${translate('chat_area_empty_placeholder')}</div>`;
    }
};

// --- Theme Management Functions ---
function applyTheme(theme) { /* As provided */
    if (theme === 'dark') {
        console.log("dark mode")
        document.documentElement.classList.add('dark');
        if (themeIconMoon) themeIconMoon.classList.remove('hidden');
        if (themeIconSun) themeIconSun.classList.add('hidden');
    } else {
        console.log("light mode")
        document.documentElement.classList.remove('dark');
        if (themeIconSun) themeIconSun.classList.remove('hidden');
        if (themeIconMoon) themeIconMoon.classList.add('hidden');
    }
    localStorage.setItem('theme', theme);
    currentTheme = theme;
}
function toggleTheme() { /* As provided */
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    applyTheme(newTheme);
}
function initializeThemeToggle() { /* As provided */
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', toggleTheme);
    }
    applyTheme(currentTheme);
}

// --- Auth and App Initialization ---
async function attemptInitialAuthAndLoad() { /* As provided */
    if (appLoadingStatus) appLoadingStatus.textContent = translate('app_loading_status_authenticating', "Authenticating...");
    if (appLoadingProgress) appLoadingProgress.style.width = '10%';
    try {
        const response = await apiRequest('/api/auth/me');
        currentUser = await response.json();
        if (loginModal) loginModal.classList.remove('active');
        if (appContainer) appContainer.style.display = 'flex';
        if (appLoadingMessage) appLoadingMessage.style.display = 'none';
        await initializeAppContent();
    } catch (error) {
        if (error.status === 401) {
            if (appLoadingMessage) appLoadingMessage.style.display = 'none';
            showStatus(translate('login_failed_or_required_status', "Login failed or required."), "error", loginStatus);
            openModal('loginModal', false);
            if (loginUsernameInput) loginUsernameInput.focus();
        } else {
            if (appLoadingStatus) appLoadingStatus.textContent = translate('initialization_failed_status', `Initialization failed: ${error.message}. Please refresh.`, { message: error.message });
            if (appLoadingStatus) appLoadingStatus.classList.add('text-red-600');
        }
    }
}
async function initializeAppContent() { /* Mostly as provided, with calls to new functions */
    if (appLoadingStatus) appLoadingStatus.textContent = translate('app_loading_status_user_data', "Loading user data...");
    if (appLoadingProgress) appLoadingProgress.style.width = '25%';
    if (usernameDisplay) usernameDisplay.textContent = currentUser.username;
    userDefaultVectorizer = currentUser.safe_store_vectorizer;

    if (currentUser.is_admin) {
        if (adminBadge) adminBadge.style.display = 'inline-block';
        if (adminLink) adminLink.style.display = 'flex';
    } else {
        if (adminBadge) adminBadge.style.display = 'none';
        if (adminLink) adminLink.style.display = 'none';
    }

    if (appLoadingStatus) appLoadingStatus.textContent = translate('app_loading_status_discussions_stores', "Loading discussions & data stores...");
    if (appLoadingProgress) appLoadingProgress.style.width = '50%';
    await Promise.all([
        loadDiscussions(), // This will now initialize client-side branch structures
        loadDataStores()
    ]);

    if (appLoadingStatus) appLoadingStatus.textContent = translate('app_loading_status_models_vectorizers', "Loading models and vectorizers...");
    if (appLoadingProgress) appLoadingProgress.style.width = '75%';
    await loadAvailableLollmsModels();
    if (appLoadingProgress) appLoadingProgress.style.width = '90%';

    updateRagToggleButtonState();
    if (appLoadingProgress) appLoadingProgress.style.width = '100%';
    if (appLoadingMessage) {
        setTimeout(() => {
            appLoadingMessage.style.opacity = '0';
            setTimeout(() => appLoadingMessage.style.display = 'none', 300);
        }, 500);
    }
    // Event listeners moved to onload for clarity
    showStatus(translate('status_ready', 'Ready.'), 'success');
    updateUIText();
}

// --- User Menu, Login, Logout, Modal Management (largely as provided) ---
// ... (Keep your existing functions: toggleUserMenu, handleClickOutsideUserMenu, handleLoginAttempt, handleLogout, openModal, closeModal) ...
// Ensure `handleLogout` clears new branch-related state if any (e.g., currentBranchId for a discussion)

// --- User Menu Logic ---
function toggleUserMenu() {
    const isHidden = userMenuDropdown.style.display === 'none' || userMenuDropdown.style.display === '';
    userMenuDropdown.style.display = isHidden ? 'block' : 'none';
    userMenuArrow.classList.toggle('rotate-180', isHidden);
}

function handleClickOutsideUserMenu(event) {
    if (userMenuDropdown.style.display === 'block' &&
        !userMenuToggleBtn.contains(event.target) &&
        !userMenuDropdown.contains(event.target)) {
        userMenuDropdown.style.display = 'none';
        userMenuArrow.classList.remove('rotate-180');
    }
}

// --- Login and Logout ---
async function handleLoginAttempt() {
    const username = loginUsernameInput.value.trim(); const password = loginPasswordInput.value;
    if (!username || !password) { showStatus(translate('login_username_password_required', "Username and password are required."), "error", loginStatus); return; }
    showStatus(translate('login_attempting_status', "Attempting login..."), "info", loginStatus); loginSubmitBtn.disabled = true;
    tempLoginUsername = username; tempLoginPassword = password;
    try { await attemptInitialAuthAndLoad(); }
    catch (error) {
        if (error.status === 401) showStatus(translate('login_invalid_credentials', "Invalid username or password."), "error", loginStatus);
        else showStatus(translate('login_error_status', `Login error: ${error.message}`, { message: error.message }), "error", loginStatus);
    } finally { loginSubmitBtn.disabled = false; }
}

async function handleLogout() {
    showStatus(translate('logout_status_logging_out', "Logging out..."), "info");
    try { await apiRequest('/api/auth/logout', { method: 'POST' }); }
    catch (error) { 
        showStatus(translate('logout_server_failed_status', "Logout from server failed, but resetting UI."), "warning"); 
    }
    finally {
        currentUser = null; discussions = {}; currentMessages = []; currentDiscussionId = null;
        aiMessageStreaming = false; currentAiMessageContainer = null; currentAiMessageContentAccumulator = ""; currentAiMessageId = null; currentAiMessageData = null;
        isRagActive = false; uploadedImageServerPaths = [];
        ownedDataStores = []; sharedDataStores = []; availableDataStoresForRag = [];
        generationInProgress = false; if (activeGenerationAbortController) activeGenerationAbortController.abort();

        usernameDisplay.textContent = translate('username_display_default'); 
        adminBadge.style.display = 'none'; adminLink.style.display = 'none';
        discussionListContainer.innerHTML = `<p class="text-gray-500 text-sm text-center italic p-4">${translate('login_required_placeholder')}</p>`;
        clearChatArea(true); sendMessageBtn.disabled = true; messageInput.value = ''; autoGrowTextarea(messageInput);
        ragToggleBtn.classList.remove('rag-toggle-on'); ragToggleBtn.classList.add('rag-toggle-off');
        ragDataStoreSelect.style.display = 'none'; 
        ragDataStoreSelect.innerHTML = `<option value="">${translate('rag_select_default_option')}</option>`;
        imageUploadPreviewContainer.innerHTML = ''; imageUploadPreviewContainer.style.display = 'none';
        updateRagToggleButtonState();
        userMenuDropdown.style.display = 'none'; userMenuArrow.classList.remove('rotate-180');

        appContainer.style.display = 'none'; 
        appLoadingMessage.style.opacity = '1';
        appLoadingMessage.style.display = 'flex';
        appLoadingProgress.style.width = '0%';
        appLoadingStatus.textContent = translate('app_loading_status_default');


        showStatus('', 'info', statusMessage); showStatus('', 'info', pyodideStatus);
        loginUsernameInput.value = ''; loginPasswordInput.value = ''; loginSubmitBtn.disabled = false;
        showStatus(translate('logout_success_status', "You have been logged out."), "info", loginStatus);
        openModal('loginModal', false); loginUsernameInput.focus();
    }
}


// --- Modal Management ---
function openModal(modalId, allowOverlayClose = true) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        modal.dataset.allowOverlayClose = allowOverlayClose.toString();
        if (modalId === 'loginModal' && loginUsernameInput) loginUsernameInput.focus();
        else if (modalId === 'settingsModal') { populateSettingsModal(); userMenuDropdown.style.display = 'none'; userMenuArrow.classList.remove('rotate-180');}
        else if (modalId === 'dataStoresModal') { populateDataStoresModal(); userMenuDropdown.style.display = 'none'; userMenuArrow.classList.remove('rotate-180');}
        else if (modalId === 'exportModal') { populateExportModal(); userMenuDropdown.style.display = 'none'; userMenuArrow.classList.remove('rotate-180');}
        else if (modalId === 'importModal') { userMenuDropdown.style.display = 'none'; userMenuArrow.classList.remove('rotate-180');}
        if (modalId === 'renameModal' && renameInput) renameInput.focus();
        if (modalId === 'sendDiscussionModal' && sendTargetUsernameInput) sendTargetUsernameInput.focus();
        if (modalId === 'editMessageModal' && editMessageInput) editMessageInput.focus();
        if (modalId === 'shareDataStoreModal' && shareTargetUsernameDSInput) shareTargetUsernameDSInput.focus();
    }
}
function closeModal(modalId) {
    const modal = document.getElementById(modalId); if (modal) modal.classList.remove('active');
    const statusElement = document.getElementById(modalId.replace('Modal', 'Status')); if (statusElement) showStatus('', 'info', statusElement);
    if (modalId === 'renameModal' && renameDiscussionIdInput) renameDiscussionIdInput.value = '';
    if (modalId === 'sendDiscussionModal' && sendDiscussionIdInput) { sendDiscussionIdInput.value = ''; if(sendTargetUsernameInput) sendTargetUsernameInput.value = ''; }
    if (modalId === 'editMessageModal' && editMessageIdInput) editMessageIdInput.value = '';
    if (modalId === 'shareDataStoreModal' && shareDataStoreIdInput) { shareDataStoreIdInput.value = ''; if(shareTargetUsernameDSInput) shareTargetUsernameDSInput.value = '';}
}
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', (event) => {
        const allowClose = modal.dataset.allowOverlayClose !== 'false';
        if (event.target === modal && allowClose) closeModal(modal.id);
    });
});
// --- Discussion Management ---
async function loadDiscussions() {
    try {
        const response = await apiRequest('/api/discussions');
        const loadedDiscussionsList = await response.json(); // This is List[DiscussionInfo]
        discussions = {}; // Reset
        backendCapabilities.checked = false; // Reset capability check

        loadedDiscussionsList.forEach(d_info => {
            discussions[d_info.id] = {
                id: d_info.id,
                title: d_info.title,
                is_starred: d_info.is_starred,
                rag_datastore_id: d_info.rag_datastore_id,
                last_activity_at: d_info.last_activity_at || d_info.created_at || `1970-01-01T00:00:00Z`,
                branches: { main: [] }, // Initialize client-side branch structure
                activeBranchId: d_info.active_branch_id || 'main', // Use from backend if available (new backend)
                messages_loaded_fully: {} // Per-branch loading status: { branchId: boolean }
            };
            // Basic branch support detection from discussion list structure
            if (!backendCapabilities.checked && typeof d_info.active_branch_id === 'string') {
                backendCapabilities.supportsBranches = true;
                // backendCapabilities.checked = true; // Check only once from list
            }
        });
        // If still not detected, can try further checks when loading individual discussion messages
        if (!backendCapabilities.checked && loadedDiscussionsList.length > 0) {
             // Heuristic: if any discussion implies branching, assume support for now.
             // A dedicated capabilities endpoint would be better.
        }


        renderDiscussionList();
        if (currentDiscussionId && discussions[currentDiscussionId]) {
            await selectDiscussion(currentDiscussionId); // Reselect if one was active
        } else if (currentDiscussionId) { // Was active, but now gone
            clearChatArea(true); currentDiscussionId = null;
        }
    } catch (error) {
        if (discussionListContainer) discussionListContainer.innerHTML = `<p class="text-red-500 text-sm text-center p-4">${translate('failed_to_load_discussions_error')}</p>`;
    }
}

function createDiscussionItemElement(d) { /* As provided, ensure it uses d.title, d.id correctly */
    const item = document.createElement('div');
    item.className = `discussion-item p-2.5 rounded-lg cursor-pointer flex justify-between items-center text-sm transition-colors duration-150 ${d.id === currentDiscussionId ? 'bg-blue-700 font-medium text-blue-100 hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-500' : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'}`;
    item.dataset.id = d.id; item.onclick = () => selectDiscussion(d.id);

    const titleSpan = document.createElement('span');
    titleSpan.textContent = d.title || translate('untitled_discussion_prefix', `Discussion ${d.id.substring(0, 6)}`, {id_short: d.id.substring(0,6)});
    titleSpan.className = 'truncate mr-2 flex-1 text-xs';

    const controlsDiv = document.createElement('div');
    controlsDiv.className = 'flex items-center flex-shrink-0';

    const actionsContainer = document.createElement('div');
    actionsContainer.className = 'discussion-item-actions-container';

    const sendBtn = document.createElement('button');
    sendBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" /></svg>`;
    sendBtn.title = translate('send_discussion_tooltip'); sendBtn.className = 'discussion-action-btn';
    sendBtn.onclick = (e) => { e.stopPropagation(); initiateSendDiscussion(d.id); };
    actionsContainer.appendChild(sendBtn);

    const renameBtn = document.createElement('button');
    renameBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125" /></svg>`;
    renameBtn.title = translate('rename_discussion_tooltip'); renameBtn.className = 'discussion-action-btn';
    renameBtn.onclick = (e) => { e.stopPropagation(); initiateInlineRename(d.id); };
    actionsContainer.appendChild(renameBtn);

    const deleteBtn = document.createElement('button');
    deleteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12.508 0A48.067 48.067 0 0 1 7.8 5.397m7.454 0M12 10.75h.008v.008H12v-.008Z" /></svg>`;
    deleteBtn.title = translate('delete_discussion_tooltip'); deleteBtn.className = 'discussion-action-btn destructive'; // Added destructive for potential styling
    deleteBtn.querySelector('svg')?.classList.add('text-red-500', 'dark:text-red-400'); // Style icon
    deleteBtn.onclick = (e) => { e.stopPropagation(); deleteInlineDiscussion(d.id); };
    actionsContainer.appendChild(deleteBtn);

    controlsDiv.appendChild(actionsContainer);

    const starSpan = document.createElement('button'); // Changed to button for accessibility
    starSpan.className = `discussion-action-btn p-1 ml-1 star-icon ${d.is_starred ? 'starred' : ''}`;
    starSpan.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="${d.is_starred ? 'currentColor' : 'none'}" viewBox="0 0 24 24" stroke-width="1.5" stroke="${d.is_starred ? 'none' : 'currentColor'}" class="w-4 h-4 transition-colors duration-150"><path stroke-linecap="round" stroke-linejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 21.1a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" /></svg>`;
    starSpan.title = d.is_starred ? translate('unstar_discussion_tooltip') : translate('star_discussion_tooltip');
    starSpan.onclick = (e) => { e.stopPropagation(); console.log("Star clicked"); toggleStarDiscussion(d.id, d.is_starred); renderDiscussionList(); console.log("Refreshed");};
    actionsContainer.appendChild(starSpan);

    item.appendChild(titleSpan);
    item.appendChild(controlsDiv);
    return item;
}
function renderDiscussionList() { /* As provided, uses createDiscussionItemElement */
    if (!discussionListContainer || !discussions) return;
    discussionListContainer.innerHTML = '';
    const searchTerm = discussionSearchInput ? discussionSearchInput.value.toLowerCase() : "";
    const allDiscussionValues = Object.values(discussions);

    const filteredDiscussions = searchTerm
        ? allDiscussionValues.filter(d => (d.title || '').toLowerCase().includes(searchTerm))
        : allDiscussionValues;

    // Sort by last_activity_at DESC, then by title ASC
    const sortByDateDesc = (a, b) => (new Date(b.last_activity_at || 0) - new Date(a.last_activity_at || 0)) || (a.title || '').localeCompare(b.title || '');

    const starredDiscussions = filteredDiscussions.filter(d => d.is_starred).sort(sortByDateDesc);
    const regularDiscussions = filteredDiscussions.filter(d => !d.is_starred).sort(sortByDateDesc);


    if (filteredDiscussions.length === 0) {
        discussionListContainer.innerHTML = `<p class="text-gray-500 dark:text-gray-400 text-sm text-center italic p-4">${searchTerm ? translate('no_discussions_match_search') : translate('no_discussions_yet')}</p>`;
        return;
    }

    if (starredDiscussions.length > 0) {
        const starredSection = document.createElement('div');
        starredSection.id = 'starredDiscussionsSection';
        const starredHeader = document.createElement('h3');
        starredHeader.className = 'discussion-section-header';
        starredHeader.textContent = translate('discussion_section_starred');
        starredSection.appendChild(starredHeader);
        const starredListDiv = document.createElement('div');
        starredListDiv.className = 'space-y-1 p-1'; // Added padding
        starredDiscussions.forEach(d => starredListDiv.appendChild(createDiscussionItemElement(d)));
        starredSection.appendChild(starredListDiv);
        discussionListContainer.appendChild(starredSection);
    } else if (searchTerm && allDiscussionValues.some(d => d.is_starred)) { // Show header even if search filters them out
        const starredSection = document.createElement('div');
        const starredHeader = document.createElement('h3');
        starredHeader.className = 'discussion-section-header';
        starredHeader.textContent = translate('discussion_section_starred');
        starredSection.appendChild(starredHeader);
        starredSection.innerHTML += `<p class="text-gray-500 dark:text-gray-400 text-xs text-center italic p-2">${translate('no_starred_discussions_match_search')}</p>`;
        discussionListContainer.appendChild(starredSection);
    }

    const regularSection = document.createElement('div');
    regularSection.id = 'regularDiscussionsSection';
    if (starredDiscussions.length > 0) regularSection.classList.add('mt-2'); // Spacing if starred section exists

    const regularHeader = document.createElement('h3');
    regularHeader.className = 'discussion-section-header';
    regularHeader.textContent = translate('discussion_section_recent');
    regularSection.appendChild(regularHeader);

    const regularListDiv = document.createElement('div');
    regularListDiv.className = 'space-y-1 p-1'; // Added padding
    if (regularDiscussions.length > 0) {
        regularDiscussions.forEach(d => regularListDiv.appendChild(createDiscussionItemElement(d)));
    } else {
        regularListDiv.innerHTML = `<p class="text-gray-500 dark:text-gray-400 text-xs text-center italic p-2">${searchTerm ? translate('no_other_discussions_match_search') : translate('no_other_discussions')}</p>`;
    }
    regularSection.appendChild(regularListDiv);
    discussionListContainer.appendChild(regularSection);
}


if (newDiscussionBtn) newDiscussionBtn.onclick = async () => {
    showStatus(translate('status_creating_discussion', 'Creating new discussion...'), 'info');
    try {
        const response = await apiRequest('/api/discussions', { method: 'POST' });
        const newDiscussionInfo = await response.json(); // This is DiscussionInfo
        discussions[newDiscussionInfo.id] = {
            id: newDiscussionInfo.id,
            title: newDiscussionInfo.title,
            is_starred: newDiscussionInfo.is_starred,
            rag_datastore_id: newDiscussionInfo.rag_datastore_id,
            last_activity_at: newDiscussionInfo.last_activity_at || new Date().toISOString(),
            branches: { main: [] }, // Initialize with an empty main branch
            activeBranchId: 'main',
            messages_loaded_fully: { main: true } // New discussion starts with "fully loaded" empty branch
        };
        renderDiscussionList();
        await selectDiscussion(newDiscussionInfo.id); // selectDiscussion now handles branches
        showStatus(translate('status_new_discussion_created', 'New discussion created.'), 'success');
    } catch (error) { /* apiRequest handles showing status */ }
};

async function selectDiscussion(id) {
    if (!discussions[id] || aiMessageStreaming) return;

    currentDiscussionId = id;
    const discussionData = discussions[id];

    // Ensure branching structure is initialized (might be redundant if loadDiscussions does it well)
    if (!discussionData.branches) discussionData.branches = { main: [] };
    if (!discussionData.activeBranchId || !discussionData.branches[discussionData.activeBranchId]) {
        discussionData.activeBranchId = 'main';
    }
    if (!discussionData.branches['main']) discussionData.branches['main'] = []; // Ensure main always exists
    
    activeBranchId = discussionData.activeBranchId; // Set global activeBranchId
    currentMessages = discussionData.branches[activeBranchId] || []; // Point to current branch's messages

    if (discussionTitle) discussionTitle.textContent = discussionData.title;
    if (sendMessageBtn) sendMessageBtn.disabled = false;
    renderDiscussionList(); // Highlight selected
    clearChatArea(false);
    if (chatMessages) chatMessages.innerHTML = `<p class="text-gray-500 dark:text-gray-400 text-center italic mt-10">${translate('chat_area_loading_messages')}</p>`;

    isRagActive = !!discussionData.rag_datastore_id;
    updateRagToggleButtonState();
    if (ragDataStoreSelect) {
        if (isRagActive && discussionData.rag_datastore_id) {
            ragDataStoreSelect.value = discussionData.rag_datastore_id;
        } else if (availableDataStoresForRag.length > 0) {
            ragDataStoreSelect.value = "";
        }
    }
    
    // Load messages for the active branch
    // The messages_loaded_fully check should be per-branch
    if (!discussionData.messages_loaded_fully || !discussionData.messages_loaded_fully[activeBranchId]) {
        try {
            let apiMessages;
            // For old backend or if explicit branch fetching isn't implemented for GET /messages
            // we always fetch all messages and assume they belong to 'main' or are undifferentiated.
            const messagesResponse = await apiRequest(`/api/discussions/${id}${backendCapabilities.supportsBranches ? '?branch_id=' + activeBranchId : ''}`);
            const rawMessages = await messagesResponse.json();

            if (Array.isArray(rawMessages) && rawMessages.length > 0 && typeof rawMessages[0].branch_id === 'string' && !backendCapabilities.checked) {
                backendCapabilities.supportsBranches = true; // Detected branch support from message structure
                backendCapabilities.checked = true;
            }


            if (backendCapabilities.supportsBranches) {
                // If new backend returns messages specifically for the branch, use them directly.
                // Or if it returns all branches, filter here.
                // For now, assume API returns messages for the requested branch_id.
                apiMessages = rawMessages.map(msg => ({ ...msg, steps: msg.steps || [], metadata: msg.metadata || [] }));
                discussionData.branches[activeBranchId] = apiMessages;
            } else {
                // Old backend: all messages go to 'main'.
                // If activeBranchId is not 'main', currentMessages will be a client-side filtered view later.
                apiMessages = rawMessages.map(msg => ({ ...msg, steps: msg.steps || [], metadata: msg.metadata || [], branch_id: 'main' })); // Assign to main
                discussionData.branches['main'] = apiMessages;
                if (activeBranchId !== 'main') {
                    // Create client-side branch view if not main
                    // This part is complex: how to define the subset for a client-side branch?
                    // For simplicity now, if backend doesn't support branches, we only truly support 'main'.
                    // Other "branches" created via UI might only be visual until a message is sent.
                    // For now, if backend is old, we only really operate on 'main'.
                    // If we are trying to view a client-side-only branch that has messages copied into it:
                    if (discussionData.branches[activeBranchId] && discussionData.branches[activeBranchId].length > 0){
                        // It means this branch was created by client-side copy, use its messages.
                        currentMessages = discussionData.branches[activeBranchId];
                    } else {
                         // Active branch is not main and has no messages, or backend is old.
                         // Default to showing main branch messages if activeBranch is not main and empty.
                         currentMessages = discussionData.branches['main'];
                         if (activeBranchId !== 'main') {
                            console.warn(`Backend doesn't support branches or branch ${activeBranchId} is empty. Showing 'main' branch content.`);
                            // Potentially switch activeBranchId back to 'main' visually if it's a non-functional branch.
                            // discussionData.activeBranchId = 'main'; activeBranchId = 'main';
                         }
                    }
                } else {
                     currentMessages = discussionData.branches['main'];
                }
            }
            
            discussionData.messages_loaded_fully = discussionData.messages_loaded_fully || {};
            discussionData.messages_loaded_fully[activeBranchId] = true;

            if (currentMessages.length > 0) {
                const lastMessage = currentMessages[currentMessages.length - 1];
                if (lastMessage.created_at && new Date(lastMessage.created_at) > new Date(discussionData.last_activity_at || 0)) {
                    discussionData.last_activity_at = lastMessage.created_at;
                    renderDiscussionList();
                }
            }
        } catch (error) {
            if (chatMessages) chatMessages.innerHTML = `<p class="text-red-500 dark:text-red-400 text-center mt-10">${translate('chat_area_error_loading_messages')}</p>`;
            discussionData.messages_loaded_fully = discussionData.messages_loaded_fully || {};
            discussionData.messages_loaded_fully[activeBranchId] = false; // Mark as not loaded on error
        }
    } else {
        // Messages for this branch already loaded
        currentMessages = discussionData.branches[activeBranchId] || [];
    }
    renderMessages(currentMessages);
    renderBranchTabsUI(id);
}

async function confirmInlineRename() { /* As provided, ensure it updates discussion list */
    const idToRename = renameDiscussionIdInput.value; if (!idToRename || !discussions[idToRename]) return;
    const newTitle = renameInput.value.trim(); if (!newTitle) { showStatus(translate('rename_title_empty_error'), 'error', renameStatus); return; }
    showStatus(translate('status_renaming', 'Renaming...'), 'info', renameStatus);
    try {
        const response = await apiRequest(`/api/discussions/${idToRename}/title`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: newTitle }), statusElement: renameStatus
        });
        const updatedInfo = await response.json(); // This is DiscussionInfo
        discussions[idToRename].title = updatedInfo.title;
        discussions[idToRename].last_activity_at = updatedInfo.last_activity_at || new Date().toISOString();
        if (idToRename === currentDiscussionId && discussionTitle) discussionTitle.textContent = updatedInfo.title;
        renderDiscussionList(); showStatus(translate('status_renamed_success', 'Renamed successfully.'), 'success', renameStatus);
        setTimeout(() => closeModal('renameModal'), 1000);
    } catch (error) { /* Handled by apiRequest */ }
}
// initiateSendDiscussion, confirmSendDiscussion, deleteInlineDiscussion, toggleStarDiscussion as provided.
function initiateSendDiscussion(id) {
    if (!discussions[id]) return;
    sendDiscussionIdInput.value = id;
    document.getElementById('sendDiscussionModal').querySelector('.modal-title').textContent = translate('send_discussion_modal_title', `Send Discussion: "${discussions[id].title}"`, {title: discussions[id].title});
    sendTargetUsernameInput.value = '';
    showStatus('', 'info', sendDiscussionStatus);
    openModal('sendDiscussionModal');
}
async function confirmSendDiscussion() {
    const discussionId = sendDiscussionIdInput.value;
    const targetUsername = sendTargetUsernameInput.value.trim();
    if (!discussionId || !targetUsername) {
        showStatus(translate('send_discussion_target_user_required'), 'error', sendDiscussionStatus);
        return;
    }
    showStatus(translate('status_sending_discussion_to_user', `Sending discussion to ${targetUsername}...`, {username: targetUsername}), 'info', sendDiscussionStatus);
    try {
        await apiRequest(`/api/discussions/${discussionId}/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_username: targetUsername }),
            statusElement: sendDiscussionStatus
        });
        showStatus(translate('status_discussion_sent_success', 'Discussion sent successfully!'), 'success', sendDiscussionStatus);
        setTimeout(() => closeModal('sendDiscussionModal'), 1500);
    } catch (error) { /* Handled by apiRequest */ }
}
async function deleteInlineDiscussion(id) {
        if (!discussions[id]) return;
        if (confirm(translate('confirm_delete_discussion', `Are you sure you want to delete discussion "${discussions[id].title}"? This cannot be undone.`, {title: discussions[id].title}))) {
            showStatus(translate('status_deleting_discussion', 'Deleting discussion...'), 'info');
            try {
                await apiRequest(`/api/discussions/${id}`, { method: 'DELETE' });
                delete discussions[id];
                if (id === currentDiscussionId) { currentDiscussionId = null; clearChatArea(true); }
                renderDiscussionList(); showStatus(translate('status_discussion_deleted', `Discussion deleted.`), 'success');
            } catch (error) { /* Handled by apiRequest */ }
        }
}
async function toggleStarDiscussion(id, isCurrentlyStarred) {
        const method = isCurrentlyStarred ? 'DELETE' : 'POST';
        try {
        const response = await apiRequest(`/api/discussions/${id}/star`, { method: method });
        const updatedInfo = await response.json();
        discussions[id].is_starred = updatedInfo.is_starred; 
        discussions[id].last_activity_at = updatedInfo.last_activity_at || discussions[id].last_activity_at || new Date().toISOString();
        renderDiscussionList();
        } catch (error) { showStatus(translate(isCurrentlyStarred ? 'status_unstar_failed' : 'status_star_failed', `Failed to ${isCurrentlyStarred ? 'unstar' : 'star'} discussion.`), 'error'); }
}

// --- Chat Interaction ---

function autoGrowTextarea(element) { 
    element.style.height = 'auto'; const maxHeight = 200;
    element.style.height = Math.min(element.scrollHeight, maxHeight) + 'px';
    element.style.overflowY = element.scrollHeight > maxHeight ? 'auto' : 'hidden';
}
       

async function sendMessage(branchFromUserMessageId = null, resendData = null) {
    if (generationInProgress || !currentDiscussionId) return;

    const currentDisc = discussions[currentDiscussionId];
    if (!currentDisc || !currentDisc.branches || !currentDisc.branches[activeBranchId]) {
        showStatus(translate('error_active_discussion_branch_missing', "Error: Active discussion branch missing."), "error");
        return;
    }
    // Ensure currentMessages is always up-to-date with the active branch
    currentMessages = currentDisc.branches[activeBranchId];

    let prompt;
    let imagePayloadForBackend = []; // This will hold server_paths for backend

    if (resendData) { // This path is taken by initiateBranch
        prompt = resendData.prompt;
        imagePayloadForBackend = resendData.image_server_paths || []; // Use server paths
    } else { // Normal new message
        prompt = messageInput.value.trim();
        // uploadedImageServerPaths contains { filename, server_path, file_obj }
        imagePayloadForBackend = uploadedImageServerPaths.map(img => img.server_path);
        if (!prompt && imagePayloadForBackend.length === 0) return;
    }

    generationInProgress = true;
    activeGenerationAbortController = new AbortController();
    if (sendMessageBtn) sendMessageBtn.style.display = 'none';
    if (stopGenerationBtn) { stopGenerationBtn.style.display = 'inline-flex'; stopGenerationBtn.disabled = false; }

    // Add user message to the current active branch (if not a resend that already did this)
    if (!resendData) {
        const tempUserMessageId = `temp-user-${Date.now()}`;
        const userMessageData = {
            id: tempUserMessageId,
            sender: translate(currentUser.lollms_client_ai_name ? 'sender_you' : (currentUser.username || 'sender_user'), 'User'),
            content: prompt,
            user_grade: 0, token_count: null, model_name: null,
            image_references: uploadedImageServerPaths.map(img => URL.createObjectURL(img.file_obj)), // For immediate display
            server_image_paths: imagePayloadForBackend, // For API
            steps: [], metadata: [],
            created_at: new Date().toISOString(),
            branch_id: activeBranchId, // Associate with active branch
            discussion_id: currentDiscussionId
        };
        currentMessages.push(userMessageData);
        renderMessage(userMessageData); // Render this new user message
    }

    const formData = new FormData();
    formData.append('prompt', prompt);
    formData.append('image_server_paths_json', JSON.stringify(imagePayloadForBackend));
    formData.append('use_rag', isRagActive.toString()); // Send as string
    if (isRagActive && currentDisc.rag_datastore_id) {
        formData.append('rag_datastore_id', currentDisc.rag_datastore_id);
    }

    // Branching parameters for new backend
    if (backendCapabilities.supportsBranches) {
        formData.append('branch_id', activeBranchId); // Always send current active branch
        if (resendData && branchFromUserMessageId) { // resendData implies is_resend
            formData.append('is_resend', 'true');
            formData.append('branch_from_message_id', branchFromUserMessageId);
        } else {
            formData.append('is_resend', 'false');
        }
    }


    if (!resendData) { // Clear input only for new messages, not for resends
        if (messageInput) messageInput.value = '';
        uploadedImageServerPaths = [];
        if (imageUploadPreviewContainer) {
            imageUploadPreviewContainer.innerHTML = '';
            imageUploadPreviewContainer.style.display = 'none';
        }
        if (messageInput) autoGrowTextarea(messageInput);
    }
    scrollChatToBottom();

    aiMessageStreaming = true;
    currentAiMessageContentAccumulator = "";
    currentAiMessageId = `temp-ai-${Date.now()}`; // Temporary ID for AI message
    currentAiMessageData = { // Placeholder data for the AI message
        id: currentAiMessageId,
        sender: currentUser.lollms_client_ai_name || translate('sender_assistant', 'Assistant'),
        content: "", user_grade: 0, token_count: null, model_name: null,
        image_references: [], steps: [], metadata: [],
        created_at: new Date().toISOString(),
        branch_id: activeBranchId, // AI message belongs to the same active branch
        discussion_id: currentDiscussionId
    };
    currentMessages.push(currentAiMessageData);
    renderMessage(currentAiMessageData); // Initial render of AI placeholder

    // Cache the DOM elements for the AI message *after* initial render
    currentAiMessageDomContainer = document.querySelector(`.message-container[data-message-id="${currentAiMessageId}"]`);
    currentAiMessageDomBubble = document.getElementById(`message-${currentAiMessageId}`); // Assuming bubble gets this ID

    if (!isElementInDocument(currentAiMessageDomContainer) || !isElementInDocument(currentAiMessageDomBubble)) {
        console.error("sendMessage: AI placeholder DOM elements not found after initial render!");
        // Fallback or error handling
        generationInProgress = false; aiMessageStreaming = false;
        if(sendMessageBtn) sendMessageBtn.style.display = 'inline-flex';
        if(stopGenerationBtn) stopGenerationBtn.style.display = 'none';
        currentMessages.pop(); // Remove the failed placeholder
        return;
    }


    currentDisc.last_activity_at = new Date().toISOString();
    renderDiscussionList();

    try {
        const response = await fetch(`/api/discussions/${currentDiscussionId}/chat`, {
            method: 'POST',
            body: formData,
            signal: activeGenerationAbortController.signal // Add signal here
        });

        if (!response.ok || !response.body) {
            let errorDetailMessage = `HTTP error ${response.status}`;
            try { const errorData = await response.json(); errorDetailMessage = errorData.detail || errorDetailMessage; } catch (e) { /* ignore */ }
            throw new Error(translate('chat_stream_start_error', `Error starting chat stream: ${errorDetailMessage}`, { detail: errorDetailMessage }));
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
            if (!generationInProgress) { if (reader.cancel) await reader.cancel('User requested stop'); break; }
            const { done, value } = await reader.read();
            if (done) break;
            if (!generationInProgress) { if (reader.cancel) await reader.cancel('User requested stop mid-stream'); break; }

            const textChunk = decoder.decode(value, { stream: true });
            const lines = textChunk.split('\n').filter(line => line.trim() !== '');
            lines.forEach(line => {
                try {
                    const parsedLine = JSON.parse(line);
                    // Check for a special message type that might confirm the AI message ID
                    if (parsedLine.type === 'final_ai_message_id' && parsedLine.id && currentAiMessageData && currentAiMessageData.id === currentAiMessageId) {
                        // Backend confirmed/provided the final ID for the AI message.
                        // Update client-side ID if different.
                        const oldId = currentAiMessageId;
                        const newId = parsedLine.id;
                        if (oldId !== newId) {
                            console.log(`AI Message ID confirmed/updated: ${oldId} -> ${newId}`);
                            currentAiMessageId = newId;
                            currentAiMessageData.id = newId;

                            // Update DOM element IDs
                            if (isElementInDocument(currentAiMessageDomContainer)) currentAiMessageDomContainer.dataset.messageId = newId;
                            if (isElementInDocument(currentAiMessageDomBubble)) currentAiMessageDomBubble.id = `message-${newId}`;
                            
                            // Update in currentMessages array
                            const msgIndex = currentMessages.findIndex(m => m.id === oldId);
                            if (msgIndex > -1) currentMessages[msgIndex].id = newId;
                        }
                    } else {
                        handleStreamChunk(parsedLine);
                    }
                } catch (e) {
                    console.error("sendMessage: Error parsing stream line:", line, e);
                    // Render a system error message in the chat
                    const systemErrorMsg = {
                        id: `syserr-${Date.now()}`, sender: 'system',
                        content: translate('malformed_data_chunk_error', 'Malformed data chunk from server.'),
                        steps: [], metadata: [], branch_id: activeBranchId, discussion_id: currentDiscussionId
                    };
                    currentMessages.push(systemErrorMsg); renderMessage(systemErrorMsg);
                }
            });
        }
        if (generationInProgress) handleStreamEnd(false); // False = not an error
    } catch (error) {
        if (error.name === 'AbortError') {
            showStatus(translate('status_generation_cancelled_by_user', 'Generation cancelled by user.'), 'info');
             // handleStreamEnd will be called by stopGeneration if that was the source of abort
             // If abort came from elsewhere (e.g. navigation), ensure stream ends.
            if (generationInProgress) handleStreamEnd(true, true); // error=true, wasAborted=true
        } else {
            showStatus(translate('chat_stream_failed_error', `Chat stream failed: ${error.message}`, { message: error.message }), "error");
            const streamErrorMsg = {
                id: `syserr-${Date.now()}`, sender: 'system',
                content: translate('stream_error_prefix', `Stream Error: ${error.message}`, { message: error.message }),
                steps: [], metadata: [], branch_id: activeBranchId, discussion_id: currentDiscussionId
            };
            currentMessages.push(streamErrorMsg); renderMessage(streamErrorMsg);
            if (generationInProgress) handleStreamEnd(true); // error=true
        }
    } finally {
        // This finally block ensures UI reset even if errors occur before or during fetch
        if (generationInProgress) generationInProgress = false; // Should be set by handleStreamEnd or stopGeneration

        if(sendMessageBtn) sendMessageBtn.style.display = 'inline-flex';
        if(stopGenerationBtn) stopGenerationBtn.style.display = 'none';
        if(sendMessageBtn && messageInput) sendMessageBtn.disabled = !(messageInput.value.trim() || uploadedImageServerPaths.length > 0);
        
        activeGenerationAbortController = null;
        // Clear DOM element caches
        currentAiMessageDomContainer = null;
        currentAiMessageDomBubble = null;
    }
}

function handleStreamChunk(data) { // Patched to use cached DOM elements
    if (!currentAiMessageData || currentAiMessageData.id !== currentAiMessageId) {
        // If currentAiMessageData was reset or ID changed unexpectedly, log and skip.
        // This can happen if handleStreamEnd was called prematurely or due to race conditions.
        console.warn("handleStreamChunk: Mismatch or missing currentAiMessageData. Skipping chunk for ID:", currentAiMessageId, "Data:", data);
        return;
    }

    // Critical: Ensure the cached DOM elements are still valid and in the document.
    if (!isElementInDocument(currentAiMessageDomContainer) || !isElementInDocument(currentAiMessageDomBubble)) {
        console.error("handleStreamChunk: AI message DOM elements are invalid or not in document. Attempting to re-find for ID:", currentAiMessageId);
        currentAiMessageDomContainer = document.querySelector(`.message-container[data-message-id="${currentAiMessageId}"]`);
        currentAiMessageDomBubble = document.getElementById(`message-${currentAiMessageId}`);
        if (!isElementInDocument(currentAiMessageDomContainer) || !isElementInDocument(currentAiMessageDomBubble)) {
            console.error("handleStreamChunk: CRITICAL - Unable to re-find AI message DOM elements for ID:", currentAiMessageId, ". Stream updates may fail.");
            // Optionally, could attempt a full re-render of the last AI message if data is available,
            // but this might cause flickering. For now, log and potentially lose this chunk update.
            return;
        }
    }

    let needsRerender = false;
    if (data.type === 'chunk') {
        currentAiMessageContentAccumulator += data.content;
        currentAiMessageData.content = currentAiMessageContentAccumulator;
        needsRerender = true;
    } else if (data.type === 'step_update') {
        currentAiMessageData.steps = data.steps || [];
        needsRerender = true;
    } else if (data.type === 'metadata_update') {
        currentAiMessageData.metadata = data.metadata || [];
        needsRerender = true;
    } else if (data.type === 'error') {
        const errorMsgData = { id: `err-stream-${Date.now()}`, sender: 'system', content: translate('llm_error_prefix', `LLM Error: ${data.content}`, { content: data.content }), steps: [], metadata: [], branch_id: activeBranchId, discussion_id: currentDiscussionId };
        currentMessages.push(errorMsgData); renderMessage(errorMsgData);
        handleStreamEnd(true); // error=true
        return;
    } else if (data.type === 'info' && data.content === "Generation stopped by user.") {
        showStatus(translate('status_generation_stopped_by_user', 'Generation stopped by user.'), 'info');
        // Stream will end; generationInProgress likely already false if stopGeneration was called.
        return;
    }

    if (needsRerender) {
        // Pass the cached DOM elements to renderMessage for targeted update
        renderMessage(currentAiMessageData, currentAiMessageDomContainer, currentAiMessageDomBubble);
        scrollChatToBottom();
    }
}

function handleStreamEnd(errorOccurred = false, wasAbortedByStopButton = false) {
    const wasManuallyStopped = !generationInProgress && !errorOccurred; // If genInProgress already false due to stopGeneration
    
    aiMessageStreaming = false;
    if (generationInProgress) generationInProgress = false; // Ensure it's set to false here
    // activeGenerationAbortController is cleared by sendMessage's finally or stopGeneration

    if(sendMessageBtn) sendMessageBtn.style.display = 'inline-flex';
    if(stopGenerationBtn) stopGenerationBtn.style.display = 'none';
    // stopGenerationBtn.disabled = false; // Handled by stopGeneration
    if(sendMessageBtn && messageInput) sendMessageBtn.disabled = !(messageInput.value.trim() || uploadedImageServerPaths.length > 0);

    // Finalize the AI message in currentMessages if it exists
    // The message object currentAiMessageData itself should be up-to-date from handleStreamChunk
    // We just need to ensure it's correctly represented in the currentMessages array
    // and potentially re-render it if its final state changed (e.g. error step added)

    if (currentAiMessageData) {
        const msgIndex = currentMessages.findIndex(m => m.id === currentAiMessageId);
        if (msgIndex > -1) {
            currentMessages[msgIndex] = { ...currentAiMessageData }; // Ensure array has the latest version
            // Add final step if error or manual stop not already reflected
            let finalStepAdded = false;
            if (errorOccurred && !currentMessages[msgIndex].steps.some(s => s.status === 'error')) {
                currentMessages[msgIndex].steps.push({ text: translate('step_error_occurred', "An error occurred."), status: 'error', done: true });
                finalStepAdded = true;
            } else if ((wasManuallyStopped || wasAbortedByStopButton) && !currentMessages[msgIndex].steps.some(s => s.status === 'stopped')) {
                currentMessages[msgIndex].steps.push({ text: translate('step_generation_stopped_by_user', "Generation stopped."), status: 'stopped', done: true });
                finalStepAdded = true;
            }
            if (finalStepAdded && isElementInDocument(currentAiMessageDomBubble)) {
                 renderMessage(currentMessages[msgIndex], currentAiMessageDomContainer, currentAiMessageDomBubble); // Re-render with final step
            }
        }
    }
    
    // It's crucial that currentAiMessageData is nulled *after* refreshMessagesAfterStream
    // if refresh relies on its ID for some reason, or before if refresh rebuilds everything.
    // Since refreshMessagesAfterStream fetches fresh data, nulling here is okay.
    const lastAiMessageId = currentAiMessageId; // Keep for refresh check

    currentAiMessageContentAccumulator = "";
    currentAiMessageData = null;
    currentAiMessageId = null;
    // DOM element caches are cleared by sendMessage's finally block

    if (currentDiscussionId) {
        // Refresh only if not a clean manual stop, or if an error occurred, to get definitive state.
        // A clean manual stop might have partially streamed content the user wants to see before refresh.
        if (errorOccurred || !wasManuallyStopped || !wasAbortedByStopButton) {
            refreshMessagesAfterStream(lastAiMessageId);
        }
    }
    scrollChatToBottom();

    if (wasManuallyStopped || wasAbortedByStopButton) {
        showStatus(translate('status_generation_process_halted', 'Generation process halted.'), 'info');
    }
}

async function stopGeneration() {
    if (!generationInProgress || !currentDiscussionId) return;

    if(stopGenerationBtn) stopGenerationBtn.disabled = true;
    showStatus(translate('status_stopping_generation', 'Attempting to stop generation...'), 'info');

    if (activeGenerationAbortController) {
        activeGenerationAbortController.abort(); // Signal fetch to abort
    }
    // Set generationInProgress to false *immediately* so handleStreamChunk stops processing new chunks
    // and handleStreamEnd knows it was a manual stop.
    const wasInProgress = generationInProgress;
    generationInProgress = false; 

    try {
        // This API call is a "best effort" to tell the backend.
        // Client-side abort is the primary stop mechanism for the stream.
        await apiRequest(`/api/discussions/${currentDiscussionId}/stop_generation`, {
            method: 'POST'
        });
        showStatus(translate('status_stop_signal_sent', 'Stop signal sent to server.'), 'info');
    } catch (error) {
        showStatus(translate('status_stop_signal_failed_client_halted', `Stop signal to server failed, but client generation halted. ${error.message}`), 'warning');
    } finally {
        // Ensure UI reset and stream end handling occurs
        if (wasInProgress) { // Only call handleStreamEnd if generation was truly in progress
            handleStreamEnd(false, true); // error=false, wasAbortedByStopButton=true
        }
        // Redundant if handleStreamEnd does it, but safe:
        if(sendMessageBtn) sendMessageBtn.style.display = 'inline-flex';
        if(stopGenerationBtn) { stopGenerationBtn.style.display = 'none'; stopGenerationBtn.disabled = false; }
        if(sendMessageBtn && messageInput) sendMessageBtn.disabled = !(messageInput.value.trim() || uploadedImageServerPaths.length > 0);
        
        // Clear data related to the (now stopped) AI message stream
        currentAiMessageContentAccumulator = "";
        // currentAiMessageData and currentAiMessageId are cleared by handleStreamEnd or subsequent refresh
        // DOM caches currentAiMessageDomContainer/Bubble are cleared by sendMessage finally or if re-found by handleStreamChunk
        scrollChatToBottom();
    }
}


async function refreshMessagesAfterStream(lastStreamedAiMessageId = null) {
    await new Promise(resolve => setTimeout(resolve, 250)); // Small delay
    if (!currentDiscussionId || aiMessageStreaming || generationInProgress) return;

    const currentDisc = discussions[currentDiscussionId];
    if (!currentDisc || !currentDisc.branches || !currentDisc.branches[activeBranchId]) {
        return;
    }

    try {
        // Determine which branch's messages to fetch
        const branchToFetch = backendCapabilities.supportsBranches ? activeBranchId : 'main';
        const response = await apiRequest(`/api/discussions/${currentDiscussionId}${backendCapabilities.supportsBranches ? '?branch_id=' + branchToFetch : ''}`);
        const loadedMessagesRaw = await response.json();

        // Detect branch support based on message structure if not already known
        if (!backendCapabilities.checked && Array.isArray(loadedMessagesRaw) && loadedMessagesRaw.length > 0 && typeof loadedMessagesRaw[0].branch_id === 'string') {
            backendCapabilities.supportsBranches = true;
            backendCapabilities.checked = true;
        }
        
        const processedMessages = loadedMessagesRaw.map(msg => ({
            ...msg,
            steps: msg.steps || [],
            metadata: msg.metadata || [],
            branch_id: backendCapabilities.supportsBranches ? msg.branch_id : 'main' // Ensure branch_id
        }));

        if (backendCapabilities.supportsBranches) {
            currentDisc.branches[branchToFetch] = processedMessages;
        } else {
            // Old backend, all messages are for 'main'
            currentDisc.branches['main'] = processedMessages;
            // If activeBranchId was something else, its client-side copy remains.
            // The user experience for "old backend + client branches" is that only 'main' gets server updates.
        }
        currentMessages = currentDisc.branches[activeBranchId] || []; // Update currentMessages to reflect the active branch

        if (currentMessages.length > 0) {
            const lastMessage = currentMessages[currentMessages.length - 1];
            if (lastMessage.created_at && (!currentDisc.last_activity_at || new Date(lastMessage.created_at) > new Date(currentDisc.last_activity_at))) {
                currentDisc.last_activity_at = lastMessage.created_at;
            }
        } else if (currentDisc.branches['main'] && currentDisc.branches['main'].length > 0) {
            // Fallback to main branch for last activity if active branch is empty
            const lastMainMessage = currentDisc.branches['main'][currentDisc.branches['main'].length-1];
             if (lastMainMessage.created_at && (!currentDisc.last_activity_at || new Date(lastMainMessage.created_at) > new Date(currentDisc.last_activity_at))) {
                currentDisc.last_activity_at = lastMainMessage.created_at;
            }
        }
         else { // If all branches are empty, fetch discussion list to update activity time from server potentially
            const discussionsListResponse = await apiRequest('/api/discussions');
            const allDiscs = await discussionsListResponse.json();
            const updatedDiscInfo = allDiscs.find(d => d.id === currentDiscussionId);
            if (updatedDiscInfo && updatedDiscInfo.last_activity_at) {
                currentDisc.last_activity_at = updatedDiscInfo.last_activity_at;
            }
        }

        renderMessages(currentMessages);
        renderDiscussionList(); // Update discussion list (e.g. last activity time)
        renderBranchTabsUI(currentDiscussionId); // Update branch tabs
    } catch (error) {
        const errorMsgData = { id: `err-refresh-${Date.now()}`, sender: 'system', content: translate('refresh_message_list_failed_error'), steps: [], metadata: [], branch_id: activeBranchId, discussion_id: currentDiscussionId };
        // Avoid pushing to currentMessages if it's about to be overwritten or cleared
        if (chatMessages) { // Directly render the error if chatMessages is available
            const tempContainer = document.createElement('div');
            renderMessage(errorMsgData, tempContainer); // Render into a temp container
            chatMessages.appendChild(tempContainer.firstChild); // Append the message container
        } else {
            console.error("Chat messages container not found for error display.");
        }
    }
}


// --- Message Rendering (renderMessage, renderProcessedContent, etc.) ---
function clearChatArea(clearHeader = true) {
    if(chatMessages) chatMessages.innerHTML = '';
    if (clearHeader) {
        if(discussionTitle) discussionTitle.textContent = translate('default_discussion_title');
        if(sendMessageBtn) sendMessageBtn.disabled = true;
        if(ragToggleBtn) {
            ragToggleBtn.classList.remove('rag-toggle-on'); ragToggleBtn.classList.add('rag-toggle-off');
        }
        if(ragDataStoreSelect) { ragDataStoreSelect.style.display = 'none'; ragDataStoreSelect.value = ''; }
        isRagActive = false; updateRagToggleButtonState();
        const branchTabsContainer = document.getElementById('branchTabsContainer');
        if (branchTabsContainer) branchTabsContainer.innerHTML = ''; // Clear branch tabs
    } else {
        if (!currentDiscussionId && chatMessages) {
            chatMessages.innerHTML = `<div class="text-center text-gray-500 dark:text-gray-400 italic mt-10">${translate('chat_area_empty_placeholder')}</div>`;
        }
    }
    currentMessages = [];
    currentAiMessageDomContainer = null; currentAiMessageDomBubble = null;
    currentAiMessageContentAccumulator = ""; currentAiMessageId = null; currentAiMessageData = null;
}

// `renderMessage` from your "Enhanced message rendering" section, adapted for the new DOM caching.
// This is the "full" renderMessage you provided, slightly adapted.
function renderMessage(message, existingContainer = null, existingBubble = null) {
    if (!message || typeof message.sender === 'undefined' || (typeof message.content === 'undefined' && (!message.image_references || message.image_references.length === 0) && (!message.steps || message.steps.length === 0) && (!message.metadata || message.metadata.length === 0) && !(message.id === currentAiMessageId && (aiMessageStreaming || generationInProgress) ))) { // Allow rendering empty streaming AI msg
        return;
    }

    const messageId = message.id || `temp-render-${Date.now()}`;
    const domIdForBubble = `message-${messageId}`; // ID for the bubble div itself

    let messageContainerToUse = isElementInDocument(existingContainer) ? existingContainer : document.querySelector(`.message-container[data-message-id="${messageId}"]`);
    let bubbleDivToUse = isElementInDocument(existingBubble) && existingBubble.id === domIdForBubble ? existingBubble : null;

    if (isElementInDocument(messageContainerToUse) && !isElementInDocument(bubbleDivToUse)) {
        // Container exists, but bubble might have been cleared or is incorrect. Try to find it.
        bubbleDivToUse = messageContainerToUse.querySelector(`#${domIdForBubble}`);
    }
    
    const isUpdate = isElementInDocument(messageContainerToUse) && isElementInDocument(bubbleDivToUse);

    if (isUpdate) {
        // Clear dynamic parts for update
        const elementsToClearOrRebuild = ['.sender-name', '.message-images-container', '.message-timestamp', '.message-content', '.message-footer'];
        elementsToClearOrRebuild.forEach(selector => {
            const el = bubbleDivToUse.querySelector(selector);
            if (el) {
                if (selector === '.message-content' || selector === '.message-footer') el.innerHTML = ''; // Clear content for rebuild
                else el.remove(); // Remove structural elements like sender, images, timestamp for rebuild
            }
        });
    } else { // Create new elements
        messageContainerToUse = document.createElement('div');
        messageContainerToUse.className = 'message-container flex flex-col';
        messageContainerToUse.dataset.messageId = messageId;

        bubbleDivToUse = document.createElement('div');
        // bubbleDivToUse.id = domIdForBubble; // Set by enhanced styles later if needed, but good to have
        messageContainerToUse.appendChild(bubbleDivToUse);
        if(chatMessages) chatMessages.appendChild(messageContainerToUse);
        else { console.error("renderMessage: chatMessages DOM element not found!"); return; }

        messageContainerToUse.style.opacity = '0';
        messageContainerToUse.style.transform = 'translateY(20px)';
        requestAnimationFrame(() => {
            messageContainerToUse.style.transition = 'all 0.3s ease-out';
            messageContainerToUse.style.opacity = '1';
            messageContainerToUse.style.transform = 'translateY(0)';
        });
    }

    bubbleDivToUse.id = domIdForBubble; // Ensure ID is set/updated

    // Handle spacing (as before)
    if (message.addSpacing && messageContainerToUse.previousElementSibling) {
        messageContainerToUse.classList.add('mt-4');
    } else {
        messageContainerToUse.classList.remove('mt-4');
    }

    // Determine bubble type and styling (as before)
    let bubbleClass = 'ai-bubble';
    let senderNameForDisplay = getSenderNameText(message); // Use helper
    let showGradeControls = false; // Renamed from showGrade for clarity
    const userNames = [currentUser.username, 'user', 'You', translate('sender_you', 'You'), translate('sender_user', 'User')];
    if (currentUser.lollms_client_ai_name === null || currentUser.lollms_client_ai_name === undefined) { // If AI name is not set, user is effectively the AI
         // This case is tricky. If lollms_client_ai_name is null, it means the user IS the AI.
         // So "User" messages are from "other users" if multi-user is deeply implemented.
         // For single-user context or if client_ai_name is just not set, this logic might need adjustment.
         // Assuming current logic: if message.sender matches User-like names, it's a user-bubble.
    }

    if (userNames.includes(message.sender) || (message.sender === "User" && currentUser.username === "user") || (currentUser.lollms_client_ai_name === null && message.sender === currentUser.username)) {
        bubbleClass = 'user-bubble';
        senderNameForDisplay = ''; // User bubbles don't typically show "User"
    } else if (message.sender && (message.sender.toLowerCase() === 'system' || message.sender.toLowerCase() === 'error')) {
        bubbleClass = 'system-bubble';
        senderNameForDisplay = '';
    } else { // AI or other named sender
        bubbleClass = 'ai-bubble';
        // senderNameForDisplay is already set by getSenderNameText
        showGradeControls = !messageId.startsWith('temp-');
    }
    bubbleDivToUse.className = `message-bubble ${bubbleClass}`;

    // Timestamp (rebuild if not present or update)
    let timestampDiv = bubbleDivToUse.querySelector('.message-timestamp');
    if (message.timestamp || message.created_at) {
        if (!timestampDiv) {
            timestampDiv = document.createElement('div');
            timestampDiv.className = 'message-timestamp';
            bubbleDivToUse.insertBefore(timestampDiv, bubbleDivToUse.firstChild); // Timestamps often at top or bottom
        }
        const timestampDate = new Date(message.timestamp || message.created_at);
        timestampDiv.textContent = formatTimestamp(timestampDate);
    } else if (timestampDiv) {
        timestampDiv.remove();
    }


    // Sender Name (rebuild if not present or update)
    let senderDiv = bubbleDivToUse.querySelector('.sender-name');
    if (senderNameForDisplay) {
        if (!senderDiv) {
            senderDiv = document.createElement('div');
            senderDiv.className = 'sender-name';
            // Insert after timestamp if it exists, otherwise at the top
            const existingTimestampDiv = bubbleDivToUse.querySelector('.message-timestamp');
            bubbleDivToUse.insertBefore(senderDiv, existingTimestampDiv ? existingTimestampDiv.nextSibling : bubbleDivToUse.firstChild);
        }
        // Use innerHTML for avatar and model badge structure
        senderDiv.innerHTML = `
            <div class="flex items-center gap-2">
                <span class="sender-avatar-placeholder"></span> <!-- Placeholder for JS-generated avatar -->
                <span class="sender-text">${escapeHtml(senderNameForDisplay)}</span>
                ${message.model_name ? `<span class="model-badge">${escapeHtml(message.model_name)}</span>` : ''}
            </div>
        `;
        // JS-generated avatar
        const avatarPlaceholder = senderDiv.querySelector('.sender-avatar-placeholder');
        if(avatarPlaceholder) avatarPlaceholder.outerHTML = getSenderAvatar(senderNameForDisplay);

    } else if (senderDiv) {
        senderDiv.remove(); // Remove if no sender name to display
    }


    // Images (rebuild if not present or update)
    let imagesContainer = bubbleDivToUse.querySelector('.message-images-container');
    if (message.image_references && message.image_references.length > 0) {
        if (!imagesContainer) {
            imagesContainer = document.createElement('div');
            imagesContainer.className = 'message-images-container';
            const anchor = bubbleDivToUse.querySelector('.sender-name') || bubbleDivToUse.querySelector('.message-timestamp');
            bubbleDivToUse.insertBefore(imagesContainer, anchor ? anchor.nextSibling : bubbleDivToUse.firstChild);
        }
        imagesContainer.innerHTML = ''; // Clear existing images
        message.image_references.forEach(imgSrc => {
            const imgItem = document.createElement('div'); imgItem.className = 'message-image-item';
            const imgTag = document.createElement('img'); imgTag.src = imgSrc; imgTag.alt = translate('chat_image_alt', 'Chat Image');
            imgTag.loading = 'lazy'; imgTag.onclick = () => viewImage(imgSrc);
            imgTag.onload = () => imgItem.classList.add('loaded');
            imgTag.onerror = () => imgItem.classList.add('error');
            imgItem.appendChild(imgTag); imagesContainer.appendChild(imgItem);
        });
    } else if (imagesContainer) {
        imagesContainer.remove();
    }

    // Content (get or create, then populate by renderEnhancedContent)
    let contentDiv = bubbleDivToUse.querySelector('.message-content');
    if (!contentDiv) {
        contentDiv = document.createElement('div');
        contentDiv.className = 'message-content'; // Base class, prose classes added by renderEnhancedContent if needed
        const imagesAnchor = bubbleDivToUse.querySelector('.message-images-container') || bubbleDivToUse.querySelector('.sender-name') || bubbleDivToUse.querySelector('.message-timestamp');
        bubbleDivToUse.insertBefore(contentDiv, imagesAnchor ? imagesAnchor.nextSibling : bubbleDivToUse.firstChild);
    }
    // renderEnhancedContent will clear and populate this contentDiv
    renderEnhancedContent(contentDiv, message.content || "", messageId, message.steps, message.metadata, message);


    // Footer (get or create, then populate)
    let footerDiv = bubbleDivToUse.querySelector('.message-footer');
    if (!footerDiv) {
        footerDiv = document.createElement('div');
        footerDiv.className = 'message-footer';
        bubbleDivToUse.appendChild(footerDiv); // Footer is usually last
    }
    // Footer content (details, actions, grade) is rebuilt below
    const footerContent = document.createElement('div');
    footerContent.className = 'footer-content'; // Flex container for left (details) and right (actions/grade)

    // Message Details (left side of footer)
    const detailsContainer = document.createElement('div');
    detailsContainer.className = 'message-details';
    if (message.token_count) {
        const tokenBadge = document.createElement('span');
        tokenBadge.className = 'detail-badge token-badge';
        tokenBadge.innerHTML = `<svg class="w-3 h-3 inline -mt-px" fill="currentColor" viewBox="0 0 20 20"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg> ${message.token_count}`;
        detailsContainer.appendChild(tokenBadge);
    }
    if (message.processing_time_ms) { // Assuming you might get ms from backend
        const timeBadge = document.createElement('span');
        timeBadge.className = 'detail-badge time-badge';
        timeBadge.innerHTML = `<svg class="w-3 h-3 inline -mt-px" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/></svg> ${formatProcessingTime(message.processing_time_ms)}`;
        detailsContainer.appendChild(timeBadge);
    }
    footerContent.appendChild(detailsContainer);

    // Actions and Rating Container (right side of footer)
    const actionsAndRatingContainer = document.createElement('div');
    actionsAndRatingContainer.className = 'message-actions-container'; // This is the overall right-side container

    // Action Buttons (Copy, Edit, Delete, Resend)
    if (!messageId.startsWith('temp-')) { // Don't show for temporary messages
        const actionsGroup = document.createElement('div');
        actionsGroup.className = 'message-actions'; // Group for standard buttons

        actionsGroup.appendChild(createActionButton('copy', translate('copy_content_tooltip'), () => {
            navigator.clipboard.writeText(message.content || "").then(() => showStatus(translate('status_content_copied', "Content copied!"), "success")).catch(err => showStatus(translate('status_copy_failed', "Copy failed."), "error"));
        }));
        actionsGroup.appendChild(createActionButton('edit', translate('edit_message_tooltip'), () => initiateEditMessage(messageId, message.branch_id)));
        
        if (bubbleClass === 'user-bubble') { // Resend/Branch button specific to user messages
            actionsGroup.appendChild(createActionButton('refresh', translate('resend_branch_tooltip', 'Resend/Branch'), () => initiateBranch(message.discussion_id, messageId)));
        } else if (bubbleClass === 'ai-bubble') { // Regenerate for AI messages
            actionsGroup.appendChild(createActionButton('refresh', translate('regenerate_message_tooltip'), () => regenerateMessage(messageId, message.branch_id)));
        }

        actionsGroup.appendChild(createActionButton('delete', translate('delete_message_tooltip'), () => deleteMessage(messageId, message.branch_id), 'destructive'));
        actionsAndRatingContainer.appendChild(actionsGroup);
    }

    // Rating System for AI messages
    if (showGradeControls && bubbleClass === 'ai-bubble') {
        const ratingContainer = document.createElement('div');
        ratingContainer.className = 'message-rating';
        const userGrade = message.user_grade || 0;

        const upvoteBtn = document.createElement('button');
        upvoteBtn.className = `rating-btn upvote ${userGrade > 0 ? 'active' : ''}`;
        upvoteBtn.innerHTML = `<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 3a1 1 0 01.707.293l5 5a1 1 0 01-1.414 1.414L11 6.414V16a1 1 0 11-2 0V6.414L5.707 9.707a1 1 0 01-1.414-1.414l5-5A1 1 0 0110 3z" clip-rule="evenodd" /></svg>`;
        upvoteBtn.title = translate('grade_good_tooltip');
        upvoteBtn.onclick = () => gradeMessage(messageId, 1, message.branch_id);

        const gradeDisplay = document.createElement('span');
        gradeDisplay.className = 'rating-score'; gradeDisplay.textContent = userGrade;

        const downvoteBtn = document.createElement('button');
        downvoteBtn.className = `rating-btn downvote ${userGrade < 0 ? 'active' : ''}`;
        downvoteBtn.innerHTML = `<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 17a1 1 0 01-.707-.293l-5-5a1 1 0 011.414-1.414L9 13.586V4a1 1 0 112 0v9.586l3.293-3.293a1 1 0 011.414 1.414l-5 5A1 1 0 0110 17z" clip-rule="evenodd" /></svg>`;
        downvoteBtn.title = translate('grade_bad_tooltip');
        downvoteBtn.onclick = () => gradeMessage(messageId, -1, message.branch_id);

        ratingContainer.appendChild(upvoteBtn); ratingContainer.appendChild(gradeDisplay); ratingContainer.appendChild(downvoteBtn);
        actionsAndRatingContainer.appendChild(ratingContainer);
    }
    footerContent.appendChild(actionsAndRatingContainer);
    footerDiv.appendChild(footerContent);


    // Final check for streaming AI message DOM caching
    if (messageId === currentAiMessageId && (aiMessageStreaming || generationInProgress)) {
        currentAiMessageDomContainer = messageContainerToUse;
        currentAiMessageDomBubble = bubbleDivToUse;
    }
}

// `renderEnhancedContent` (with <think> block fix)
function renderEnhancedContent(contentDivElement, rawContent, messageId, steps = [], metadata = [], messageObject = {}) {
    contentDivElement.innerHTML = ''; // Start fresh

    let currentSegment = rawContent || "";
    const thinkBlockRegex = /<think>([\s\S]*?)<\/think>/gs;
    let lastIndex = 0;
    let match;
    let hasRenderedTextContent = false;

    while ((match = thinkBlockRegex.exec(currentSegment)) !== null) {
        const textBefore = currentSegment.substring(lastIndex, match.index);
        if (textBefore.trim()) {
            const regularContentSegmentDiv = document.createElement('div');
            regularContentSegmentDiv.innerHTML = marked.parse(textBefore); // Use a Markdown parser
            contentDivElement.appendChild(regularContentSegmentDiv);
            hasRenderedTextContent = true;
        }

        const thinkDetails = document.createElement('details');
        thinkDetails.className = 'think-block my-2';
        const thinkSummary = document.createElement('summary');
        thinkSummary.className = 'px-2 py-1 text-xs italic text-gray-500 dark:text-gray-400 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-750 rounded focus:outline-none focus:ring-2 focus:ring-blue-500';
        thinkSummary.textContent = translate('assistant_thoughts_summary', "Assistant's Thoughts");
        const thinkContentDiv = document.createElement('div');
        thinkContentDiv.className = 'think-content p-2 border-t border-gray-200 dark:border-gray-700 prose prose-sm max-w-none dark:prose-invert';
        thinkContentDiv.innerHTML = marked.parse(match[1].trim()); // Parse think content as Markdown
        
        thinkDetails.appendChild(thinkSummary);
        thinkDetails.appendChild(thinkContentDiv);
        contentDivElement.appendChild(thinkDetails);
        hasRenderedTextContent = true; // A think block counts as content
        lastIndex = thinkBlockRegex.lastIndex;
    }

    const remainingText = currentSegment.substring(lastIndex);
    if (remainingText.trim()) {
        const finalContentSegmentDiv = document.createElement('div');
        finalContentSegmentDiv.innerHTML = marked.parse(remainingText); // Parse remaining as Markdown
        contentDivElement.appendChild(finalContentSegmentDiv);
        hasRenderedTextContent = true;
    }
    
    // Apply prose styling to the main content if it doesn't have specific sub-containers that handle it
    if (hasRenderedTextContent && !contentDivElement.classList.contains('prose')) {
         // Check if children are already prose, if not, wrap text nodes or apply to contentDivElement
        let applyProseToBase = true;
        contentDivElement.childNodes.forEach(node => {
            if (node.nodeType === Node.ELEMENT_NODE && (node.classList.contains('prose') || node.classList.contains('think-block') || node.classList.contains('steps-container') || node.classList.contains('message-metadata'))) {
                applyProseToBase = false;
            }
        });
        if(applyProseToBase) {
            contentDivElement.classList.add('prose', 'prose-sm', 'max-w-none', 'dark:prose-invert');
            // Ensure code block theming for prose is applied
            contentDivElement.classList.add('prose-code:before:content-none', 'prose-code:after:content-none', 'prose-code:font-normal', 'prose-code:bg-gray-200', 'dark:prose-code:bg-gray-700', 'prose-code:text-gray-800', 'dark:prose-code:text-gray-100', 'prose-code:px-1', 'prose-code:py-0.5', 'prose-code:rounded');
        }
    }


    if (steps && steps.length > 0) renderSteps(contentDivElement, steps); // From your enhanced rendering
    if (metadata && metadata.length > 0) renderMetadata(contentDivElement, metadata); // From your enhanced rendering

    // Typing Indicator or Empty Placeholder
    const isStreamingThisMessage = aiMessageStreaming && messageId === currentAiMessageId;
    const isEffectivelyEmpty = !hasRenderedTextContent && (!steps || steps.length === 0) && (!metadata || metadata.length === 0);

    if (isStreamingThisMessage && currentAiMessageContentAccumulator === "" && isEffectivelyEmpty) {
        if (!contentDivElement.querySelector('.typing-indicator')) {
            const typingIndicatorDiv = document.createElement('div');
            typingIndicatorDiv.className = 'typing-indicator flex items-center space-x-1 h-5 my-1';
            for (let i = 0; i < 3; i++) { typingIndicatorDiv.appendChild(document.createElement('span')); }
            contentDivElement.appendChild(typingIndicatorDiv);
        }
    } else if (isEffectivelyEmpty &&
        (!messageObject.image_references || messageObject.image_references.length === 0) &&
        !isStreamingThisMessage) {
        contentDivElement.innerHTML = `<p class="empty-message">${translate('empty_message_placeholder')}</p>`;
    }

    // KaTeX and Custom Code Blocks
    if (typeof renderMathInElement === 'function') { // Check if KaTeX utility is available
        try {
            renderMathInElement(contentDivElement, { delimiters: [{ left: '$$', right: '$$', display: true }, { left: '$', right: '$', display: false }, { left: '\\(', right: '\\)', display: false }, { left: '\\[', right: '\\]', display: true }], throwOnError: false });
        } catch (e) { console.warn("KaTeX rendering error:", e); }
    } else if (typeof MathJax !== 'undefined') { // Fallback for MathJax if pre-loaded
         MathJax.typesetPromise([contentDivElement]).catch(err => console.warn('MathJax error:', err));
    }

    renderCustomCodeBlocks(contentDivElement, messageId); // Your syntax highlighting and copy button logic
    applySyntaxHighlighting(contentDivElement); // Apply basic or PrismJS highlighting
    addCodeBlockCopyButtons(contentDivElement); // Add copy buttons to all code blocks now
}


function renderMessages(messagesToRender) { /* Your "Enhanced renderMessages" from problem desc, with date grouping */
    if(!chatMessages) return;
    chatMessages.innerHTML = '';

    if (messagesToRender.length === 0 && currentDiscussionId) {
        const emptyState = document.createElement('div');
        emptyState.className = 'chat-empty-state';
        emptyState.innerHTML = `
            <div class="empty-state-content">
                <svg class="empty-state-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
                <h3 class="empty-state-title">${translate('chat_area_no_messages_yet', 'No messages yet')}</h3>
                <p class="empty-state-description">${translate('chat_area_start_conversation', 'Start a conversation by typing a message below.')}</p>
            </div>
        `;
        chatMessages.appendChild(emptyState);
        return;
    }

    const messagesByDate = groupMessagesByDate(messagesToRender);

    Object.entries(messagesByDate).forEach(([date, messagesOnDate]) => {
        if (Object.keys(messagesByDate).length > 1 || (Object.keys(messagesByDate).length === 1 && new Date(date).toDateString() !== new Date().toDateString())) { // Show for single day if not today
            const dateSeparator = document.createElement('div');
            dateSeparator.className = 'date-separator';
            dateSeparator.innerHTML = `
                <div class="date-separator-line"></div>
                <div class="date-separator-text">${formatDateSeparator(new Date(date))}</div>
                <div class="date-separator-line"></div>
            `;
            chatMessages.appendChild(dateSeparator);
        }
        messagesOnDate.forEach((msg, index) => {
            msg.addSpacing = (index > 0 && messagesOnDate[index - 1].sender !== msg.sender);
            renderMessage(msg);
        });
    });
    requestAnimationFrame(() => { scrollChatToBottom(false); }); // Scroll immediately after render
}
// groupMessagesByDate, formatDateSeparator, formatProcessingTime as in your enhanced version
// getSenderAvatar, createActionButton, addCodeBlockCopyButtons, renderSteps, renderMetadata, escapeHtml also as in your enhanced version.

// Helper functions
function createActionButton(type, tooltip, onClick, variant = 'default') {
    const button = document.createElement('button');
    button.className = `action-btn action-btn-${type} ${variant === 'destructive' ? 'destructive' : ''}`;
    button.title = tooltip;
    button.onclick = onClick;

    const icons = {
        copy: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>`,
        edit: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>`,
        delete: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>`,
        refresh: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>`
    };

    button.innerHTML = icons[type] || '';
    return button;
}

function groupMessagesByDate(messages) {
    const groups = {};
    
    messages.forEach(message => {
        const date = new Date(message.timestamp || message.created_at || Date.now());
        const dateKey = date.toDateString();
        
        if (!groups[dateKey]) {
            groups[dateKey] = [];
        }
        groups[dateKey].push(message);
    });
    
    return groups;
}
function formatDateSeparator(date) {
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    if (date.toDateString() === today.toDateString()) {
        return 'Today';
    } else if (date.toDateString() === yesterday.toDateString()) {
        return 'Yesterday';
    } else {
        return date.toLocaleDateString(undefined, { 
            weekday: 'long', 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
        });
    }
} 
function getSenderAvatar(senderName) {
    // Generate a simple avatar based on sender name
    const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8'];
    const colorIndex = senderName.length % colors.length;
    const initial = senderName.charAt(0).toUpperCase();
    
    return `<div class="sender-avatar" style="background-color: ${colors[colorIndex]}">${initial}</div>`;
}

// Helper functions
function createActionButton(type, tooltip, onClick, variant = 'default') {
    const button = document.createElement('button');
    button.className = `action-btn action-btn-${type} ${variant === 'destructive' ? 'destructive' : ''}`;
    button.title = tooltip;
    button.onclick = onClick;

    const icons = {
        copy: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>`,
        edit: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>`,
        delete: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>`,
        refresh: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>`
    };

    button.innerHTML = icons[type] || '';
    return button;
}

function formatProcessingTime(ms) {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
}


function addCodeBlockCopyButtons(container) {
    const copyButtons = container.querySelectorAll('.code-copy-btn');
    
    copyButtons.forEach(button => {
        button.addEventListener('click', async (e) => {
            e.preventDefault();
            const code = button.getAttribute('data-code');
            
            try {
                await navigator.clipboard.writeText(code);
                
                // Visual feedback
                const originalText = button.innerHTML;
                button.innerHTML = `<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg> Copied!`;
                button.classList.add('copied');
                
                setTimeout(() => {
                    button.innerHTML = originalText;
                    button.classList.remove('copied');
                }, 2000);
                
            } catch (err) {
                console.error('Failed to copy code:', err);
                showStatus('Failed to copy code', 'error');
            }
        });
    });
}

function renderSteps(container, steps) {
    if (!steps || steps.length === 0) return;

    const stepsContainer = document.createElement('div');
    stepsContainer.className = 'message-steps';
    
    const stepsHeader = document.createElement('div');
    stepsHeader.className = 'steps-header';
    stepsHeader.innerHTML = `
        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clip-rule="evenodd"/>
        </svg>
        Processing Steps
    `;
    stepsContainer.appendChild(stepsHeader);

    const stepsList = document.createElement('div');
    stepsList.className = 'steps-list';

    steps.forEach((step, index) => {
        const stepItem = document.createElement('div');
        stepItem.className = `step-item ${step.status || 'completed'}`;
        
        stepItem.innerHTML = `
            <div class="step-indicator">
                <span class="step-number">${index + 1}</span>
            </div>
            <div class="step-content">
                <div class="step-title">${step.title || `Step ${index + 1}`}</div>
                ${step.description ? `<div class="step-description">${step.description}</div>` : ''}
                ${step.duration ? `<div class="step-duration">${formatProcessingTime(step.duration)}</div>` : ''}
            </div>
        `;
        
        stepsList.appendChild(stepItem);
    });

    stepsContainer.appendChild(stepsList);
    container.appendChild(stepsContainer);
}

function renderMetadata(container, metadata) {
    if (!metadata || metadata.length === 0) return;

    const metadataContainer = document.createElement('div');
    metadataContainer.className = 'message-metadata';
    
    const metadataHeader = document.createElement('div');
    metadataHeader.className = 'metadata-header';
    metadataHeader.innerHTML = `
        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/>
        </svg>
        Additional Information
    `;
    metadataContainer.appendChild(metadataHeader);

    const metadataList = document.createElement('div');
    metadataList.className = 'metadata-list';

    metadata.forEach(item => {
        const metadataItem = document.createElement('div');
        metadataItem.className = 'metadata-item';
        
        metadataItem.innerHTML = `
            <div class="metadata-key">${item.key}</div>
            <div class="metadata-value">${item.value}</div>
        `;
        
        metadataList.appendChild(metadataItem);
    });

    metadataContainer.appendChild(metadataList);
    container.appendChild(metadataContainer);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getSenderNameText(){
    return "lollms"
}

async function gradeMessage(messageId, change, branchId) { // Added branchId
    if (!currentDiscussionId || !messageId || messageId.startsWith('temp-') || !branchId) return;
    const messageBubble = document.getElementById(`message-${messageId}`);
    if (!messageBubble) return;

    let apiUrl = `/api/discussions/${currentDiscussionId}/messages/${messageId}/grade`;
    if (backendCapabilities.supportsBranches) {
        apiUrl += `?branch_id=${encodeURIComponent(branchId)}`;
    }

    try {
        const response = await apiRequest(apiUrl, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ change: change })
        });
        const updatedMessage = await response.json(); // This is MessageOutput

        const gradeSpan = messageBubble.querySelector('.rating-score'); // Assuming class 'rating-score' from enhanced
        const upBtn = messageBubble.querySelector('.rating-btn.upvote');
        const downBtn = messageBubble.querySelector('.rating-btn.downvote');

        if (gradeSpan) gradeSpan.textContent = updatedMessage.user_grade;
        if (upBtn) upBtn.classList.toggle('active', updatedMessage.user_grade > 0);
        if (downBtn) downBtn.classList.toggle('active', updatedMessage.user_grade < 0);

        const disc = discussions[currentDiscussionId];
        if (disc && disc.branches[branchId]) {
            const msgIndex = disc.branches[branchId].findIndex(m => m.id === messageId);
            if (msgIndex > -1) disc.branches[branchId][msgIndex].user_grade = updatedMessage.user_grade;
        }
    } catch (error) { showStatus(translate('status_grade_update_failed'), 'error'); }
}

// --- Message Edit/Delete ---
function initiateEditMessage(messageId, branchId) {
    if (!currentDiscussionId || !discussions[currentDiscussionId] || !branchId) return;
    const branchMessages = discussions[currentDiscussionId].branches[branchId];
    if (!branchMessages) return;

    const messageData = branchMessages.find(m => m.id === messageId);
    if (!messageData) { showStatus(translate('status_cannot_find_message_to_edit'), "error"); return; }

    if(editMessageIdInput) editMessageIdInput.value = messageId;
    if(editMessageBranchIdInput) editMessageBranchIdInput.value = branchId; // Store branchId
    if(editMessageInput) editMessageInput.value = messageData.content;
    showStatus('', 'info', editMessageStatus);
    openModal('editMessageModal');
}

async function confirmMessageEdit() {
    const messageId = editMessageIdInput ? editMessageIdInput.value : null;
    const branchId = editMessageBranchIdInput ? editMessageBranchIdInput.value : null; // Get branchId
    const newContent = editMessageInput ? editMessageInput.value : null;

    if (!messageId || !branchId || !currentDiscussionId || newContent === null) return;
    showStatus(translate('status_saving_changes', 'Saving changes...'), 'info', editMessageStatus);
    if(confirmEditMessageBtn) confirmEditMessageBtn.disabled = true;

    let apiUrl = `/api/discussions/${currentDiscussionId}/messages/${messageId}`;
    if (backendCapabilities.supportsBranches) {
        apiUrl += `?branch_id=${encodeURIComponent(branchId)}`;
    }

    try {
        const response = await apiRequest(apiUrl, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: newContent }),
            statusElement: editMessageStatus
        });
        const updatedMessageData = await response.json(); // This is MessageOutput

        const disc = discussions[currentDiscussionId];
        if (disc && disc.branches[branchId]) {
            const msgIndex = disc.branches[branchId].findIndex(m => m.id === messageId);
            if (msgIndex > -1) {
                // Preserve client-side only fields if backend doesn't return everything
                const originalMsg = disc.branches[branchId][msgIndex];
                disc.branches[branchId][msgIndex] = {
                    ...originalMsg, // Keep original fields like addSpacing
                    ...updatedMessageData, // Overlay with backend response
                    steps: updatedMessageData.steps || originalMsg.steps || [], // Merge steps/meta carefully
                    metadata: updatedMessageData.metadata || originalMsg.metadata || [],
                    branch_id: branchId // Ensure branch_id is correct
                };
            }
        }

        // Re-render only the affected message for efficiency
        const messageContainer = document.querySelector(`.message-container[data-message-id="${messageId}"]`);
        const messageBubble = document.getElementById(`message-${messageId}`);
        if (messageContainer && messageBubble && disc.branches[branchId]) {
            const msgToRender = disc.branches[branchId].find(m => m.id === messageId);
            if (msgToRender) {
                 msgToRender.addSpacing = messageContainer.classList.contains('mt-4'); // Preserve spacing
                 renderMessage(msgToRender, messageContainer, messageBubble);
            }
        } else { // Fallback to full re-render if specific elements not found
            renderMessages(currentMessages);
        }


        if (disc && updatedMessageData.created_at) { // Backend should return updated timestamp
            disc.last_activity_at = updatedMessageData.created_at;
            renderDiscussionList();
        }
        showStatus(translate('status_message_updated_success', 'Message updated successfully.'), 'success', editMessageStatus);
        setTimeout(() => closeModal('editMessageModal'), 1000);
    } catch (error) { /* apiRequest handles status */
    } finally {
        if(confirmEditMessageBtn) confirmEditMessageBtn.disabled = false;
    }
}

async function deleteMessage(messageId, branchId) {
    if (!currentDiscussionId || !messageId || messageId.startsWith('temp-') || !branchId) return;

    const disc = discussions[currentDiscussionId];
    if (!disc || !disc.branches[branchId]) return;
    const messageData = disc.branches[branchId].find(m => m.id === messageId);
    if (!messageData) return;

    const msgPreview = (messageData.content || translate('image_message_placeholder', 'Image message')).substring(0, 50) + '...';
    if (confirm(translate('confirm_delete_message', `Are you sure you want to delete this message?\n\n"${msgPreview}"`, { preview: msgPreview }))) {
        showStatus(translate('status_deleting_message', 'Deleting message...'), 'info');

        let apiUrl = `/api/discussions/${currentDiscussionId}/messages/${messageId}`;
        if (backendCapabilities.supportsBranches) {
            apiUrl += `?branch_id=${encodeURIComponent(branchId)}`;
        }

        try {
            await apiRequest(apiUrl, { method: 'DELETE' });
            disc.branches[branchId] = disc.branches[branchId].filter(m => m.id !== messageId);
            // If active branch becomes empty (and not 'main'), consider switching or special UI
            if (disc.branches[branchId].length === 0 && branchId !== 'main') {
                // Optional: delete branch from client & backend if empty
                // For now, just leave it empty. Client can navigate away.
                // delete disc.branches[branchId];
                // if (disc.activeBranchId === branchId) switchBranch(currentDiscussionId, 'main');
            }
            currentMessages = disc.branches[activeBranchId] || []; // Refresh currentMessages pointer
            renderMessages(currentMessages); // Re-render messages for the active branch
            renderBranchTabsUI(currentDiscussionId); // Update tabs (branch might be gone or empty)

            showStatus(translate('status_message_deleted_success', 'Message deleted successfully.'), 'success');
            await refreshMessagesAfterStream(); // Get definitive state, especially if active branch changed
        } catch (error) { /* apiRequest handles status */ }
    }
}

async function regenerateMessage(messageId, branchId) {
    if (!currentDiscussionId || !branchId || generationInProgress) return;

    const disc = discussions[currentDiscussionId];
    if (!disc || !disc.branches[branchId]) return;

    const aiMessageIndex = disc.branches[branchId].findIndex(msg => msg.id === messageId);
    if (aiMessageIndex === -1 || aiMessageIndex === 0) { // Cannot regenerate first message or non-AI
        showStatus(translate('status_cannot_regenerate_message', "Cannot regenerate this message."), "warning");
        return;
    }

    const aiMessageToRegenerate = disc.branches[branchId][aiMessageIndex];
    const userPromptMessage = disc.branches[branchId][aiMessageIndex - 1];

    if (!userPromptMessage || userPromptMessage.sender.toLowerCase() === (currentUser.lollms_client_ai_name || 'assistant').toLowerCase()) {
        showStatus(translate('status_cannot_regenerate_no_user_prompt', "Cannot regenerate without a preceding user prompt."), "warning");
        return;
    }

    showStatus(translate('status_regenerating_response', "Regenerating response..."), "info");

    // Remove the AI message and any subsequent messages in this branch
    disc.branches[branchId] = disc.branches[branchId].slice(0, aiMessageIndex);
    currentMessages = disc.branches[branchId]; // Update currentMessages
    renderMessages(currentMessages); // Re-render to remove messages

    // Prepare data for resending the user prompt
    const resendPayload = {
        prompt: userPromptMessage.content,
        image_server_paths: userPromptMessage.server_image_paths || userPromptMessage.image_references || [] // Use server_paths if available
    };

    // Call sendMessage, effectively resending the user's prompt in the same branch
    // The `is_resend` and `branch_from_message_id` are not strictly needed here as we are
    // continuing the *same* branch, not creating a new one from this action.
    // The key is that sendMessage will use the current `activeBranchId` (which is `branchId`).
    await sendMessage(null, resendPayload); // branchFromUserMessageId is null, resendData has the payload
}


// --- Pyodide, Settings, Data Store, File Management, RAG Toggle (largely as provided, ensure IDs and branch awareness where needed) ---
// ... (Keep your existing functions, ensure they don't conflict with new message rendering or state) ...
// Example: `updateRagToggleButtonState` should consider `discussions[currentDiscussionId]?.rag_datastore_id`
// `ragDataStoreSelect.onchange` should call `updateDiscussionRagStoreOnBackend`
async function updateDiscussionRagStoreOnBackend(discussionId, ragDatastoreId) {
    if (!discussionId) return;
    try {
        await apiRequest(`/api/discussions/${discussionId}/rag_datastore`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rag_datastore_id: ragDatastoreId })
        });
        const dsName = ragDatastoreId ? (availableDataStoresForRag.find(ds => ds.id === ragDatastoreId)?.name || 'Unknown Store') : translate('none_text');
        showStatus(translate('status_rag_datastore_set', `RAG datastore for this discussion set to: ${dsName}.`, {name: dsName}), 'success');
    } catch (error) {
        showStatus(translate('status_rag_datastore_set_failed'), 'error');
        // Revert client-side change if backend update fails
        if (discussions[discussionId]) {
            // This is tricky, you'd need to know the *previous* value.
            // For now, let's assume the user might have to manually fix it or retry.
        }
    }
}

// --- Branching Logic ---
async function initiateBranch(discussionId, userMessageIdToBranchFrom) {
    if (!discussionId || !userMessageIdToBranchFrom || generationInProgress) return;
    const disc = discussions[discussionId];
    if (!disc || !disc.branches || !disc.branches[activeBranchId]) { // Branch from current active branch
        console.error("initiateBranch: Discussion or current active branch not found."); return;
    }

    const sourceBranchMessages = disc.branches[activeBranchId];
    const userMessageIndex = sourceBranchMessages.findIndex(msg => msg.id === userMessageIdToBranchFrom);

    if (userMessageIndex === -1) {
        console.error("initiateBranch: User message to branch from not found in active branch."); return;
    }
    const userMessageToResend = sourceBranchMessages[userMessageIndex];
     if (!userMessageToResend || (userMessageToResend.sender !== currentUser.username && userMessageToResend.sender !== "User" && userMessageToResend.sender !== translate('sender_you', 'You'))) { // Simple check
        showStatus(translate('status_can_only_branch_from_user_prompts', "Can only branch from your own prompts."), "warning"); return;
    }

    const newBranchId = `branch-${Date.now()}`;
    showStatus(translate('status_creating_branch', `Creating new branch "${newBranchId}"...`, { branch_id: newBranchId }), 'info');

    // Create new branch with messages up to and including the user message
    disc.branches[newBranchId] = sourceBranchMessages.slice(0, userMessageIndex + 1).map(msg => ({
        ...msg,
        branch_id: newBranchId // Ensure all messages in the new branch have the new branch_id
    }));

    // If backend supports branches, tell it to switch. Otherwise, it's client-side only.
    if (backendCapabilities.supportsBranches) {
        try {
            await apiRequest(`/api/discussions/${discussionId}/active_branch`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ active_branch_id: newBranchId })
            });
            disc.activeBranchId = newBranchId;
        } catch (error) {
            showStatus(translate('status_failed_to_set_active_branch_backend', "Failed to set active branch on server. Branching client-side only."), "warning");
            // Proceed with client-side branching even if backend fails to set active
            disc.activeBranchId = newBranchId; // Still set locally
        }
    } else {
        disc.activeBranchId = newBranchId; // Client-side switch
    }
    activeBranchId = newBranchId; // Update global
    currentMessages = disc.branches[newBranchId];

    renderMessages(currentMessages);
    renderBranchTabsUI(discussionId);

    const resendPayload = {
        prompt: userMessageToResend.content,
        image_server_paths: userMessageToResend.server_image_paths || userMessageToResend.image_references || [] // Prefer server_image_paths
    };
    // Call sendMessage, it will use the new `activeBranchId`
    await sendMessage(userMessageIdToBranchFrom, resendPayload);
}

function renderBranchTabsUI(discussionId) {
    const disc = discussions[discussionId];
    let tabsContainer = document.getElementById('branchTabsContainer');

    if (!disc || !disc.branches || Object.keys(disc.branches).length <= 1) {
        if (tabsContainer) tabsContainer.innerHTML = ''; // Clear if only main or no branches
        return;
    }

    if (!tabsContainer && chatHeader) { // Create if doesn't exist, place in chat header
        tabsContainer = document.createElement('div');
        tabsContainer.id = 'branchTabsContainer';
        // Style appropriately, e.g., below discussion title
        tabsContainer.className = 'flex flex-wrap gap-2 p-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800';
        chatHeader.appendChild(tabsContainer); // Append to chat header
    } else if (!tabsContainer) { // Fallback if chatHeader not found
        console.warn("Branch tabs container or chat header not found. Tabs UI will not be rendered.");
        return;
    }
    tabsContainer.innerHTML = ''; // Clear existing tabs

    const branchIds = Object.keys(disc.branches).sort((a, b) => {
        if (a === 'main') return -1; if (b === 'main') return 1;
        // Sort by part after "branch-" if it's a timestamp, otherwise localeCompare
        const aTime = a.startsWith('branch-') ? parseInt(a.substring(7), 10) : 0;
        const bTime = b.startsWith('branch-') ? parseInt(b.substring(7), 10) : 0;
        if (aTime && bTime) return aTime - bTime;
        return a.localeCompare(b);
    });

    branchIds.forEach(branchId => {
        const tabButton = document.createElement('button');
        const idSuffix = branchId.startsWith('branch-') ? branchId.substring(branchId.lastIndexOf('-') + 1).substring(0, 5) : branchId;
        tabButton.textContent = branchId === 'main' ? translate('branch_tab_main', 'Main') : translate('branch_tab_branch_prefix', `Branch ${idSuffix}`, { id_short: idSuffix });
        tabButton.className = `px-3 py-1 text-xs rounded-full transition-colors whitespace-nowrap ${branchId === disc.activeBranchId
            ? 'bg-blue-500 text-white font-semibold'
            : 'bg-gray-200 text-gray-700 hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'}`;
        tabButton.onclick = () => switchBranch(discussionId, branchId);
        tabsContainer.appendChild(tabButton);
    });
}

async function switchBranch(discussionId, newBranchId) {
    const disc = discussions[discussionId];
    if (!disc || !disc.branches || !disc.branches[newBranchId] || disc.activeBranchId === newBranchId || generationInProgress) {
        return;
    }

    showStatus(translate('status_switching_branch', `Switching to branch: ${newBranchId}...`, { branch_id: newBranchId }), 'info');

    if (backendCapabilities.supportsBranches) {
        try {
            await apiRequest(`/api/discussions/${discussionId}/active_branch`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ active_branch_id: newBranchId })
            });
            disc.activeBranchId = newBranchId;
        } catch (error) {
            showStatus(translate('status_failed_to_set_active_branch_backend_switched_client', "Failed to set active branch on server. Switched client-side."), "warning");
            disc.activeBranchId = newBranchId; // Still switch client-side
        }
    } else {
        disc.activeBranchId = newBranchId; // Client-side only switch
    }
    activeBranchId = newBranchId;
    currentMessages = disc.branches[newBranchId] || []; // Fallback to empty if branch somehow missing

    // Check if messages for this branch are loaded
    if (!disc.messages_loaded_fully || !disc.messages_loaded_fully[newBranchId]) {
        await selectDiscussion(discussionId); // This will re-trigger message loading for the new active branch
    } else {
        renderMessages(currentMessages); // Messages already loaded, just render
    }
    renderBranchTabsUI(discussionId);
    scrollChatToBottom(false);
}

// --- Utilities (scrollChatToBottom, showStatus, populateDropdown - largely as provided) ---
// Ensure showStatus clears its own timer if called again.
function scrollChatToBottom(smooth = true) {
    if (chatMessages) {
        if (smooth) {
            chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: 'smooth' });
        } else {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }
}

function showStatus(msg, type = 'info', statusElement = statusMessage) {
    const targetElement = statusElement || statusMessage;
    if (targetElement) {
        // Clear previous timer if exists on this element
        if (targetElement.timer) clearTimeout(targetElement.timer);

        targetElement.textContent = msg;
        let typeClass = 'text-gray-500 dark:text-gray-400'; // Default info
        if (type === 'error') typeClass = 'text-red-500 dark:text-red-400';
        else if (type === 'success') typeClass = 'text-green-500 dark:text-green-400';
        else if (type === 'warning') typeClass = 'text-yellow-500 dark:text-yellow-400';

        // Remove old color classes before adding new one
        targetElement.className = targetElement.className.replace(/text-(gray|red|green|yellow)-[0-9]{3}/g, '').replace(/dark:text-(gray|red|green|yellow)-[0-9]{3}/g, '');
        targetElement.classList.add(...typeClass.split(' '));


        if (targetElement === statusMessage && msg) { // Auto-clear for global status message
            targetElement.timer = setTimeout(() => {
                if (targetElement.textContent === msg) { // Only clear if it's the same message
                    targetElement.textContent = '';
                    targetElement.className = targetElement.className.replace(/text-(gray|red|green|yellow)-[0-9]{3}/g, '').replace(/dark:text-(gray|red|green|yellow)-[0-9]{3}/g, '');
                }
            }, 5000);
        }
    }
}
// populateDropdown, and other utilities from your original code are assumed to be here.


// --- Data Store Management --- 
dataStoresBtn.onclick = () => openModal('dataStoresModal');

async function loadDataStores() { 
    try {
        const response = await apiRequest('/api/datastores');
        const allStores = await response.json();
        ownedDataStores = allStores.filter(ds => ds.owner_username === currentUser.username);
        sharedDataStores = allStores.filter(ds => ds.owner_username !== currentUser.username);
        
        availableDataStoresForRag = [...ownedDataStores, ...sharedDataStores].sort((a,b) => a.name.localeCompare(b.name));
        
        populateDataStoresModal(); 
        populateRagDataStoreSelect(); 
    } catch (error) {
        if(ownedDataStoresList) ownedDataStoresList.innerHTML = `<p class="text-red-500 italic">${translate('datastores_error_loading')}</p>`;
        if(sharedDataStoresList) sharedDataStoresList.innerHTML = `<p class="text-red-500 italic">${translate('datastores_error_loading')}</p>`;
    }
}

function populateRagDataStoreSelect() {
    ragDataStoreSelect.innerHTML = `<option value="">${translate('rag_select_default_option')}</option>`;
    availableDataStoresForRag.forEach(ds => {
        const option = document.createElement('option');
        option.value = ds.id;
        option.textContent = `${ds.name} (${ds.owner_username === currentUser.username ? translate('datastores_owned_by_you_suffix') : translate('datastores_shared_by_suffix', `Shared by ${ds.owner_username}`, {owner: ds.owner_username})})`;
        ragDataStoreSelect.appendChild(option);
    });
    if (currentDiscussionId && discussions[currentDiscussionId] && discussions[currentDiscussionId].rag_datastore_id) {
        ragDataStoreSelect.value = discussions[currentDiscussionId].rag_datastore_id;
    }
}

ragDataStoreSelect.onchange = async () => {
    if (!currentDiscussionId) return;
    const selectedDataStoreId = ragDataStoreSelect.value || null; 
    try {
        await apiRequest(`/api/discussions/${currentDiscussionId}/rag_datastore`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rag_datastore_id: selectedDataStoreId })
        });
        discussions[currentDiscussionId].rag_datastore_id = selectedDataStoreId;
        const dsName = selectedDataStoreId ? availableDataStoresForRag.find(ds=>ds.id===selectedDataStoreId)?.name : translate('none_text');
        showStatus(translate('status_rag_datastore_set', `RAG datastore for this discussion set to: ${dsName}.`, {name: dsName}), 'success');
        updateRagToggleButtonState(); 
    } catch (error) {
        showStatus(translate('status_rag_datastore_set_failed'), 'error');
        ragDataStoreSelect.value = discussions[currentDiscussionId].rag_datastore_id || "";
    }
};

function populateDataStoresModal() {
    ownedDataStoresList.innerHTML = '';
    if (ownedDataStores.length === 0) {
        ownedDataStoresList.innerHTML = `<p class="text-gray-500 italic">${translate('datastores_no_owned_stores')}</p>`;
    } else {
        ownedDataStores.forEach(ds => {
            const div = document.createElement('div');
            div.className = 'flex justify-between items-center py-1.5 px-2 hover:bg-gray-700 rounded text-sm';
            div.innerHTML = `
                <div class="flex-1">
                    <strong class="text-gray-100">${ds.name}</strong>
                    <p class="text-xs text-gray-400 truncate">${ds.description || translate('datastores_no_description')}</p>
                </div>
                <div class="space-x-1">
                    <button title="${translate('manage_files_tooltip')}" onclick="openFileManagerForStore('${ds.id}', '${ds.name}')" class="p-1.5 hover:bg-blue-700 rounded-full"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4 text-blue-400"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 9.776c.112-.017.227-.026.344-.026h15.812c.117 0 .232.009.344.026m-16.5 0a2.25 2.25 0 0 0-1.883 2.542l.857 6a2.25 2.25 0 0 0 2.227 1.932H19.05a2.25 2.25 0 0 0 2.227-1.932l.857-6a2.25 2.25 0 0 0-1.883-2.542m-16.5 0V6A2.25 2.25 0 0 1 6 3.75h3.879a1.5 1.5 0 0 1 1.06.44l2.122 2.12a1.5 1.5 0 0 0 1.06.44H18A2.25 2.25 0 0 1 20.25 9v.776" /></svg></button>
                    <button title="${translate('share_datastore_tooltip')}" onclick="initiateShareDataStore('${ds.id}', '${ds.name}')" class="p-1.5 hover:bg-green-700 rounded-full"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4 text-green-400"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7.5v3m0 0v3m0-3h3m-3 0h-3m-2.25-4.125a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0ZM3 19.235v-.11a6.375 6.375 0 0 1 12.75 0v.109A12.318 12.318 0 0 1 9.374 21c-2.331 0-4.512-.645-6.374-1.766Z" /></svg></button>
                    <button title="${translate('rename_edit_datastore_tooltip')}" onclick="initiateEditDataStore('${ds.id}', '${ds.name}', '${ds.description || ''}')" class="p-1.5 hover:bg-yellow-700 rounded-full"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4 text-yellow-400"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125" /></svg></button>
                    <button title="${translate('delete_datastore_tooltip')}" onclick="deleteDataStore('${ds.id}', '${ds.name}')" class="p-1.5 hover:bg-red-700 rounded-full"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4 text-red-400"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12.508 0A48.067 48.067 0 0 1 7.8 5.397m7.454 0M12 10.75h.008v.008H12v-.008Z" /></svg></button>
                </div>
            `;
            ownedDataStoresList.appendChild(div);
        });
    }
    sharedDataStoresList.innerHTML = '';
    if (sharedDataStores.length === 0) {
        sharedDataStoresList.innerHTML = `<p class="text-gray-500 italic">${translate('datastores_no_shared_stores')}</p>`;
    } else {
            sharedDataStores.forEach(ds => {
            const div = document.createElement('div');
            div.className = 'flex justify-between items-center py-1.5 px-2 text-sm'; 
            div.innerHTML = `
                <div class="flex-1">
                    <strong class="text-gray-100">${ds.name}</strong> (${translate('datastores_owned_by_prefix')}: ${ds.owner_username})
                    <p class="text-xs text-gray-400 truncate">${ds.description || translate('datastores_no_description')}</p>
                </div>
                <button title="${translate('use_for_rag_tooltip')}" onclick="setDiscussionRagStore('${ds.id}')" class="p-1.5 text-xs bg-blue-700 text-blue-100 rounded-md hover:bg-blue-600" data-translate-key="use_for_rag_btn">Use for RAG</button>
            `;
            sharedDataStoresList.appendChild(div);
        });
    }
}

async function handleCreateDataStore(event) {
    event.preventDefault();
    const name = newDataStoreNameInput.value.trim();
    const description = newDataStoreDescriptionInput.value.trim();
    if (!name) { showStatus(translate('datastores_name_required_error'), "error", createDataStoreStatus); return; }
    showStatus(translate('status_creating_datastore', "Creating data store..."), "info", createDataStoreStatus);
    try {
        await apiRequest('/api/datastores', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description }),
            statusElement: createDataStoreStatus
        });
        showStatus(translate('status_datastore_created_success', `Data Store "${name}" created.`, {name: name}), "success", createDataStoreStatus);
        createDataStoreForm.reset();
        await loadDataStores(); 
    } catch (error) { /* Handled by apiRequest */ }
}

function initiateEditDataStore(id, name, description) { 
    newDataStoreNameInput.value = name;
    newDataStoreDescriptionInput.value = description;
    showStatus(translate('status_editing_datastore_note', `Editing store: ${name}. (Note: Save functionality for edit uses the 'Create Store' button logic but would ideally be a PUT request to /api/datastores/${id})`, {name: name}), 'info', createDataStoreStatus);
}

async function deleteDataStore(id, name) {
    if (!confirm(translate('confirm_delete_datastore', `Are you sure you want to delete data store "${name}" and all its indexed files? This cannot be undone.`, {name: name}))) return;
    showStatus(translate('status_deleting_datastore', `Deleting data store ${name}...`, {name: name}), 'info', createDataStoreStatus); 
    try {
        await apiRequest(`/api/datastores/${id}`, { method: 'DELETE', statusElement: createDataStoreStatus });
        showStatus(translate('status_datastore_deleted_success', `Data Store "${name}" deleted.`, {name: name}), 'success', createDataStoreStatus);
        await loadDataStores(); 
    } catch (error) { /* Handled by apiRequest */ }
}

function initiateShareDataStore(id, name) {
    shareDataStoreIdInput.value = id;
    shareDataStoreTitle.textContent = translate('share_datastore_modal_title', `Share Data Store: "${name}"`, {name: name});
    shareTargetUsernameDSInput.value = '';
    showStatus('', 'info', shareDataStoreStatus);
    openModal('shareDataStoreModal');
}

confirmShareDataStoreBtn.onclick = async () => {
    const datastoreId = shareDataStoreIdInput.value;
    const targetUsername = shareTargetUsernameDSInput.value.trim();
    if (!datastoreId || !targetUsername) {
        showStatus(translate('share_datastore_target_user_required_error'), 'error', shareDataStoreStatus);
        return;
    }
    showStatus(translate('status_sharing_datastore_with_user', `Sharing data store with ${targetUsername}...`, {username: targetUsername}), 'info', shareDataStoreStatus);
    try {
        await apiRequest(`/api/datastores/${datastoreId}/share`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_username: targetUsername, permission_level: "read_query" }), 
            statusElement: shareDataStoreStatus
        });
        showStatus(translate('status_datastore_shared_success', 'Data Store shared successfully!'), 'success', shareDataStoreStatus);
        setTimeout(() => closeModal('shareDataStoreModal'), 1500);
    } catch (error) { /* Handled by apiRequest */ }
};

function setDiscussionRagStore(datastoreId) {
    if (!currentDiscussionId) {
        showStatus(translate('status_select_discussion_first_warning'), "warning");
        closeModal('dataStoresModal'); 
        return;
    }
    ragDataStoreSelect.value = datastoreId;
    ragDataStoreSelect.dispatchEvent(new Event('change')); 
    closeModal('dataStoresModal');
}

// --- File Management Modal Logic ---
async function openFileManagerForStore(datastoreId, datastoreName) {
    closeModal('dataStoresModal'); 
    fileManagerCurrentDataStoreId.value = datastoreId;
    fileManagerDataStoreName.textContent = datastoreName;
    
    showStatus('', 'info', uploadStatus); showStatus('', 'info', fileListStatus);
    if(fileUploadInputFS) fileUploadInputFS.value = ''; 
    confirmUploadBtn.disabled = true;
    
    try {
        const response = await apiRequest(`/api/store/${datastoreId}/vectorizers`);
        const storeVectorizers = await response.json();
        populateDropdown(fileVectorizerSelect, storeVectorizers, null, translate('file_manager_vectorizer_select_default'), true);
    } catch (error) {
        populateDropdown(fileVectorizerSelect, [], null, translate('file_manager_error_loading_vectorizers'), true);
    }
    
    await loadIndexedRagFilesInStore(datastoreId);
    openModal('fileManagementModal');
}
async function loadIndexedRagFilesInStore(datastoreId) {
        indexedFileList.innerHTML = `<p class="text-gray-500 italic px-1">${translate('file_manager_loading_files')}</p>`;
        try {
            const response = await apiRequest(`/api/store/${datastoreId}/files`);
            const files = await response.json(); renderRagFileList(files);
        } catch (error) { renderRagFileList(null, translate('file_manager_error_loading_files_detail')); }
}
function updateConfirmUploadBtnState() {
        if (!fileUploadInputFS) return; 
        const filesSelected = fileUploadInputFS.files && fileUploadInputFS.files.length > 0;
        const vectorizerSelected = fileVectorizerSelect.value !== ""; confirmUploadBtn.disabled = !(filesSelected && vectorizerSelected);
}
if(fileUploadInputFS) fileUploadInputFS.onchange = updateConfirmUploadBtnState;
if(fileVectorizerSelect) fileVectorizerSelect.onchange = updateConfirmUploadBtnState;

confirmUploadBtn.onclick = async () => {
    const datastoreId = fileManagerCurrentDataStoreId.value;
    if (!datastoreId) { showStatus(translate('file_manager_no_datastore_selected_error'), "error", uploadStatus); return; }
    if (!fileUploadInputFS) { showStatus(translate('file_manager_file_input_not_found_error'), "error", uploadStatus); return; }

    const files = fileUploadInputFS.files; const vectorizer = fileVectorizerSelect.value;
    if (!files || files.length === 0 || !vectorizer) return;

    const formData = new FormData();
    for (const file of files) formData.append('files', file);
    formData.append('vectorizer_name', vectorizer);

    showStatus(translate('status_uploading_files_to_store', `Uploading ${files.length} file(s) to store using ${vectorizer}...`, {count: files.length, vectorizer: vectorizer}), 'info', uploadStatus);
    confirmUploadBtn.disabled = true;
    try {
            const response = await apiRequest(`/api/store/${datastoreId}/upload-files`, { method: 'POST', body: formData, statusElement: uploadStatus });
            const result = await response.json();
            let message = result.message || translate('status_upload_completed', "Upload completed.");
            let statusType = response.status === 207 ? 'warning' : 'success';
            if (response.status === 207) message = translate('status_upload_partial_success', `Upload finished. Processed: ${result.processed_files?.length || 0}, Errors: ${result.errors?.length || 0}`, {processed: result.processed_files?.length || 0, errors: result.errors?.length || 0});
            showStatus(message, statusType, uploadStatus);
            await loadIndexedRagFilesInStore(datastoreId);
            fileUploadInputFS.value = ''; updateConfirmUploadBtnState();
    } catch (error) { /* Handled by apiRequest */ }
    finally { confirmUploadBtn.disabled = false; updateConfirmUploadBtnState(); }
};
function renderRagFileList(files, message = null) { 
        indexedFileList.innerHTML = ''; if (message) { const msgElement = document.createElement('p'); msgElement.className = 'text-gray-500 italic px-1'; if(message.toLowerCase().includes("error")) msgElement.classList.add('text-red-400'); msgElement.textContent = message; indexedFileList.appendChild(msgElement); return; }
        if (!files || files.length === 0) { indexedFileList.innerHTML = `<p class="text-gray-500 italic px-1">${translate('file_manager_no_indexed_docs')}</p>`; return; }
        files.forEach(file => {
            const fileDiv = document.createElement('div'); fileDiv.className = 'flex justify-between items-center py-1 px-1 hover:bg-gray-700 rounded';
            const fileNameSpan = document.createElement('span'); fileNameSpan.textContent = file.filename; fileNameSpan.className = 'truncate text-sm text-gray-200'; fileNameSpan.title = file.filename;
            const deleteBtn = document.createElement('button');
            deleteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>`;
            deleteBtn.className = 'flex-shrink-0 text-red-400 hover:text-red-300 p-1 rounded hover:bg-red-700 ml-2'; 
            deleteBtn.title = translate('delete_rag_file_tooltip', `Delete ${file.filename}`, {filename: file.filename});
            deleteBtn.onclick = () => deleteRagFileInModal(file.filename);
            fileDiv.appendChild(fileNameSpan); fileDiv.appendChild(deleteBtn); indexedFileList.appendChild(fileDiv);
        });
}
async function deleteRagFileInModal(filename) {
        const datastoreId = fileManagerCurrentDataStoreId.value;
        if (!datastoreId) { showStatus(translate('file_manager_no_datastore_for_delete_error'), "error", fileListStatus); return; }
        if (!confirm(translate('confirm_delete_rag_file', `Are you sure you want to delete RAG document "${filename}" from this store?`, {filename: filename}))) return;
        showStatus(translate('status_deleting_rag_file', `Deleting ${filename}...`, {filename: filename}), 'info', fileListStatus);
        try {
            await apiRequest(`/api/store/${datastoreId}/files/${encodeURIComponent(filename)}`, { method: 'DELETE', statusElement: fileListStatus });
            showStatus(translate('status_rag_file_deleted_success', `Deleted ${filename}.`, {filename: filename}), 'success', fileListStatus);
            await loadIndexedRagFilesInStore(datastoreId); 
        } catch (error) { /* Handled by apiRequest */ }
}

// --- RAG Toggle Logic ---
ragToggleBtn.onclick = () => {
        if (availableDataStoresForRag.length === 0) {
            showStatus(translate('rag_cannot_enable_no_stores_warning'), 'warning');
            return;
        }
        isRagActive = !isRagActive;
        updateRagToggleButtonState();
        if (isRagActive && !ragDataStoreSelect.value && availableDataStoresForRag.length > 0) {
            ragDataStoreSelect.value = availableDataStoresForRag[0].id; 
            ragDataStoreSelect.dispatchEvent(new Event('change')); 
        } else if (!isRagActive && currentDiscussionId && discussions[currentDiscussionId]) {
            ragDataStoreSelect.value = ""; 
            ragDataStoreSelect.dispatchEvent(new Event('change'));
        }
        showStatus(translate(isRagActive ? 'status_rag_active' : 'status_rag_inactive', `RAG is now ${isRagActive ? 'ACTIVE' : 'INACTIVE'}.`), 'info');
};
function updateRagToggleButtonState() {
    const hasDataStores = availableDataStoresForRag.length > 0;
    ragToggleBtn.disabled = !hasDataStores;
    ragDataStoreSelect.style.display = (isRagActive && hasDataStores) ? 'inline-block' : 'none';

    if (!hasDataStores) {
        ragToggleBtn.classList.remove('rag-toggle-on'); ragToggleBtn.classList.add('rag-toggle-off');
        ragToggleBtn.title = translate('rag_toggle_btn_title_no_stores'); 
        isRagActive = false; return;
    }
    if (isRagActive) {
        ragToggleBtn.classList.remove('rag-toggle-off'); ragToggleBtn.classList.add('rag-toggle-on');
        const selectedDS = availableDataStoresForRag.find(ds => ds.id === ragDataStoreSelect.value);
        ragToggleBtn.title = translate('rag_toggle_btn_title_on', `RAG Active ${selectedDS ? `(Using: ${selectedDS.name})` : '(Select Store)'} - Click to disable`, {datastore_name: selectedDS ? selectedDS.name : translate('rag_select_store_text', '(Select Store)')});
    } else {
        ragToggleBtn.classList.remove('rag-toggle-on'); ragToggleBtn.classList.add('rag-toggle-off');
        ragToggleBtn.title = translate('rag_toggle_btn_title_off');
    }
}

function renderCustomCodeBlocks(element, messageId) {
    element.querySelectorAll('pre').forEach((preElement) => {
        if (preElement.parentElement.classList.contains('code-block-wrapper')) return; 

        const codeElement = preElement.querySelector('code');
        if (!codeElement) return;

        let language = 'plaintext';
        const langClassMatch = Array.from(codeElement.classList).find(cls => cls.startsWith('language-'));
        if (langClassMatch) language = langClassMatch.substring('language-'.length);
        else { const hljsLangClass = Array.from(codeElement.classList).find(cls => hljs.getLanguage(cls)); if(hljsLangClass) language = hljsLangClass; }

        const code = codeElement.textContent || '';
        const wrapperDiv = document.createElement('div'); wrapperDiv.className = 'code-block-wrapper'; 
        const header = document.createElement('div'); header.className = 'code-block-header';
        const langSpan = document.createElement('span'); langSpan.textContent = language; langSpan.className = 'text-xs font-semibold';
        const buttonsDiv = document.createElement('div'); buttonsDiv.className = 'code-block-buttons';

        const copyBtn = document.createElement('button');
        copyBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 inline-block mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg><span data-translate-key="copy_code_btn_text">${translate('copy_code_btn_text', 'Copy')}</span>`;
        copyBtn.title = translate('copy_code_tooltip');
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(code).then(() => {
                const originalText = copyBtn.querySelector('span').textContent;
                copyBtn.querySelector('span').textContent = translate('copied_code_btn_text', 'Copied!');
                setTimeout(() => { copyBtn.querySelector('span').textContent = originalText; }, 1500);
            }).catch(err => console.error("Copy failed", err));
        };
        buttonsDiv.appendChild(copyBtn);

        if (language === 'python') {
            const execBtn = document.createElement('button');
            execBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 inline-block mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg><span data-translate-key="run_code_btn_text">${translate('run_code_btn_text', 'Run')}</span>`;
            execBtn.title = translate('execute_python_code_tooltip');
            execBtn.onclick = () => executePythonCode(code, wrapperDiv); 
            buttonsDiv.appendChild(execBtn);
        }
        header.appendChild(langSpan); header.appendChild(buttonsDiv);
        
        preElement.parentNode.insertBefore(wrapperDiv, preElement);
        wrapperDiv.appendChild(header); wrapperDiv.appendChild(preElement); 
        preElement.classList.add('relative'); 
    });
}
// --- Re-add the other functions from your original script ---
// handleImageFileSelection, renderImagePreview, viewImage,
// handleSettingsTabSwitch, loadAvailableLollmsModels, saveLollmsModelConfig, saveLLMParamsConfig, handleChangePassword, populateSettingsModal,
// loadDataStores, populateRagDataStoreSelect, populateDataStoresModal, handleCreateDataStore, initiateEditDataStore, deleteDataStore,
// initiateShareDataStore, confirmShareDataStore, setDiscussionRagStore,
// openFileManagerForStore, loadIndexedRagFilesInStore, updateConfirmUploadBtnState, handleRagFileUpload (was confirmUploadBtn.onclick), renderRagFileList, deleteRagFileInModal,
// updateRagToggleButtonState (ensure it uses new RAG state logic),
// populateExportModal, handleExportData (was confirmExportBtn.onclick), handleImportFileChange (was importFile.onchange), handleConfirmImport (was confirmImportBtn.onclick),
// Python execution functions: loadPyodide, executePythonCode, showPyodideStatus
// All your `createActionButton`, `getSenderAvatar`, `formatTimestamp`, `addCodeBlockCopyButtons`, `renderSteps`, `renderMetadata`, `escapeHtml`, syntax highlighting helpers etc.
// from the "Enhanced message rendering" section should be included.
// Make sure they are compatible with the overall structure.

function formatTimestamp(date) {
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    
    return date.toLocaleDateString();
}
function formatProcessingTime(ms) {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
}


async function handleExportData(params) {
    const selectedIds = Array.from(exportDiscussionList.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.value); closeModal('exportModal'); showStatus(translate('status_exporting_data', 'Exporting data...'), 'info');
    try {
            const requestBody = { discussion_ids: selectedIds.length > 0 ? selectedIds : null };
            const response = await apiRequest('/api/discussions/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(requestBody) });
            const exportData = await response.json(); const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob);
            const a = document.createElement('a'); a.href = url; const timestamp = new Date().toISOString().replace(/[:.]/g, '-'); a.download = `simplified_lollms_export_${currentUser.username}_${timestamp}.json`; document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url);
            showStatus(translate('status_data_exported_success', 'Data exported successfully.'), 'success');
    } catch (error) { /* Handled by apiRequest */ }
};



async function handleImportFileChange(params) {
    const file = importFile.files[0]; parsedImportData = null; importPreviewArea.style.display = 'none'; importDiscussionList.innerHTML = ''; confirmImportBtn.disabled = true; showStatus('', 'info', importStatus); if (!file) return;
    if (file.type !== 'application/json') { showStatus(translate('import_invalid_json_error'), 'error', importStatus); return; }
    showStatus(translate('status_reading_import_file', 'Reading file...'), 'info', importStatus);
    try {
        const content = await file.text(); parsedImportData = JSON.parse(content);
        if (!parsedImportData || !Array.isArray(parsedImportData.discussions)) throw new Error(translate('import_invalid_file_format_error'));
            if (parsedImportData.discussions.length === 0) { importDiscussionList.innerHTML = `<p class="text-gray-500 italic">${translate('import_no_discussions_in_file')}</p>`; confirmImportBtn.disabled = true; }
            else { parsedImportData.discussions.forEach((disc, index) => { if (!disc || typeof disc.discussion_id !== 'string') { return; } const div = document.createElement('div'); div.className = 'flex items-center'; const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.id = `import-check-${disc.discussion_id}`; checkbox.value = disc.discussion_id; checkbox.checked = true; checkbox.className = 'h-4 w-4 mr-2 rounded border-gray-600 text-blue-500 bg-gray-700 shadow-sm focus:border-blue-500 focus:ring-2 focus:ring-offset-0 focus:ring-blue-500 focus:ring-opacity-50'; const label = document.createElement('label'); label.htmlFor = `import-check-${disc.discussion_id}`; label.textContent = `${disc.title || translate('untitled_discussion_placeholder')} (ID: ...${disc.discussion_id.slice(-6)})`; label.className = 'text-sm text-gray-300'; div.appendChild(checkbox); div.appendChild(label); importDiscussionList.appendChild(div); }); confirmImportBtn.disabled = importDiscussionList.childElementCount === 0; }
            importPreviewArea.style.display = 'block'; showStatus('', 'info', importStatus);
    } catch (error) { showStatus(translate('import_error_reading_file', `Error reading file: ${error.message}`, {message: error.message}), 'error', importStatus); parsedImportData = null; confirmImportBtn.disabled = true; }
}

async function handleConfirmImport(params) {
        if (!parsedImportData || !importFile.files[0]) return;
        const selectedOriginalIds = Array.from(importDiscussionList.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.value); if (selectedOriginalIds.length === 0) { showStatus(translate('import_select_one_discussion_error'), 'error', importStatus); return; }
        showStatus(translate('status_importing_discussions', 'Importing discussions...'), 'info', importStatus); confirmImportBtn.disabled = true;
        try {
        const importRequest = { discussion_ids_to_import: selectedOriginalIds }; const formData = new FormData(); formData.append('import_file', importFile.files[0]); formData.append('import_request_json', JSON.stringify(importRequest));
            const response = await apiRequest('/api/discussions/import', { method: 'POST', body: formData, statusElement: importStatus });
            const result = await response.json(); showStatus(result.message || translate('status_import_count_success', `Imported ${result.imported_count} discussions.`, {count: result.imported_count}), 'success', importStatus);
            await loadDiscussions(); setTimeout(() => closeModal('importModal'), 2000);
        } catch (error) { confirmImportBtn.disabled = false; /* Handled by apiRequest */ }
};

async function handleRagFileUpload(){
    const datastoreId = fileManagerCurrentDataStoreId.value;
    if (!datastoreId) { showStatus(translate('file_manager_no_datastore_selected_error'), "error", uploadStatus); return; }
    if (!fileUploadInputFS) { showStatus(translate('file_manager_file_input_not_found_error'), "error", uploadStatus); return; }

    const files = fileUploadInputFS.files; const vectorizer = fileVectorizerSelect.value;
    if (!files || files.length === 0 || !vectorizer) return;

    const formData = new FormData();
    for (const file of files) formData.append('files', file);
    formData.append('vectorizer_name', vectorizer);

    showStatus(translate('status_uploading_files_to_store', `Uploading ${files.length} file(s) to store using ${vectorizer}...`, {count: files.length, vectorizer: vectorizer}), 'info', uploadStatus);
    confirmUploadBtn.disabled = true;
    try {
            const response = await apiRequest(`/api/store/${datastoreId}/upload-files`, { method: 'POST', body: formData, statusElement: uploadStatus });
            const result = await response.json();
            let message = result.message || translate('status_upload_completed', "Upload completed.");
            let statusType = response.status === 207 ? 'warning' : 'success';
            if (response.status === 207) message = translate('status_upload_partial_success', `Upload finished. Processed: ${result.processed_files?.length || 0}, Errors: ${result.errors?.length || 0}`, {processed: result.processed_files?.length || 0, errors: result.errors?.length || 0});
            showStatus(message, statusType, uploadStatus);
            await loadIndexedRagFilesInStore(datastoreId);
            fileUploadInputFS.value = ''; updateConfirmUploadBtnState();
    } catch (error) { /* Handled by apiRequest */ }
    finally { confirmUploadBtn.disabled = false; updateConfirmUploadBtnState(); }
};

// Example of adapting a function:
function updateRagToggleButtonState() {
    if (!ragToggleBtn || !ragDataStoreSelect) return;
    const disc = currentDiscussionId ? discussions[currentDiscussionId] : null;
    const currentDiscussionRagStore = disc ? disc.rag_datastore_id : null;

    const hasDataStores = availableDataStoresForRag.length > 0;
    ragToggleBtn.disabled = !hasDataStores;
    ragDataStoreSelect.style.display = (isRagActive && hasDataStores) ? 'inline-block' : 'none';

    if (!hasDataStores) {
        ragToggleBtn.classList.remove('rag-toggle-on'); ragToggleBtn.classList.add('rag-toggle-off');
        ragToggleBtn.title = translate('rag_toggle_btn_title_no_stores');
        isRagActive = false; // Force off if no stores
        if (disc && disc.rag_datastore_id) { // If a store was set but now none available
            disc.rag_datastore_id = null;
            updateDiscussionRagStoreOnBackend(currentDiscussionId, null);
        }
        return;
    }

    // Sync isRagActive with discussion's RAG state if a discussion is selected
    if (disc) {
        isRagActive = !!currentDiscussionRagStore;
    }


    if (isRagActive) {
        ragToggleBtn.classList.remove('rag-toggle-off'); ragToggleBtn.classList.add('rag-toggle-on');
        const selectedDS = availableDataStoresForRag.find(ds => ds.id === currentDiscussionRagStore);
        ragToggleBtn.title = translate('rag_toggle_btn_title_on', `RAG Active ${selectedDS ? `(Using: ${selectedDS.name})` : '(Select Store)'}`, { datastore_name: selectedDS ? selectedDS.name : translate('rag_select_store_text', '(Select Store)') });
        if (currentDiscussionRagStore) {
            ragDataStoreSelect.value = currentDiscussionRagStore;
        } else if (ragDataStoreSelect.options.length > 1) { // Has a default "" and actual stores
             // If RAG is active but no specific store selected for discussion, default to first actual store
            if(availableDataStoresForRag.length > 0){
                const firstStoreId = availableDataStoresForRag[0].id;
                ragDataStoreSelect.value = firstStoreId;
                if(disc) disc.rag_datastore_id = firstStoreId; // Also update local state
                updateDiscussionRagStoreOnBackend(currentDiscussionId, firstStoreId); // And backend
            }
        }
    } else {
        ragToggleBtn.classList.remove('rag-toggle-on'); ragToggleBtn.classList.add('rag-toggle-off');
        ragToggleBtn.title = translate('rag_toggle_btn_title_off');
        ragDataStoreSelect.value = ""; // Clear select if RAG is off
    }
}


// Make sure that all the helper functions for rendering messages (like formatTimestamp, getSenderAvatar, createActionButton, etc.)
// are defined in your script. Many of these were part of the "enhanced rendering" section you provided previously.
// I've included placeholders for some and assumed others.

// Full list of functions from your original JS that need to be present:
// All DOM element event handlers and their corresponding functions
// All modal population and interaction functions
// All API interaction functions for settings, data stores, RAG files, export/import, etc.
// All utility functions.

// Placeholder for KaTeX rendering if you use it
function renderMathInElement(element, options) {
    if (typeof katex !== 'undefined' && typeof renderMathInElement === 'function') { // Check if the actual KaTeX auto-render is loaded
        // This is usually a global function provided by KaTeX auto-render extension
        // If you're calling katex.render directly, your logic would be different.
        // The original had this structure, implying auto-render.
        // For manual:
        // element.querySelectorAll('.math-inline').forEach(el => katex.render(el.textContent, el, {displayMode: false, ...options}));
        // element.querySelectorAll('.math-display').forEach(el => katex.render(el.textContent, el, {displayMode: true, ...options}));
    }
}
// Ensure all your `createActionButton`, `getSenderAvatar`, `formatTimestamp`, `formatProcessingTime`,
// `addCodeBlockCopyButtons`, `renderSteps`, `renderMetadata`, `escapeHtml`, and various syntax
// highlighting functions (`highlightJavaScript`, `highlightPython`, etc.) are defined.
// Also, `applySyntaxHighlighting` and `enhanceMarkdownContent` from the previous message.

// Syntax highlighting function
function applySyntaxHighlighting(container) {
    const codeBlocks = container.querySelectorAll('pre code[class*="language-"]');
    
    codeBlocks.forEach(block => {
        const language = block.className.match(/language-(\w+)/)?.[1] || 'text';
        
        // Apply syntax highlighting based on language
        if (typeof Prism !== 'undefined' && Prism.languages[language]) {
            // Using Prism.js if available
            const highlighted = Prism.highlight(block.textContent, Prism.languages[language], language);
            block.innerHTML = highlighted;
        } else {
            // Fallback to basic highlighting
            applyBasicSyntaxHighlighting(block, language);
        }
        
        // Add language-specific styling
        block.parentElement.setAttribute('data-language', language);
    });
}

function applyBasicSyntaxHighlighting(codeElement, language) {
    if (!hljs) {
        console.error("Highlight.js not loaded!");
        // Fallback: just display plain text, ensuring HTML entities are escaped
        const plainText = document.createTextNode(codeElement.textContent || "");
        codeElement.innerHTML = ''; // Clear existing content
        codeElement.appendChild(plainText);
        return;
    }

    // Highlight.js uses CSS classes to determine the language.
    // It's good practice to clear any previous language classes
    // and set the new one.
    // Example: if codeElement has class="language-python", hljs will use python.
    // If no language class is present, it will try to auto-detect.

    let langClass = '';
    if (language) {
        const lang = language.toLowerCase();
        // Normalize common aliases to what Highlight.js expects
        switch (lang) {
            case 'js':
                langClass = 'language-javascript';
                break;
            case 'py':
                langClass = 'language-python';
                break;
            case 'shell':
                langClass = 'language-bash'; // 'bash' is a common alias for shell scripts
                break;
            // Add other common aliases if your input `language` might use them
            // e.g., 'txt' -> 'language-plaintext'
            // default: use the language name directly if it's a valid hljs identifier
            default:
                // Check if hljs supports the language directly
                if (hljs.getLanguage(lang)) {
                    langClass = `language-${lang}`;
                } else {
                    // If language is unknown to hljs, let it auto-detect or treat as plain text
                    console.warn(`Highlight.js: Unknown language "${lang}", attempting auto-detection or plaintext.`);
                    // You might want to explicitly set 'language-plaintext' if auto-detection is not desired
                    // langClass = 'language-plaintext';
                }
        }
    }

    // Clear any existing language-xxxx classes and add the new one
    // This regex finds classes like "language-javascript", "lang-js" etc.
    const existingLangClassRegex = /\blang(?:uage)?-[a-zA-Z0-9_.-]+\b/g;
    codeElement.className = codeElement.className.replace(existingLangClassRegex, '').trim();

    if (langClass) {
        codeElement.classList.add(langClass);
    }
    // Else, if no specific language or langClass determined, hljs will auto-detect.

    // The highlightElement function takes care of reading textContent,
    // highlighting, and setting innerHTML.
    // It also adds the 'hljs' class to the element for general styling.
    hljs.highlightElement(codeElement);
}
// --- Pyodide Python Execution ---
async function loadPyodide() {
    if (pyodide || pyodideLoading) return;
    pyodideLoading = true; showPyodideStatus(translate('pyodide_loading_interpreter', 'Loading Python interpreter...'));
    try {
        if (typeof window.loadPyodide !== "function") {
            throw new Error(translate('pyodide_script_not_loaded_error'));
        }
        pyodide = await window.loadPyodide({ indexURL: "https://cdn.jsdelivr.net/pyodide/v0.25.1/full/" });
        if (!pyodide || typeof pyodide.loadPackage !== 'function') {
            throw new Error(translate('pyodide_object_load_failed_error'));
        }
        await pyodide.loadPackage("micropip");
        showPyodideStatus(translate('pyodide_ready_status', 'Python ready.')); setTimeout(() => showPyodideStatus(''), 3000);
    } catch (error) { 
        showPyodideStatus(translate('pyodide_load_error', `Error loading Python: ${error.message}`, {message: error.message}), true); 
        pyodide = null; 
    }
    finally { pyodideLoading = false; }
}
async function executePythonCode(code, codeContainerElement) { 
        await loadPyodide(); if (!pyodide) { showPyodideStatus(translate('pyodide_not_available_error'), true); return; }
        
        let outputDiv = codeContainerElement.querySelector('.code-output');
        if (outputDiv) { 
            outputDiv.textContent = '';
        } else { 
            outputDiv = document.createElement('pre');
            outputDiv.className = 'code-output'; 
            codeContainerElement.appendChild(outputDiv);
        }
        outputDiv.textContent = translate('pyodide_executing_text', 'Executing...') + '\n'; 

        let stdoutBuffer = ''; let stderrBuffer = '';
        pyodide.setStdout({ batched: (msg) => { stdoutBuffer += msg + '\n'; outputDiv.textContent += msg + '\n'; outputDiv.scrollTop = outputDiv.scrollHeight;} });
        pyodide.setStderr({ batched: (msg) => { stderrBuffer += msg + '\n'; outputDiv.textContent += `${translate('pyodide_error_prefix', 'Error:')} ${msg}\n`; outputDiv.scrollTop = outputDiv.scrollHeight;} });
        
        showPyodideStatus(translate('pyodide_running_code_status', 'Running Python code...'));
        try {
            const lines = code.split('\n');
            const installCommands = lines.filter(line => line.trim().startsWith('%pip install') || line.trim().startsWith('!pip install'));
            const codeToRun = lines.filter(line => !line.trim().startsWith('%pip install') && !line.trim().startsWith('!pip install')).join('\n');
            
            if (installCommands.length > 0) {
                outputDiv.textContent += translate('pyodide_installing_packages_text', 'Installing packages...') + '\n';
                const micropip = pyodide.pyimport("micropip");
                for (const cmd of installCommands) {
                    const packages = cmd.split('install')[1].trim().split(' ');
                    outputDiv.textContent += `> ${cmd}\n`; 
                    await micropip.install(packages);
                    outputDiv.textContent += translate('pyodide_packages_installed_text', `Packages installed: ${packages.join(', ')}`, { packages: packages.join(', ')}) + '\n';
                    outputDiv.scrollTop = outputDiv.scrollHeight;
                }
                outputDiv.textContent += translate('pyodide_installation_complete_text', 'Installation complete. Running code...') + '\n';
                outputDiv.scrollTop = outputDiv.scrollHeight;
            }
            
            let result = await pyodide.runPythonAsync(codeToRun);
            if (result !== undefined) {
            outputDiv.textContent += `\n${translate('pyodide_result_prefix', 'Result:')} ${result}\n`;
            outputDiv.scrollTop = outputDiv.scrollHeight;
            }
            if (!stderrBuffer) outputDiv.textContent += '\n' + translate('pyodide_execution_finished_text', 'Execution finished.');
            showPyodideStatus(translate('pyodide_execution_finished_status', 'Python execution finished.'));
        } catch (error) { 
            outputDiv.textContent += `\n${translate('pyodide_execution_error_prefix', 'Execution Error:')} ${error.message}\n`; 
            outputDiv.scrollTop = outputDiv.scrollHeight;
            showPyodideStatus(translate('pyodide_execution_failed_status', 'Python execution failed.'), true); 
    }
        finally { 
            pyodide.setStdout({}); pyodide.setStderr({}); 
            setTimeout(() => showPyodideStatus(''), 3000); 
    }
}
function showPyodideStatus(msg, isError = false) {
    pyodideStatus.textContent = msg;
    pyodideStatus.className = `text-xs mt-1 h-4 text-center ${isError ? 'text-red-400' : 'text-blue-400'}`;
}

// --- Settings Modal Logic --- 
settingsBtn.onclick = () => openModal('settingsModal');

function handleSettingsTabSwitch(tabId) {
    document.querySelectorAll('#settingsModal .settings-tab-content').forEach(content => {
        content.style.display = 'none';
    });
    document.querySelectorAll('#settingsModal .settings-tab-btn').forEach(button => {
        button.classList.remove('active-tab');
    });

    document.getElementById(tabId).style.display = 'block';
    document.querySelector(`#settingsModal .settings-tab-btn[data-tab="${tabId}"]`).classList.add('active-tab');
}

async function loadAvailableLollmsModels() { 
        try {
        const response = await apiRequest('/api/config/lollms-models');
        if (!response.ok) throw new Error(`API failed: ${response.status}`);
        availableLollmsModels = await response.json();
        populateDropdown(settingsLollmsModelSelect, availableLollmsModels, currentUser.lollms_model_name, translate('settings_no_models_found'));
        } catch (error) {
            availableLollmsModels = [];
            populateDropdown(settingsLollmsModelSelect, [], null, translate('settings_error_loading_models', `Error: ${error.message || 'Failed to load'}`, {message: error.message || 'Failed to load'}));
        }
    }

settingsLollmsModelSelect.onchange = () => { saveModelAndVectorizerBtn.disabled = (settingsLollmsModelSelect.value === currentUser.lollms_model_name); };

saveModelAndVectorizerBtn.onclick = async () => {
    const selectedModel = settingsLollmsModelSelect.value;
    let modelChanged = selectedModel && selectedModel !== currentUser.lollms_model_name;
    if (!modelChanged) return;

    showStatus(translate('status_saving_model', 'Saving model...'), 'info', settingsStatus_llmConfig); 
    saveModelAndVectorizerBtn.disabled = true;
    try {
        if (modelChanged) {
            const formData = new FormData(); formData.append('model_name', selectedModel);
            await apiRequest('/api/config/lollms-model', { method: 'POST', body: formData, statusElement: settingsStatus_llmConfig });
            currentUser.lollms_model_name = selectedModel;
        }
        showStatus(translate('status_model_saved_success', 'Model saved. LLM Client will re-init if model changed.'), 'success', settingsStatus_llmConfig);
    } catch (error) { /* Handled by apiRequest */ 
    } finally {
        saveModelAndVectorizerBtn.disabled = (settingsLollmsModelSelect.value === currentUser.lollms_model_name);
    }
};

[settingsTemperature, settingsTopK, settingsTopP, settingsRepeatPenalty, settingsRepeatLastN].forEach(el => {
    el.oninput = () => { saveLLMParamsBtn.disabled = false; };
});

saveLLMParamsBtn.onclick = async () => {
    const params = {
        llm_temperature: parseFloat(settingsTemperature.value) || null,
        llm_top_k: parseInt(settingsTopK.value) || null,
        llm_top_p: parseFloat(settingsTopP.value) || null,
        llm_repeat_penalty: parseFloat(settingsRepeatPenalty.value) || null,
        llm_repeat_last_n: parseInt(settingsRepeatLastN.value) || null,
    };
    const payload = Object.fromEntries(Object.entries(params).filter(([_, v]) => v !== null && !isNaN(v)));

    showStatus(translate('status_saving_llm_params', 'Saving LLM parameters...'), 'info', settingsStatus_llmParams); 
    saveLLMParamsBtn.disabled = true;
    try {
        await apiRequest('/api/config/llm-params', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            statusElement: settingsStatus_llmParams
        });
        Object.assign(currentUser, payload);
        showStatus(translate('status_llm_params_saved_success', 'LLM parameters saved.'), 'success', settingsStatus_llmParams);
    } catch (error) { /* Handled by apiRequest */ 
    } finally {
        saveLLMParamsBtn.disabled = false;
    }
};

[settingsCurrentPassword, settingsNewPassword, settingsConfirmPassword].forEach(el => {
    el.oninput = () => {
        changePasswordBtn.disabled = !(settingsCurrentPassword.value && settingsNewPassword.value && settingsConfirmPassword.value);
    };
});
function handleSettingsTabSwitch(tabId) { /* As provided */
    document.querySelectorAll('#settingsModal .settings-tab-content').forEach(content => {
        content.style.display = 'none';
    });
    document.querySelectorAll('#settingsModal .settings-tab-btn').forEach(button => {
        button.classList.remove('active-tab');
    });
    const tabContent = document.getElementById(tabId);
    const tabButton = document.querySelector(`#settingsModal .settings-tab-btn[data-tab="${tabId}"]`);
    if(tabContent) tabContent.style.display = 'block';
    if(tabButton) tabButton.classList.add('active-tab');
}

async function loadAvailableLollmsModels() { /* As provided */
    try {
        const response = await apiRequest('/api/config/lollms-models');
        if (!response.ok) throw new Error(`API failed: ${response.status}`); // Should be caught by apiRequest already
        availableLollmsModels = await response.json();
        populateDropdown(settingsLollmsModelSelect, availableLollmsModels, currentUser?.lollms_model_name, translate('settings_no_models_found'));
    } catch (error) {
        availableLollmsModels = [];
        populateDropdown(settingsLollmsModelSelect, [], null, translate('settings_error_loading_models', `Error: ${error.message || 'Failed to load'}`, { message: error.message || 'Failed to load' }));
    }
}

// **RENAMED AND DEFINED AS SEPARATE FUNCTION**
async function handleSaveModelAndVectorizer() {
    if (!settingsLollmsModelSelect || !currentUser || !saveModelAndVectorizerBtn) return;

    const selectedModel = settingsLollmsModelSelect.value;
    let modelChanged = selectedModel && selectedModel !== currentUser.lollms_model_name;

    if (!modelChanged) {
        showStatus(translate('status_no_model_changes', 'No model changes to save.'), 'info', settingsStatus_llmConfig);
        return;
    }

    showStatus(translate('status_saving_model', 'Saving model...'), 'info', settingsStatus_llmConfig);
    saveModelAndVectorizerBtn.disabled = true;
    try {
        const formData = new FormData(); formData.append('model_name', selectedModel);
        await apiRequest('/api/config/lollms-model', { method: 'POST', body: formData, statusElement: settingsStatus_llmConfig });
        currentUser.lollms_model_name = selectedModel; // Update local currentUser state
        showStatus(translate('status_model_saved_success', 'Model saved. LLM Client will re-init if model changed.'), 'success', settingsStatus_llmConfig);
    } catch (error) {
        // apiRequest should handle showing the error status
        saveModelAndVectorizerBtn.disabled = false; // Re-enable on error
    } finally {
        // Disable button again only if selection matches current user setting (or it was re-enabled by error)
        if (settingsLollmsModelSelect.value === currentUser.lollms_model_name && !saveModelAndVectorizerBtn.disabled) {
             saveModelAndVectorizerBtn.disabled = true;
        }
    }
}

// **RENAMED AND DEFINED AS SEPARATE FUNCTION**
async function handleSaveLLMParams() {
    if (!settingsTemperature || !settingsTopK || !settingsTopP || !settingsRepeatPenalty || !settingsRepeatLastN || !saveLLMParamsBtn) return;

    const params = {
        llm_temperature: parseFloat(settingsTemperature.value) || null,
        llm_top_k: parseInt(settingsTopK.value) || null,
        llm_top_p: parseFloat(settingsTopP.value) || null,
        llm_repeat_penalty: parseFloat(settingsRepeatPenalty.value) || null,
        llm_repeat_last_n: parseInt(settingsRepeatLastN.value) || null,
    };
    // Filter out null/NaN values before sending, backend might expect only present values
    const payload = Object.fromEntries(Object.entries(params).filter(([_, v]) => v !== null && !isNaN(v)));

    // Check if anything actually changed
    let changed = false;
    if (currentUser) {
        for (const key in payload) {
            if (payload[key] !== currentUser[key]) { // Compare against potentially different types (e.g. string from input vs number in currentUser)
                if (parseFloat(payload[key]) !== parseFloat(currentUser[key])) { // Ensure numeric comparison
                     changed = true; break;
                }
            }
        }
         // Check for cases where a value is cleared (becomes null) from a previously set value
        for (const key of ['llm_temperature', 'llm_top_k', 'llm_top_p', 'llm_repeat_penalty', 'llm_repeat_last_n']) {
            if (currentUser[key] !== null && currentUser[key] !== undefined && (params[key] === null || isNaN(params[key]))) {
                 changed = true; break;
            }
        }

    } else { changed = true; } // If no currentUser, assume changes are new

    if (!changed) {
        showStatus(translate('status_no_llm_param_changes', 'No LLM parameter changes to save.'), 'info', settingsStatus_llmParams);
        saveLLMParamsBtn.disabled = true; // Disable as no changes
        return;
    }

    showStatus(translate('status_saving_llm_params', 'Saving LLM parameters...'), 'info', settingsStatus_llmParams);
    saveLLMParamsBtn.disabled = true;
    try {
        await apiRequest('/api/config/llm-params', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            statusElement: settingsStatus_llmParams
        });
        if (currentUser) Object.assign(currentUser, payload); // Update local state
        showStatus(translate('status_llm_params_saved_success', 'LLM parameters saved.'), 'success', settingsStatus_llmParams);
    } catch (error) {
        // apiRequest handles status
        saveLLMParamsBtn.disabled = false; // Re-enable on error
    } finally {
        // Disable button again if no effective changes or it was re-enabled by error
        // This logic is tricky, better to just leave it enabled or rely on oninput disabling
        // saveLLMParamsBtn.disabled = true; // Or false to allow retry
    }
}
async function handleChangePassword() {
    const currentPassword = settingsCurrentPassword.value;
    const newPassword = settingsNewPassword.value;
    const confirmPassword = settingsConfirmPassword.value;

    if (!currentPassword || !newPassword || !confirmPassword) {
        showStatus(translate('settings_pwd_all_fields_required'), "error", passwordChangeStatus);
        return;
    }
    if (newPassword.length < 8) { 
        showStatus(translate('settings_pwd_new_min_length_error'), "error", passwordChangeStatus);
        return;
    }
    if (newPassword !== confirmPassword) {
        showStatus(translate('settings_pwd_mismatch_error'), "error", passwordChangeStatus);
        return;
    }

    showStatus(translate('status_changing_password', "Changing password..."), "info", passwordChangeStatus);
    changePasswordBtn.disabled = true;

    try {
        await apiRequest('/api/auth/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            }),
            statusElement: passwordChangeStatus 
        });
        showStatus(translate('status_password_changed_success', "Password changed successfully."), "success", passwordChangeStatus);
        settingsCurrentPassword.value = '';
        settingsNewPassword.value = '';
        settingsConfirmPassword.value = '';
    } catch (error) { /* Handled by apiRequest */
    } finally {
        changePasswordBtn.disabled = true;
    }
}

function populateSettingsModal() {
        populateDropdown(settingsLollmsModelSelect, availableLollmsModels, currentUser.lollms_model_name, translate('settings_no_models_found'));
        saveModelAndVectorizerBtn.disabled = true;
        showStatus('', 'info', settingsStatus_llmConfig);
        
        settingsTemperature.value = currentUser.llm_temperature ?? '';
        settingsTopK.value = currentUser.llm_top_k ?? '';
        settingsTopP.value = currentUser.llm_top_p ?? '';
        settingsRepeatPenalty.value = currentUser.llm_repeat_penalty ?? '';
        settingsRepeatLastN.value = currentUser.llm_repeat_last_n ?? '';
        saveLLMParamsBtn.disabled = true;
        showStatus('', 'info', settingsStatus_llmParams);

        settingsCurrentPassword.value = '';
        settingsNewPassword.value = '';
        settingsConfirmPassword.value = '';
        changePasswordBtn.disabled = true;
        showStatus('', 'info', passwordChangeStatus);
        
        handleSettingsTabSwitch('llmConfigTab');
}


// --- Image Upload Handling ---
async function handleImageFileSelection(event) {
    const files = Array.from(event.target.files);
    if (files.length === 0) return;
    if (uploadedImageServerPaths.length + files.length > 5) { 
        showStatus(translate('max_5_images_warning'), "warning"); return;
    }

    imageUploadPreviewContainer.style.display = 'flex';
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));

    showStatus(translate('status_uploading_images', "Uploading images..."), "info");
    try {
        const response = await apiRequest('/api/upload/chat_image', { method: 'POST', body: formData });
        const newUploadedImages = await response.json(); 
        
        newUploadedImages.forEach(imgInfo => {
            const originalFile = files.find(f => f.name === imgInfo.filename);
            if (originalFile) {
                uploadedImageServerPaths.push({ ...imgInfo, file_obj: originalFile }); 
                renderImagePreview(originalFile, imgInfo.server_path);
            }
        });
        showStatus(translate('status_images_ready_to_send', "Images ready to send."), "success");
        sendMessageBtn.disabled = generationInProgress; 
    } catch (error) {
        showStatus(translate('status_image_upload_failed', "Image upload failed."), "error");
    } finally {
        imageUploadInput.value = ''; 
    }
}
function renderImagePreview(file, serverPath) {
    const reader = new FileReader();
    reader.onload = (e) => {
        const itemDiv = document.createElement('div'); itemDiv.className = 'image-preview-item';
        itemDiv.dataset.serverPath = serverPath; 
        const img = document.createElement('img'); img.src = e.target.result;
        const removeBtn = document.createElement('button'); removeBtn.className = 'remove-preview-btn';
        removeBtn.textContent = '×';
        removeBtn.title = translate('remove_image_preview_tooltip');
        removeBtn.onclick = () => {
            uploadedImageServerPaths = uploadedImageServerPaths.filter(p => p.server_path !== serverPath);
            itemDiv.remove();
            if (imageUploadPreviewContainer.children.length === 0) imageUploadPreviewContainer.style.display = 'none';
            sendMessageBtn.disabled = !(messageInput.value.trim() || uploadedImageServerPaths.length > 0) || generationInProgress;
        };
        itemDiv.appendChild(img); itemDiv.appendChild(removeBtn);
        imageUploadPreviewContainer.appendChild(itemDiv);
    };
    reader.readAsDataURL(file);
}
function viewImage(src) {
    imageViewerSrc.src = src;
    openModal('imageViewerModal');
}

// --- Export / Import Logic ---
function populateExportModal() { 
    exportDiscussionList.innerHTML = '';
    const sortedDiscussions = Object.values(discussions).sort((a,b) => (a.title || '').localeCompare(b.title || ''));
    if (sortedDiscussions.length === 0) { exportDiscussionList.innerHTML = `<p class="text-gray-500 italic">${translate('export_no_discussions')}</p>`; return; }
    sortedDiscussions.forEach(d => {
        const div = document.createElement('div'); div.className = 'flex items-center';
        const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.id = `export-check-${d.id}`; checkbox.value = d.id; checkbox.className = 'h-4 w-4 mr-2 rounded border-gray-600 text-blue-500 bg-gray-700 shadow-sm focus:border-blue-500 focus:ring-2 focus:ring-offset-0 focus:ring-blue-500 focus:ring-opacity-50';
        const label = document.createElement('label'); label.htmlFor = `export-check-${d.id}`; label.textContent = `${d.title || translate('untitled_discussion_placeholder')} (ID: ...${d.id.slice(-6)})`; label.className = 'text-sm text-gray-300';
        div.appendChild(checkbox); div.appendChild(label); exportDiscussionList.appendChild(div);
    });
}
exportDataBtn.onclick = () => openModal('exportModal');
confirmExportBtn.onclick = async () => { 
    const selectedIds = Array.from(exportDiscussionList.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.value); closeModal('exportModal'); showStatus(translate('status_exporting_data', 'Exporting data...'), 'info');
    try {
            const requestBody = { discussion_ids: selectedIds.length > 0 ? selectedIds : null };
            const response = await apiRequest('/api/discussions/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(requestBody) });
            const exportData = await response.json(); const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob);
            const a = document.createElement('a'); a.href = url; const timestamp = new Date().toISOString().replace(/[:.]/g, '-'); a.download = `simplified_lollms_export_${currentUser.username}_${timestamp}.json`; document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url);
            showStatus(translate('status_data_exported_success', 'Data exported successfully.'), 'success');
    } catch (error) { /* Handled by apiRequest */ }
};
importDataBtn.onclick = () => { 
        importFile.value = ''; importPreviewArea.style.display = 'none'; importDiscussionList.innerHTML = ''; confirmImportBtn.disabled = true; showStatus('', 'info', importStatus); parsedImportData = null; openModal('importModal');
};
let parsedImportData = null; 
importFile.onchange = async () => { 
    const file = importFile.files[0]; parsedImportData = null; importPreviewArea.style.display = 'none'; importDiscussionList.innerHTML = ''; confirmImportBtn.disabled = true; showStatus('', 'info', importStatus); if (!file) return;
    if (file.type !== 'application/json') { showStatus(translate('import_invalid_json_error'), 'error', importStatus); return; }
    showStatus(translate('status_reading_import_file', 'Reading file...'), 'info', importStatus);
    try {
        const content = await file.text(); parsedImportData = JSON.parse(content);
        if (!parsedImportData || !Array.isArray(parsedImportData.discussions)) throw new Error(translate('import_invalid_file_format_error'));
            if (parsedImportData.discussions.length === 0) { importDiscussionList.innerHTML = `<p class="text-gray-500 italic">${translate('import_no_discussions_in_file')}</p>`; confirmImportBtn.disabled = true; }
            else { parsedImportData.discussions.forEach((disc, index) => { if (!disc || typeof disc.discussion_id !== 'string') { return; } const div = document.createElement('div'); div.className = 'flex items-center'; const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.id = `import-check-${disc.discussion_id}`; checkbox.value = disc.discussion_id; checkbox.checked = true; checkbox.className = 'h-4 w-4 mr-2 rounded border-gray-600 text-blue-500 bg-gray-700 shadow-sm focus:border-blue-500 focus:ring-2 focus:ring-offset-0 focus:ring-blue-500 focus:ring-opacity-50'; const label = document.createElement('label'); label.htmlFor = `import-check-${disc.discussion_id}`; label.textContent = `${disc.title || translate('untitled_discussion_placeholder')} (ID: ...${disc.discussion_id.slice(-6)})`; label.className = 'text-sm text-gray-300'; div.appendChild(checkbox); div.appendChild(label); importDiscussionList.appendChild(div); }); confirmImportBtn.disabled = importDiscussionList.childElementCount === 0; }
            importPreviewArea.style.display = 'block'; showStatus('', 'info', importStatus);
    } catch (error) { showStatus(translate('import_error_reading_file', `Error reading file: ${error.message}`, {message: error.message}), 'error', importStatus); parsedImportData = null; confirmImportBtn.disabled = true; }
};
confirmImportBtn.onclick = async () => { 
        if (!parsedImportData || !importFile.files[0]) return;
        const selectedOriginalIds = Array.from(importDiscussionList.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.value); if (selectedOriginalIds.length === 0) { showStatus(translate('import_select_one_discussion_error'), 'error', importStatus); return; }
        showStatus(translate('status_importing_discussions', 'Importing discussions...'), 'info', importStatus); confirmImportBtn.disabled = true;
        try {
        const importRequest = { discussion_ids_to_import: selectedOriginalIds }; const formData = new FormData(); formData.append('import_file', importFile.files[0]); formData.append('import_request_json', JSON.stringify(importRequest));
            const response = await apiRequest('/api/discussions/import', { method: 'POST', body: formData, statusElement: importStatus });
            const result = await response.json(); showStatus(result.message || translate('status_import_count_success', `Imported ${result.imported_count} discussions.`, {count: result.imported_count}), 'success', importStatus);
            await loadDiscussions(); setTimeout(() => closeModal('importModal'), 2000);
        } catch (error) { confirmImportBtn.disabled = false; /* Handled by apiRequest */ }
};

// --- Utilities ---
function scrollChatToBottom() { requestAnimationFrame(() => { if(chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight; }); }
function showStatus(msg, type = 'info', statusElement = statusMessage) {
    const targetElement = statusElement || statusMessage; if (targetElement) { targetElement.textContent = msg; let typeClass = 'text-gray-400'; if (type === 'error') typeClass = 'text-red-400'; else if (type === 'success') typeClass = 'text-green-400'; else if (type === 'warning') typeClass = 'text-yellow-400'; targetElement.className = targetElement.className.replace(/text-(gray|red|green|yellow)-[0-9]{3}/g, ''); targetElement.classList.add(typeClass); if (targetElement === statusMessage && msg) { clearTimeout(targetElement.timer); targetElement.timer = setTimeout(() => { if (targetElement.textContent === msg) targetElement.textContent = ''; }, 5000); } }
}
function populateDropdown(selectElement, items, selectedValue, emptyText = "Nothing found", allowEmpty = false) {
    if (!selectElement) { return; } selectElement.innerHTML = '';
    if (allowEmpty) { const emptyOption = document.createElement('option'); emptyOption.value = ""; emptyOption.textContent = emptyText; selectElement.appendChild(emptyOption); }
    if (!items || !Array.isArray(items) || items.length === 0) { if (!allowEmpty) { const placeholder = document.createElement('option'); placeholder.disabled = true; placeholder.selected = true; placeholder.textContent = emptyText; selectElement.appendChild(placeholder); } }
    else { items.forEach(item => { if (!item || typeof item.name !== 'string') { return; } const option = document.createElement('option'); option.value = item.name; option.textContent = item.method_name || item.name; if (item.name === selectedValue) { option.selected = true; } selectElement.appendChild(option); }); }
}

