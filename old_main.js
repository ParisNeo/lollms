// --- Localization State ---
let currentTranslations = {};
let currentLang = 'en';
let availableLanguages = { 'en': 'English' };

// --- Global State (Additions/Modifications) ---
let currentUser = null;
let currentDiscussionId = null;
let discussions = {}; // Will be enhanced for branching: discussions[id].branches, .activeBranchId
let currentMessages = []; // This will point to messages of the active branch
let aiMessageStreaming = false;
let currentAiMessageDomContainer = null; // Specific DOM element for the current AI message's container
let currentAiMessageDomBubble = null; // Specific DOM element for the current AI message's bubble
let currentAiMessageContentAccumulator = "";
let currentAiMessageId = null;
let currentAiMessageData = null;
let pyodide = null;
let pyodideLoading = false;
let isRagActive = false;
let availableLollmsModels = [];
let availableVectorizers = [];
let userDefaultVectorizer = null;
let ownedDataStores = [];
let sharedDataStores = [];
let availableDataStoresForRag = [];
let uploadedImageServerPaths = [];
let tempLoginUsername = null;
let tempLoginPassword = null;
let generationInProgress = false;
let activeGenerationAbortController = null;
let currentTheme = localStorage.getItem('theme') || 'dark'; // Default to dark, or load preference
let activeBranchId = 'main'; // Default branch ID

// --- DOM Elements ---
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

// --- Localization Functions ---
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

function updateUIText() {
    document.querySelectorAll('[data-translate-key]').forEach(el => {
        const key = el.dataset.translateKey;
        const fallback = el.textContent; 
        if (el.dataset.translateAttr) {
            const attr = el.dataset.translateAttr;
                if (el.tagName === 'INPUT' && attr === 'placeholder' || el.tagName === 'TEXTAREA' && attr === 'placeholder') {
                    el.placeholder = translate(key, el.placeholder);
                } else if (attr === 'title') {
                    el.title = translate(key, el.title);
                } else {
                    el.setAttribute(attr, translate(key, el.getAttribute(attr)));
                }
        } else if (el.dataset.translateAlt) {
                el.alt = translate(key, el.alt);
        }
        else {
            if (el.childNodes.length > 1 && Array.from(el.childNodes).some(n => n.nodeType === Node.ELEMENT_NODE)) {
                const textNode = Array.from(el.childNodes).find(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim() !== '');
                if (textNode) {
                    textNode.textContent = translate(key, fallback);
                } else { 
                    const span = el.querySelector(`span[data-translate-key="${key}"]`);
                    if (span) span.textContent = translate(key, fallback);
                    else el.textContent = translate(key, fallback); 
                }
            } else {
                    el.textContent = translate(key, fallback);
            }
        }
    });
    
    renderDiscussionList(); 
    if (currentDiscussionId && discussions[currentDiscussionId]) { 
        discussionTitle.textContent = discussions[currentDiscussionId].title; 
    } else {
            discussionTitle.textContent = translate('default_discussion_title');
    }
    updateRagToggleButtonState();
    if (currentMessages.length > 0) {
        renderMessages(currentMessages);
    } else if (!currentDiscussionId) {
            chatMessages.innerHTML = `<div class="text-center text-gray-500 italic mt-10">${translate('chat_area_empty_placeholder')}</div>`;
    } else {
            chatMessages.innerHTML = `<p class="text-gray-500 text-center italic mt-10">${translate('chat_area_loading_messages')}</p>`;
    }
}
function updateUIWithTranslations() {
    document.querySelectorAll('[data-translate-key]').forEach(element => {
        const key = element.getAttribute('data-translate-key');
        const fallback = element.dataset.fallback || element.textContent;
        element.textContent = translate(key, fallback);
    });
    const titleElement = document.querySelector('title[data-translate-key]');
    if (titleElement) {
            document.title = translate(titleElement.getAttribute('data-translate-key'), 'App');
    }
}        
async function loadLanguage(langCode) {
    appLoadingStatus.textContent = translate('app_loading_status_loading_language', `Loading ${langCode}...`, {lang_code: langCode});
    try {
        const response = await apiRequest(`/locals/${langCode}.json`);
        currentTranslations = await response.json();
        localStorage.setItem('preferredLang', langCode);
        languageSelector.value = langCode; 
        document.documentElement.lang = langCode.split('-')[0];
        updateUIText();
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
        availableLanguages = { 'en': 'English' };
    }

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
                        return;
                    }
                }
            }
        }
    }
    await loadLanguage(langToLoad); 
}
// --- Helper: Ensure DOM element exists and is in the document ---
function isElementInDocument(element) {
    return element && document.body.contains(element);
}
// --- API Helper ---
async function apiRequest(url, options = {}) {
    if (!options.statusElement) showStatus('');
    const fetchOptions = { ...options };
    fetchOptions.headers = { ...fetchOptions.headers };
    if (tempLoginUsername && tempLoginPassword && !fetchOptions.headers['Authorization']) {
        const basicAuth = btoa(`${tempLoginUsername}:${tempLoginPassword}`);
        fetchOptions.headers['Authorization'] = `Basic ${basicAuth}`;
    }
    if (activeGenerationAbortController && options.method && options.method.toUpperCase() !== 'GET') {
        fetchOptions.signal = activeGenerationAbortController.signal;
    }
    try {
        const response = await fetch(url, fetchOptions);
        if (!response.ok) {
            let errorDetail = `HTTP error ${response.status}`;
            try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) { /* Ignore */ }
            const errorMsg = translate('api_error_prefix', "API Error:") + ` ${errorDetail}`;
            showStatus(errorMsg, "error", options.statusElement || statusMessage);
            const error = new Error(errorMsg); error.status = response.status; throw error;
        }
        if (response.status === 204) return null;
        return response;
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log("API Request Aborted:", url);
            showStatus(translate('api_request_aborted', "Request aborted by user."), "warning", options.statusElement || statusMessage);
        } else {
            console.error("API Request Error:", url, fetchOptions, error);
            if (!error.status) showStatus(translate('api_request_failed_prefix', "Request failed:") + ` ${error.message}`, "error", options.statusElement || statusMessage);
        }
        throw error;
    } finally {
        if (url === '/api/auth/me' && fetchOptions.headers['Authorization'] && fetchOptions.headers['Authorization'].startsWith('Basic')) {
            tempLoginUsername = null; tempLoginPassword = null;
        }
    }
}

// --- Initialization ---
window.onload = async () => {
    marked.setOptions({
        highlight: function(code, lang) {
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
    // Initialize theme toggle button and apply initial theme AFTER DOM is ready
    initializeThemeToggle(); 

    await initializeLocalization(); 
    await attemptInitialAuthAndLoad();
    imageUploadInput.addEventListener('change', handleImageFileSelection);
    
    const settingsTabButtons = document.querySelectorAll('#settingsModal .settings-tab-btn');
    settingsTabButtons.forEach(button => {
        button.addEventListener('click', () => handleSettingsTabSwitch(button.dataset.tab));
    });

    userMenuToggleBtn.addEventListener('click', toggleUserMenu);
    document.addEventListener('click', handleClickOutsideUserMenu);
    discussionSearchInput.addEventListener('input', renderDiscussionList);


};

// --- Theme Management Functions ---
function applyTheme(theme) {
    console.log("Applying theme")
    if (theme === 'dark') {
        console.log("Dark theme")
        document.documentElement.classList.add('dark');
        if (themeIconMoon) themeIconMoon.classList.remove('hidden');
        if (themeIconSun) themeIconSun.classList.add('hidden');
    } else {
        console.log("Light theme")
        document.documentElement.classList.remove('dark');
        if (themeIconSun) themeIconSun.classList.remove('hidden');
        if (themeIconMoon) themeIconMoon.classList.add('hidden');
    }
    localStorage.setItem('theme', theme);
    currentTheme = theme;
    // Potentially dispatch an event or call a function if other parts of the app need to react to theme changes,
    // e.g., if using JS to draw charts that need theme-specific colors.
    // For Tailwind, class changes are enough.
}

function toggleTheme() {
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    applyTheme(newTheme);
}

function initializeThemeToggle() {
    console.log("Initializing theme toggle")
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', toggleTheme);
        console.log("Added click event")
    }
    // Apply the initial theme loaded from localStorage or default
    applyTheme(currentTheme); 
}

async function attemptInitialAuthAndLoad() {
    appLoadingStatus.textContent = translate('app_loading_status_authenticating', "Authenticating...");
    appLoadingProgress.style.width = '10%';
    try {
        const response = await apiRequest('/api/auth/me');
        currentUser = await response.json();
        loginModal.classList.remove('active');
        appContainer.style.display = 'flex';
        appLoadingMessage.style.display = 'none';
        await initializeAppContent();
    } catch (error) {
        if (error.status === 401) {
            appLoadingMessage.style.display = 'none';
            showStatus(translate('login_failed_or_required_status', "Login failed or required."), "error", loginStatus);
            openModal('loginModal', false);
            loginUsernameInput.focus();
        } else {
            appLoadingStatus.textContent = translate('initialization_failed_status', `Initialization failed: ${error.message}. Please refresh.`, { message: error.message });
            appLoadingStatus.classList.add('text-red-600');
        }
    }
}

async function initializeAppContent() {
    appLoadingStatus.textContent = translate('app_loading_status_user_data', "Loading user data...");
    appLoadingProgress.style.width = '25%';
    usernameDisplay.textContent = currentUser.username;
    userDefaultVectorizer = currentUser.safe_store_vectorizer; 

    if (currentUser.is_admin) {
        adminBadge.style.display = 'inline-block';
        adminLink.style.display = 'flex';
    } else {
        adminBadge.style.display = 'none';
        adminLink.style.display = 'none';
    }

    appLoadingStatus.textContent = translate('app_loading_status_discussions_stores', "Loading discussions & data stores...");
    appLoadingProgress.style.width = '50%';
    await Promise.all([
        loadDiscussions(),
        loadDataStores() 
    ]);
    
    appLoadingStatus.textContent = translate('app_loading_status_models_vectorizers', "Loading models and vectorizers...");
    appLoadingProgress.style.width = '75%';
    await loadAvailableLollmsModels(); 
    appLoadingProgress.style.width = '90%';

    updateRagToggleButtonState(); 
    appLoadingProgress.style.width = '100%';
    setTimeout(() => {
        appLoadingMessage.style.opacity = '0';
        setTimeout(() => appLoadingMessage.style.display = 'none', 300);
    }, 500);


    confirmRenameBtn.onclick = confirmInlineRename;
    confirmSendDiscussionBtn.onclick = confirmSendDiscussion;
    confirmEditMessageBtn.onclick = confirmMessageEdit;
    logoutBtn.onclick = handleLogout;
    loginSubmitBtn.onclick = handleLoginAttempt;
    loginPasswordInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') handleLoginAttempt(); });
    
    createDataStoreForm.addEventListener('submit', handleCreateDataStore);
    changePasswordBtn.onclick = handleChangePassword;
    const sidebarLogoutBtn = document.getElementById('sidebarLogoutBtn');
    if (sidebarLogoutBtn) {
        sidebarLogoutBtn.onclick = handleLogout;
    }
    showStatus(translate('status_ready', 'Ready.'), 'success');
    updateUIText(); 
}

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
        const loadedDiscussions = await response.json();
        discussions = {}; 
        loadedDiscussions.forEach(d => {
            discussions[d.id] = { 
                id: d.id, title: d.title, is_starred: d.is_starred,
                rag_datastore_id: d.rag_datastore_id, messages_loaded_fully: false,
                last_activity_at: d.last_activity_at || d.created_at || `1970-01-01T00:00:00Z`
            };
        });
        renderDiscussionList();
        if (currentDiscussionId && discussions[currentDiscussionId]) {
            selectDiscussion(currentDiscussionId); 
        } else if (currentDiscussionId) { 
            clearChatArea(); currentDiscussionId = null;
        }
    } catch (error) {
        discussionListContainer.innerHTML = `<p class="text-red-500 text-sm text-center p-4">${translate('failed_to_load_discussions_error')}</p>`;
    }
}

function createDiscussionItemElement(d) {
    const item = document.createElement('div');
    item.className = `discussion-item p-2.5 rounded-lg cursor-pointer hover:bg-gray-700 flex justify-between items-center text-sm transition-colors duration-150 ${d.id === currentDiscussionId ? 'bg-blue-700 font-medium text-blue-100 hover:bg-blue-600' : 'text-gray-300 hover:text-gray-100'}`;
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
    deleteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="text-red-400 hover:text-red-300"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12.508 0A48.067 48.067 0 0 1 7.8 5.397m7.454 0M12 10.75h.008v.008H12v-.008Z" /></svg>`;
    deleteBtn.title = translate('delete_discussion_tooltip'); deleteBtn.className = 'discussion-action-btn';
    deleteBtn.onclick = (e) => { e.stopPropagation(); deleteInlineDiscussion(d.id); };
    actionsContainer.appendChild(deleteBtn);
    
    const starSpan = document.createElement('button');
    starSpan.className = 'discussion-action-btn p-1 ml-1'; 
    starSpan.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="${d.is_starred ? 'currentColor' : 'none'}" viewBox="0 0 24 24" stroke-width="1.5" stroke="${d.is_starred ? 'none' : 'currentColor'}" class="w-4 h-4 star-icon ${d.is_starred ? 'starred' : ''} transition-colors duration-150"><path stroke-linecap="round" stroke-linejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 21.1a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" /></svg>`;
    starSpan.title = d.is_starred ? translate('unstar_discussion_tooltip') : translate('star_discussion_tooltip');
    starSpan.onclick = (e) => { e.stopPropagation(); toggleStarDiscussion(d.id, d.is_starred); };
    
    controlsDiv.appendChild(actionsContainer);
    controlsDiv.appendChild(starSpan);  

    item.appendChild(titleSpan);
    item.appendChild(controlsDiv);
    return item;
}

function renderDiscussionList() {
    discussionListContainer.innerHTML = ''; 
    const searchTerm = discussionSearchInput.value.toLowerCase();
    const allDiscussionValues = Object.values(discussions);
    const filteredDiscussions = searchTerm 
        ? allDiscussionValues.filter(d => (d.title || '').toLowerCase().includes(searchTerm))
        : allDiscussionValues;

    const starredDiscussions = filteredDiscussions.filter(d => d.is_starred);
    const regularDiscussions = filteredDiscussions.filter(d => !d.is_starred);
    const sortByDateDesc = (a, b) => (new Date(b.last_activity_at || 0) - new Date(a.last_activity_at || 0)) || (a.title || '').localeCompare(b.title || '');
    
    starredDiscussions.sort(sortByDateDesc);
    regularDiscussions.sort(sortByDateDesc);

    if (filteredDiscussions.length === 0) {
        discussionListContainer.innerHTML = `<p class="text-gray-500 text-sm text-center italic p-4">${searchTerm ? translate('no_discussions_match_search') : translate('no_discussions_yet')}</p>`;
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
        starredListDiv.className = 'space-y-1';
        starredDiscussions.forEach(d => starredListDiv.appendChild(createDiscussionItemElement(d)));
        starredSection.appendChild(starredListDiv);
        discussionListContainer.appendChild(starredSection);
    } else if (searchTerm && allDiscussionValues.some(d => d.is_starred)) {
        const starredSection = document.createElement('div');
        const starredHeader = document.createElement('h3');
        starredHeader.className = 'discussion-section-header';
        starredHeader.textContent = translate('discussion_section_starred');
        starredSection.appendChild(starredHeader);
        starredSection.innerHTML += `<p class="text-gray-500 text-xs text-center italic p-2">${translate('no_starred_discussions_match_search')}</p>`;
        discussionListContainer.appendChild(starredSection);
    }

    const regularSection = document.createElement('div');
    regularSection.id = 'regularDiscussionsSection';
    if (starredDiscussions.length > 0) regularSection.classList.add('mt-3'); 

    const regularHeader = document.createElement('h3');
    regularHeader.className = 'discussion-section-header';
    regularHeader.textContent = translate('discussion_section_recent');
    regularSection.appendChild(regularHeader);

    const regularListDiv = document.createElement('div');
    regularListDiv.className = 'space-y-1';
    if (regularDiscussions.length > 0) {
        regularDiscussions.forEach(d => regularListDiv.appendChild(createDiscussionItemElement(d)));
    } else {
            regularListDiv.innerHTML = `<p class="text-gray-500 text-xs text-center italic p-2">${searchTerm ? translate('no_other_discussions_match_search') : translate('no_other_discussions')}</p>`;
    }
    regularSection.appendChild(regularListDiv);
    discussionListContainer.appendChild(regularSection);
}

newDiscussionBtn.onclick = async () => {
    showStatus(translate('status_creating_discussion', 'Creating new discussion...'), 'info');
    try {
        const response = await apiRequest('/api/discussions', { method: 'POST' });
        const newDiscussion = await response.json();
        discussions[newDiscussion.id] = { 
            id: newDiscussion.id, title: newDiscussion.title, is_starred: newDiscussion.is_starred,
            rag_datastore_id: newDiscussion.rag_datastore_id, messages_loaded_fully: true,
            last_activity_at: newDiscussion.last_activity_at || newDiscussion.created_at || new Date().toISOString()
        };
        renderDiscussionList();
        selectDiscussion(newDiscussion.id);
        showStatus(translate('status_new_discussion_created', 'New discussion created.'), 'success');
    } catch (error) { /* Handled by apiRequest */ }
};
async function selectDiscussion(id) {
    if (!discussions[id] || aiMessageStreaming) return;
    currentDiscussionId = id;
    const discussionData = discussions[id];
    discussionTitle.textContent = discussionData.title;
    sendMessageBtn.disabled = false;
    renderDiscussionList(); 
    clearChatArea(false);
    chatMessages.innerHTML = `<p class="text-gray-500 text-center italic mt-10">${translate('chat_area_loading_messages')}</p>`;
    
    isRagActive = discussionData.rag_datastore_id !== null && discussionData.rag_datastore_id !== "";
    updateRagToggleButtonState(); 
    if(isRagActive && discussionData.rag_datastore_id) {
        ragDataStoreSelect.value = discussionData.rag_datastore_id;
    } else if (availableDataStoresForRag.length > 0) { 
        ragDataStoreSelect.value = ""; 
    }

    try {
        const response = await apiRequest(`/api/discussions/${id}`);
        const loadedMessages = await response.json();
        currentMessages = loadedMessages;
        discussions[id].messages_loaded_fully = true;
        
        if (loadedMessages.length > 0) {
            const lastMessage = loadedMessages[loadedMessages.length -1];
            if (lastMessage.created_at && new Date(lastMessage.created_at) > new Date(discussions[id].last_activity_at || 0)) {
                discussions[id].last_activity_at = lastMessage.created_at;
                renderDiscussionList(); 
            }
        }
        renderMessages(currentMessages);
    } catch (error) {
            chatMessages.innerHTML = `<p class="text-red-500 text-center mt-10">${translate('chat_area_error_loading_messages')}</p>`;
    }
}
function initiateInlineRename(id) {
    if (!discussions[id]) return;
    renameDiscussionIdInput.value = id; renameInput.value = discussions[id].title;
    showStatus('', 'info', renameStatus); openModal('renameModal');
}
async function confirmInlineRename() {
        const idToRename = renameDiscussionIdInput.value; if (!idToRename || !discussions[idToRename]) return;
        const newTitle = renameInput.value.trim(); if (!newTitle) { showStatus(translate('rename_title_empty_error'), 'error', renameStatus); return; }
        showStatus(translate('status_renaming', 'Renaming...'), 'info', renameStatus);
        try {
            const response = await apiRequest(`/api/discussions/${idToRename}/title`, {
                method: 'PUT', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: newTitle }), statusElement: renameStatus
            });
            const updatedInfo = await response.json();
            discussions[idToRename].title = updatedInfo.title;
            discussions[idToRename].last_activity_at = updatedInfo.last_activity_at || new Date().toISOString();
            if (idToRename === currentDiscussionId) discussionTitle.textContent = updatedInfo.title;
            renderDiscussionList(); showStatus(translate('status_renamed_success', 'Renamed successfully.'), 'success', renameStatus);
            setTimeout(() => closeModal('renameModal'), 1000);
        } catch (error) { /* Handled by apiRequest */ }
}
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
messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    autoGrowTextarea(messageInput);
});
messageInput.addEventListener('input', () => {
    autoGrowTextarea(messageInput);
    sendMessageBtn.disabled = !(messageInput.value.trim() || uploadedImageServerPaths.length > 0) || generationInProgress;
});
sendMessageBtn.onclick = sendMessage;
stopGenerationBtn.onclick = stopGeneration;

function autoGrowTextarea(element) { 
    element.style.height = 'auto'; const maxHeight = 200;
    element.style.height = Math.min(element.scrollHeight, maxHeight) + 'px';
    element.style.overflowY = element.scrollHeight > maxHeight ? 'auto' : 'hidden';
}
       
async function sendMessage() {
    console.log("sendMessage: Entered");
    if (generationInProgress || !currentDiscussionId) {
        console.log("sendMessage: Exiting - generation in progress or no current discussion.");
        return;
    }
    const prompt = messageInput.value.trim();
    if (!prompt && uploadedImageServerPaths.length === 0) {
        console.log("sendMessage: Exiting - empty prompt and no images.");
        return;
    }

    generationInProgress = true;
    console.log("sendMessage: generationInProgress set to true");
    activeGenerationAbortController = new AbortController();
    sendMessageBtn.style.display = 'none';
    stopGenerationBtn.style.display = 'inline-flex';
    stopGenerationBtn.disabled = false;
    console.log("sendMessage: UI buttons updated for sending");

    const tempUserMessageId = `temp-user-${Date.now()}`;
    const userMessageData = {
        id: tempUserMessageId,
        sender: translate(currentUser.lollms_client_ai_name ? 'sender_you' : (currentUser.username || 'sender_user'), 'User'),
        content: prompt, user_grade: 0, token_count: null, model_name: null,
        image_references: uploadedImageServerPaths.map(img => URL.createObjectURL(img.file_obj)),
        steps: [], metadata: [], created_at: new Date().toISOString() // Add created_at for consistency
    };
    currentMessages.push(userMessageData);
    console.log("sendMessage: User message pushed to currentMessages");
    try {
        renderMessage(userMessageData);
        console.log("sendMessage: User message rendered");
    } catch (e) {
        console.error("sendMessage: Error rendering user message:", e);
        generationInProgress = false; 
        return;
    }

    const formData = new FormData();
    formData.append('prompt', prompt);
    formData.append('image_server_paths_json', JSON.stringify(uploadedImageServerPaths.map(img => img.server_path)));
    formData.append('use_rag', isRagActive);
    if(isRagActive && discussions[currentDiscussionId] && discussions[currentDiscussionId].rag_datastore_id) {
        formData.append('rag_datastore_id', discussions[currentDiscussionId].rag_datastore_id);
    }
    // console.log("sendMessage: FormData prepared:", Array.from(formData.keys())); // Keep this concise

    messageInput.value = ''; uploadedImageServerPaths = [];
    imageUploadPreviewContainer.innerHTML = ''; imageUploadPreviewContainer.style.display = 'none';
    autoGrowTextarea(messageInput);
    scrollChatToBottom();
    console.log("sendMessage: Input cleared, scrolled to bottom");

    aiMessageStreaming = true;
    currentAiMessageContentAccumulator = "";
    currentAiMessageContainer = null; // Will be set by renderMessage
    currentAiMessageId = `temp-ai-${Date.now()}`;
    currentAiMessageData = {
        id: currentAiMessageId, sender: currentUser.lollms_client_ai_name || translate('sender_assistant', 'Assistant'),
        content: "", user_grade: 0, token_count: null, model_name: null,
        image_references: [], steps: [], metadata: [], created_at: new Date().toISOString() // Add created_at
    };
    currentMessages.push(currentAiMessageData);
    console.log("sendMessage: AI message placeholder pushed to currentMessages");
    try {
        renderMessage(currentAiMessageData); 
        console.log("sendMessage: AI message placeholder rendered successfully.");
    } catch (e) {
        console.error("sendMessage: Error rendering AI placeholder message:", e);
        generationInProgress = false; 
        aiMessageStreaming = false;
        return;
    }

    if (discussions[currentDiscussionId]) {
        discussions[currentDiscussionId].last_activity_at = new Date().toISOString();
        renderDiscussionList();
        console.log("sendMessage: Discussion activity updated and list re-rendered");
    } else {
        console.warn("sendMessage: currentDiscussionId not found in discussions object before fetch.");
        // Handle this case - maybe re-fetch discussions or show an error.
        // For now, we'll proceed, but this is a potential issue.
    }

    // --- Fetch and Streaming Logic ---
    try {
        console.log(`sendMessage: Attempting fetch to /api/discussions/${currentDiscussionId}/chat`);
        const response = await fetch(`/api/discussions/${currentDiscussionId}/chat`, {
            method: 'POST',
            body: formData,
            signal: activeGenerationAbortController.signal
        });
        console.log("sendMessage: Fetch response received, status:", response.status);

        if (!response.ok || !response.body) {
            let errorDetailMessage = `HTTP error ${response.status}`;
            try {
                const errorData = await response.json(); errorDetailMessage = errorData.detail || errorDetailMessage;
                console.error("sendMessage: Fetch error data:", errorData);
            } catch (e) {
                console.error("sendMessage: Could not parse error response JSON", e);
                try { const errorText = await response.text(); errorDetailMessage = errorText || errorDetailMessage; console.error("sendMessage: Fetch error text:", errorText);
                } catch (textErr) { console.error("sendMessage: Could not get error response text", textErr); }
            }
            throw new Error(translate('chat_stream_start_error', `Error starting chat stream: ${errorDetailMessage}`, { detail: errorDetailMessage }));
        }

        const reader = response.body.getReader(); const decoder = new TextDecoder();
        console.log("sendMessage: Streaming started...");
        while (true) {
            if (!generationInProgress) { console.log("sendMessage: Loop check - generationInProgress is false, cancelling reader."); if (reader.cancel) await reader.cancel('User requested stop early in loop'); break; }
            // console.log("sendMessage: Awaiting reader.read()"); // Can be too verbose
            const { done, value } = await reader.read();
            // console.log("sendMessage: reader.read() done:", done); // Can be too verbose

            if (done) { console.log("sendMessage: Stream finished (done is true)."); break; }
            if (!generationInProgress) { console.log("sendMessage: Loop check after read - generationInProgress is false, cancelling reader."); if (reader.cancel) await reader.cancel('User requested stop after read'); break; }

            const textChunk = decoder.decode(value, { stream: true });
            const lines = textChunk.split('\n').filter(line => line.trim() !== '');
            lines.forEach(line => {
                try { handleStreamChunk(JSON.parse(line));
                } catch (e) { console.error("sendMessage: Error parsing stream line:", line, e); renderMessage({ id: `warn-${Date.now()}`, sender: 'system', content: translate('malformed_data_chunk_error'), steps:[], metadata:[] }); }
            });
        }
        if (generationInProgress) { console.log("sendMessage: Stream loop finished, calling handleStreamEnd."); handleStreamEnd();
        } else { console.log("sendMessage: Stream loop exited because generationInProgress was false."); }
    } catch (error) {
        console.error("sendMessage: Outer catch block error:", error);
        if (error.name === 'AbortError') { showStatus(translate('status_generation_cancelled_by_user', 'Generation cancelled by user.'), 'info');
        } else {
            showStatus(translate('chat_stream_failed_error', `Chat stream failed: ${error.message}`, {message: error.message}), "error");
            renderMessage({ id: `err-${Date.now()}`, sender: 'system', content: translate('stream_error_prefix', `Stream Error: ${error.message}`, {message: error.message}), steps:[], metadata:[] });
        }
        if (generationInProgress) { handleStreamEnd(true); }
    } finally {
        console.log("sendMessage: Finally block executing.");
        if (generationInProgress) { console.warn("sendMessage: generationInProgress was still true in finally, resetting."); generationInProgress = false; }
        sendMessageBtn.style.display = 'inline-flex'; stopGenerationBtn.style.display = 'none';
        sendMessageBtn.disabled = !(messageInput.value.trim() || uploadedImageServerPaths.length > 0); 
        activeGenerationAbortController = null; 
        console.log("sendMessage: Exiting finally block.");
    }
}


function renderMessage(message) {
    // console.log("renderMessage: Called for message ID:", message.id, "Sender:", message.sender);
    if (!message || typeof message.sender === 'undefined' || (typeof message.content === 'undefined' && (!message.image_references || message.image_references.length === 0) && (!message.steps || message.steps.length === 0) && (!message.metadata || message.metadata.length === 0))) {
        // console.warn("renderMessage: Skipping invalid or truly empty message object:", message);
        return;
    }
    const messageId = message.id || `temp-render-${Date.now()}`;
    const domId = `message-${messageId}`; 

    let messageContainer = document.querySelector(`.message-container[data-message-id="${messageId}"]`);
    let bubbleDiv;

    if (messageContainer) {
        // console.log("renderMessage: Updating existing container for ID:", messageId);
        bubbleDiv = messageContainer.querySelector('.message-bubble');
        if (!bubbleDiv) {
            console.error("renderMessage: Container found but bubble missing for ID:", messageId, ". Recreating bubble.");
            messageContainer.innerHTML = ''; 
            bubbleDiv = document.createElement('div');
            bubbleDiv.id = domId; 
            messageContainer.appendChild(bubbleDiv);
        } else {
            const senderNameEl = bubbleDiv.querySelector('.sender-name');
            const imagesContEl = bubbleDiv.querySelector('.message-images-container');
            const contentEl = bubbleDiv.querySelector('.message-content');
            const footerEl = bubbleDiv.querySelector('.message-footer');
            const actionsContEl = bubbleDiv.querySelector('.message-actions-container');

            if (senderNameEl) senderNameEl.remove();
            if (imagesContEl) imagesContEl.remove();
            if (contentEl) contentEl.innerHTML = ''; 
            else {
                const newContentDiv = document.createElement('div');
                newContentDiv.className = 'message-content prose prose-sm max-w-none prose-invert prose-code:before:content-none prose-code:after:content-none prose-code:font-normal prose-code:bg-gray-700 prose-code:text-gray-100 prose-code:px-1 prose-code:py-0.5 prose-code:rounded';
                bubbleDiv.appendChild(newContentDiv);
            }
            if (footerEl) footerEl.innerHTML = ''; 
            else {
                const newFooterDiv = document.createElement('div');
                newFooterDiv.className = 'message-footer';
                bubbleDiv.appendChild(newFooterDiv);
            }
            if (actionsContEl) actionsContEl.innerHTML = '';
            else {
                const newActionsContainer = document.createElement('div');
                newActionsContainer.className = 'message-actions-container';
                bubbleDiv.appendChild(newActionsContainer);
            }
        }
    } else {
        // console.log("renderMessage: Creating new container for ID:", messageId);
        messageContainer = document.createElement('div');
        messageContainer.className = 'message-container flex flex-col';
        messageContainer.dataset.messageId = messageId; 

        bubbleDiv = document.createElement('div');
        bubbleDiv.id = domId; 
        messageContainer.appendChild(bubbleDiv);
        chatMessages.appendChild(messageContainer);
    }

    if (message.addSpacing && messageContainer.previousElementSibling) {
        messageContainer.classList.add('mt-3');
    } else {
        messageContainer.classList.remove('mt-3');
    }

    let bubbleClass = 'ai-bubble';
    let senderNameText = message.sender;
    let showGrade = false;
    const userNames = [currentUser.username, 'user', 'You', translate('sender_you', 'You'), translate('sender_user', 'User'), currentUser.lollms_client_ai_name ? null : currentUser.username];

    if (userNames.includes(senderNameText) || (message.sender === "User" && currentUser.username === "user")) {
        bubbleClass = 'user-bubble'; senderNameText = '';
    } else if (senderNameText && (senderNameText.toLowerCase() === 'system' || senderNameText.toLowerCase() === 'error')) {
        bubbleClass = 'system-bubble'; senderNameText = '';
    } else {
        bubbleClass = 'ai-bubble';
        senderNameText = currentUser.lollms_client_ai_name || message.sender || translate('sender_assistant', 'Assistant');
        showGrade = !messageId.startsWith('temp-');
    }
    bubbleDiv.className = `message-bubble ${bubbleClass}`; 

    let senderDiv = bubbleDiv.querySelector('.sender-name'); 
    if (senderNameText) {
        if (!senderDiv) { senderDiv = document.createElement('div'); senderDiv.className = 'sender-name'; bubbleDiv.insertBefore(senderDiv, bubbleDiv.firstChild); }
        senderDiv.textContent = senderNameText;
    }

    let imagesContainer = bubbleDiv.querySelector('.message-images-container');
    if (message.image_references && message.image_references.length > 0) {
        if (!imagesContainer) {
            imagesContainer = document.createElement('div'); imagesContainer.className = 'message-images-container';
            const targetNodeForImages = senderDiv ? senderDiv.nextSibling : bubbleDiv.firstChild;
            bubbleDiv.insertBefore(imagesContainer, targetNodeForImages);
        }
        imagesContainer.innerHTML = ''; 
        message.image_references.forEach(imgSrc => {
            const imgItem = document.createElement('div'); imgItem.className = 'message-image-item';
            const imgTag = document.createElement('img'); imgTag.src = imgSrc; imgTag.alt = translate('chat_image_alt', 'Chat Image');
            imgTag.onclick = () => viewImage(imgSrc);
            imgItem.appendChild(imgTag); imagesContainer.appendChild(imgItem);
        });
    }

    let contentDiv = bubbleDiv.querySelector('.message-content');
    if (!contentDiv) { 
        contentDiv = document.createElement('div');
        contentDiv.className = 'message-content prose prose-sm max-w-none prose-invert prose-code:before:content-none prose-code:after:content-none prose-code:font-normal prose-code:bg-gray-700 prose-code:text-gray-100 prose-code:px-1 prose-code:py-0.5 prose-code:rounded';
        const targetNodeForContent = imagesContainer ? imagesContainer.nextSibling : (senderDiv ? senderDiv.nextSibling : bubbleDiv.firstChild);
        bubbleDiv.insertBefore(contentDiv, targetNodeForContent);
    }
    
    // console.log("renderMessage: Preparing to call renderProcessedContent for ID:", messageId, "Content length:", (message.content || "").length);
    if (message.content || (aiMessageStreaming && messageId === currentAiMessageId) || (message.steps && message.steps.length > 0) || (message.metadata && message.metadata.length > 0)) {
        renderProcessedContent(contentDiv, message.content || "", messageId, message.steps, message.metadata, message); 
        if (messageId === currentAiMessageId && (aiMessageStreaming || generationInProgress)) {
             currentAiMessageContainer = messageContainer; 
        }
    } else if ((!message.image_references || message.image_references.length === 0)) {
        contentDiv.innerHTML = `<p class="italic text-gray-500">${translate('empty_message_placeholder')}</p>`;
    } else {
        contentDiv.innerHTML = '';
    }
    // console.log("renderMessage: Finished renderProcessedContent for ID:", messageId);


    let footerDiv = bubbleDiv.querySelector('.message-footer');
    if (!footerDiv) { footerDiv = document.createElement('div'); footerDiv.className = 'message-footer'; bubbleDiv.appendChild(footerDiv); }
    footerDiv.innerHTML = ''; 
    
    const detailsSpan = document.createElement('span'); detailsSpan.className = 'message-details';
    let detailsContent = '';
    if (message.token_count) detailsContent += `<span>${translate('tokens_label', 'Tokens:')} ${message.token_count}</span>`;
    if (message.model_name) detailsContent += `<span>${translate('model_label', 'Model:')} ${message.model_name}</span>`;
    detailsSpan.innerHTML = detailsContent;
    

    let actionsContainer = bubbleDiv.querySelector('.message-actions-container');
    if(!actionsContainer){ actionsContainer = document.createElement('div'); actionsContainer.className = 'message-actions-container'; bubbleDiv.appendChild(actionsContainer); }
    actionsContainer.innerHTML = '';

    const actionsSpan = document.createElement('span'); actionsSpan.className = 'message-actions items-center'; 
    if (!messageId.startsWith('temp-')) {
        const copyBtn = document.createElement('button');
        copyBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M15.666 3.888A2.25 2.25 0 0 0 13.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 0 1-.75.75H9a.75.75 0 0 1-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 0 1-2.25 2.25H6.75A2.25 2.25 0 0 1 4.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 0 1 1.927-.184" /></svg>`;
        copyBtn.title = translate('copy_content_tooltip'); copyBtn.className = 'message-action-btn';
        copyBtn.onclick = () => { navigator.clipboard.writeText(message.content || "").then(() => showStatus(translate('status_content_copied', "Content copied!"), "success")).catch(err => showStatus(translate('status_copy_failed', "Copy failed."), "error")); };
        actionsSpan.appendChild(copyBtn);

        const editBtn = document.createElement('button');
        editBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" /></svg>`;
        editBtn.title = translate('edit_message_tooltip'); editBtn.className = 'message-action-btn';
        editBtn.onclick = () => initiateEditMessage(messageId);
        actionsSpan.appendChild(editBtn);

        const deleteBtn = document.createElement('button');
        deleteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="text-red-400 hover:text-red-300"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12.508 0A48.067 48.067 0 0 1 7.8 5.397m7.454 0M12 10.75h.008v.008H12v-.008Z" /></svg>`;
        deleteBtn.title = translate('delete_message_tooltip'); deleteBtn.className = 'message-action-btn';
        deleteBtn.onclick = () => deleteMessage(messageId);
        actionsSpan.appendChild(deleteBtn);
    }
    actionsContainer.appendChild(actionsSpan); 

    const gradeSpanContainer = document.createElement('span');
    gradeSpanContainer.className = 'flex items-center justify-end ml-auto'; 
    if (showGrade) {
        const userGrade = message.user_grade || 0;
        const upvoteBtn = document.createElement('button'); upvoteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 15l7-7 7 7" /></svg>`;
        upvoteBtn.title = translate('grade_good_tooltip'); upvoteBtn.className = `grade-btn ${userGrade > 0 ? 'selected-up' : ''} p-1 rounded hover:bg-gray-700`;
        upvoteBtn.onclick = () => gradeMessage(messageId, 1);
        const gradeDisplaySpan = document.createElement('span'); gradeDisplaySpan.className = 'grade-score font-medium'; gradeDisplaySpan.textContent = userGrade;
        const downvoteBtn = document.createElement('button'); downvoteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" /></svg>`;
        downvoteBtn.title = translate('grade_bad_tooltip'); downvoteBtn.className = `grade-btn ${userGrade < 0 ? 'selected-down' : ''} p-1 rounded hover:bg-gray-700`;
        downvoteBtn.onclick = () => gradeMessage(messageId, -1);
        gradeSpanContainer.appendChild(upvoteBtn); gradeSpanContainer.appendChild(gradeDisplaySpan); gradeSpanContainer.appendChild(downvoteBtn);
    }
    
    const footerFlexContainer = document.createElement('div');
    footerFlexContainer.className = 'flex justify-between items-center w-full';
    footerFlexContainer.appendChild(detailsSpan); 

    const rightFooterControls = document.createElement('div');
    rightFooterControls.className = 'flex items-center gap-2'; 
    rightFooterControls.appendChild(gradeSpanContainer);

    footerFlexContainer.appendChild(rightFooterControls);
    footerDiv.appendChild(footerFlexContainer);
    // console.log("renderMessage: Message structure built for ID:", messageId);
}
async function stopGeneration() {
    if (!generationInProgress || !currentDiscussionId) return;
    
    stopGenerationBtn.disabled = true; 
    showStatus(translate('status_stopping_generation', 'Attempting to stop generation...'), 'info');

    if (activeGenerationAbortController) {
        activeGenerationAbortController.abort(); // Signal the fetch to abort
    }
    generationInProgress = false; // Set this immediately

    try {
        const response = await apiRequest(`/api/discussions/${currentDiscussionId}/stop_generation`, {
            method: 'POST'
        });
        const result = await response.json();
        showStatus(result.message, 'info'); 
    } catch (error) {
        showStatus(translate('status_stop_signal_failed', `Failed to send stop signal: ${error.message}`, {message: error.message}), 'error');
    } finally {
        // Ensure UI is reset regardless of API call success for stop_generation endpoint
        // because the client-side generationInProgress is already false.
        aiMessageStreaming = false;
        sendMessageBtn.style.display = 'inline-flex';
        stopGenerationBtn.style.display = 'none';
        stopGenerationBtn.disabled = false;
        sendMessageBtn.disabled = !(messageInput.value.trim() || uploadedImageServerPaths.length > 0);

        // If there's an AI message being built, finalize it.
        if (currentAiMessageContainer && currentAiMessageData) {
             // No new content, but ensure its state is 'stopped' or similar if backend implies it
             currentAiMessageData.steps = currentAiMessageData.steps || [];
             currentAiMessageData.steps.push({text: translate('step_generation_stopped_by_user', "Generation stopped by user."), done:false, status: 'stopped'});
             renderMessage(currentAiMessageData); // Re-render to show final state
        }
        currentAiMessageContainer = null;
        currentAiMessageContentAccumulator = "";
        currentAiMessageData = null;

        refreshMessagesAfterStream(); // Get the definitive state from backend
        scrollChatToBottom();
    }
}

function handleStreamChunk(data) {
        if (!generationInProgress && data.type !== 'info') return; 

        if (!currentAiMessageContainer && currentAiMessageData) {
           renderMessage(currentAiMessageData); 
           currentAiMessageContainer = document.getElementById(`message-${currentAiMessageId}`);
        }
        
        if (!currentAiMessageContainer || !currentAiMessageData) return;

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
            renderMessage({ id: `err-${Date.now()}`, sender: 'system', content: translate('llm_error_prefix', `LLM Error: ${data.content}`, {content: data.content}), steps:[], metadata:[] });
            handleStreamEnd(true); return;
        } else if (data.type === 'info' && data.content === "Generation stopped by user.") {
            showStatus(translate('status_generation_stopped_by_user', 'Generation stopped by user.'), 'info');
            // The stream will end shortly after this.
            // generationInProgress might already be false if stopGeneration was very fast.
            // No immediate rerender needed here, handleStreamEnd will manage.
            return; // Avoid further processing for this specific info message
        }

        if (needsRerender) {
            renderMessage(currentAiMessageData);
            scrollChatToBottom();
        }
}
function handleStreamEnd(errorOccurred = false) { 
    const wasManuallyStopped = !generationInProgress && !errorOccurred; 

    aiMessageStreaming = false; 
    generationInProgress = false; 
    activeGenerationAbortController = null;

    sendMessageBtn.style.display = 'inline-flex'; 
    stopGenerationBtn.style.display = 'none'; 
    stopGenerationBtn.disabled = false; 
    sendMessageBtn.disabled = !(messageInput.value.trim() || uploadedImageServerPaths.length > 0);
    
    if (currentAiMessageData && currentAiMessageContainer) {
        if (errorOccurred && !currentAiMessageData.steps.some(s=>s.text.toLowerCase().includes('error'))) {
             currentAiMessageData.steps = currentAiMessageData.steps || [];
             currentAiMessageData.steps.push({text: translate('step_error_occurred', "An error occurred during generation."), done:false, status: 'error'});
             renderMessage(currentAiMessageData); // Re-render with error step
        } else if (wasManuallyStopped && !currentAiMessageData.steps.some(s=>s.text.toLowerCase().includes('stopped'))) {
             currentAiMessageData.steps = currentAiMessageData.steps || [];
             currentAiMessageData.steps.push({text: translate('step_generation_stopped_by_user', "Generation stopped by user."), done:false, status: 'stopped'});
             renderMessage(currentAiMessageData);
        }
    }
    
    currentAiMessageContainer = null;
    currentAiMessageContentAccumulator = "";
    currentAiMessageData = null;

    if (currentDiscussionId) {
        if (!wasManuallyStopped || errorOccurred) {
            refreshMessagesAfterStream();
        }
    }
    scrollChatToBottom();

    if (wasManuallyStopped) {
        showStatus(translate('status_generation_process_halted', 'Generation process halted.'), 'info');
    }
}        
async function refreshMessagesAfterStream() {
    await new Promise(resolve => setTimeout(resolve, 250)); 
    if (!currentDiscussionId || aiMessageStreaming || generationInProgress) return;
    try {
        const response = await apiRequest(`/api/discussions/${currentDiscussionId}`);
        const loadedMessages = await response.json();
        currentMessages = loadedMessages.map(msg => ({...msg, steps: msg.steps || [], metadata: msg.metadata || []}));

        if (loadedMessages.length > 0) {
            const lastMessage = loadedMessages[loadedMessages.length - 1];
            if (lastMessage.created_at) {
                discussions[currentDiscussionId].last_activity_at = lastMessage.created_at;
            }
        } else {
                const discussionResponse = await apiRequest(`/api/discussions`);
                const allDiscs = await discussionResponse.json();
                const updatedDisc = allDiscs.find(d => d.id === currentDiscussionId);
                if (updatedDisc && updatedDisc.last_activity_at) {
                    discussions[currentDiscussionId].last_activity_at = updatedDisc.last_activity_at;
                }
        }
        renderMessages(currentMessages);
        renderDiscussionList();
    } catch (error) {
            renderMessage({ id: `err-refresh-${Date.now()}`, sender: 'system', content: translate('refresh_message_list_failed_error'), steps:[], metadata:[] });
    }
}

// --- Message Rendering ---
function clearChatArea(clearHeader = true) {
    chatMessages.innerHTML = '';
        if (clearHeader) {
        discussionTitle.textContent = translate('default_discussion_title');
        sendMessageBtn.disabled = true;
        ragToggleBtn.classList.remove('rag-toggle-on'); ragToggleBtn.classList.add('rag-toggle-off');
        ragDataStoreSelect.style.display = 'none'; ragDataStoreSelect.value = '';
        isRagActive = false; updateRagToggleButtonState();
        } else {
        if (!currentDiscussionId) { 
            chatMessages.innerHTML = `<div class="text-center text-gray-500 italic mt-10">${translate('chat_area_empty_placeholder')}</div>`;
        }
        }
    currentMessages = []; 
    currentAiMessageContainer = null;
    currentAiMessageContentAccumulator = "";
    currentAiMessageId = null;
    currentAiMessageData = null;
}


// Enhanced message rendering with syntax highlighting and improved styling
function renderMessage(message) {
    if (!message || typeof message.sender === 'undefined' || (typeof message.content === 'undefined' && (!message.image_references || message.image_references.length === 0) && (!message.steps || message.steps.length === 0) && (!message.metadata || message.metadata.length === 0))) {
        return;
    }
    
    const messageId = message.id || `temp-render-${Date.now()}`;
    const domId = `message-${messageId}`; 

    let messageContainer = document.querySelector(`.message-container[data-message-id="${messageId}"]`);
    let bubbleDiv;

    if (messageContainer) {
        bubbleDiv = messageContainer.querySelector('.message-bubble');
        if (!bubbleDiv) {
            console.error("renderMessage: Container found but bubble missing for ID:", messageId, ". Recreating bubble.");
            messageContainer.innerHTML = ''; 
            bubbleDiv = document.createElement('div');
            bubbleDiv.id = domId; 
            messageContainer.appendChild(bubbleDiv);
        } else {
            // Clear existing content for update
            const elementsToRemove = ['.sender-name', '.message-images-container', '.message-timestamp'];
            elementsToRemove.forEach(selector => {
                const el = bubbleDiv.querySelector(selector);
                if (el) el.remove();
            });
            
            const contentEl = bubbleDiv.querySelector('.message-content');
            if (contentEl) {
                contentEl.innerHTML = '';
            } else {
                const newContentDiv = document.createElement('div');
                newContentDiv.className = 'message-content';
                bubbleDiv.appendChild(newContentDiv);
            }
            
            const footerEl = bubbleDiv.querySelector('.message-footer');
            if (footerEl) {
                footerEl.innerHTML = '';
            } else {
                const newFooterDiv = document.createElement('div');
                newFooterDiv.className = 'message-footer';
                bubbleDiv.appendChild(newFooterDiv);
            }
            
            const actionsContEl = bubbleDiv.querySelector('.message-actions-container');
            if (actionsContEl) {
                actionsContEl.innerHTML = '';
            } else {
                const newActionsContainer = document.createElement('div');
                newActionsContainer.className = 'message-actions-container';
                bubbleDiv.appendChild(newActionsContainer);
            }
        }
    } else {
        messageContainer = document.createElement('div');
        messageContainer.className = 'message-container flex flex-col';
        messageContainer.dataset.messageId = messageId; 

        bubbleDiv = document.createElement('div');
        bubbleDiv.id = domId; 
        messageContainer.appendChild(bubbleDiv);
        chatMessages.appendChild(messageContainer);
        
        // Add entrance animation
        messageContainer.style.opacity = '0';
        messageContainer.style.transform = 'translateY(20px)';
        requestAnimationFrame(() => {
            messageContainer.style.transition = 'all 0.3s ease-out';
            messageContainer.style.opacity = '1';
            messageContainer.style.transform = 'translateY(0)';
        });
    }

    // Handle spacing between different senders
    if (message.addSpacing && messageContainer.previousElementSibling) {
        messageContainer.classList.add('mt-4');
    } else {
        messageContainer.classList.remove('mt-4');
    }

    // Determine bubble type and styling
    let bubbleClass = 'ai-bubble';
    let senderNameText = message.sender;
    let showGrade = false;
    const userNames = [currentUser.username, 'user', 'You', translate('sender_you', 'You'), translate('sender_user', 'User'), currentUser.lollms_client_ai_name ? null : currentUser.username];

    if (userNames.includes(senderNameText) || (message.sender === "User" && currentUser.username === "user")) {
        bubbleClass = 'user-bubble'; 
        senderNameText = '';
    } else if (senderNameText && (senderNameText.toLowerCase() === 'system' || senderNameText.toLowerCase() === 'error')) {
        bubbleClass = 'system-bubble'; 
        senderNameText = '';
    } else {
        bubbleClass = 'ai-bubble';
        senderNameText = currentUser.lollms_client_ai_name || message.sender || translate('sender_assistant', 'Assistant');
        showGrade = !messageId.startsWith('temp-');
    }
    
    bubbleDiv.className = `message-bubble ${bubbleClass}`; 

    // Add timestamp
    if (message.timestamp || message.created_at) {
        const timestampDiv = document.createElement('div');
        timestampDiv.className = 'message-timestamp';
        const timestamp = new Date(message.timestamp || message.created_at);
        timestampDiv.textContent = formatTimestamp(timestamp);
        bubbleDiv.appendChild(timestampDiv);
    }

    // Add sender name
    if (senderNameText) {
        const senderDiv = document.createElement('div');
        senderDiv.className = 'sender-name';
        senderDiv.innerHTML = `
            <div class="flex items-center gap-2">
                <span class="sender-avatar">${getSenderAvatar(senderNameText)}</span>
                <span class="sender-text">${senderNameText}</span>
                ${message.model_name ? `<span class="model-badge">${message.model_name}</span>` : ''}
            </div>
        `;
        bubbleDiv.appendChild(senderDiv);
    }

    // Handle images
    if (message.image_references && message.image_references.length > 0) {
        const imagesContainer = document.createElement('div');
        imagesContainer.className = 'message-images-container';
        
        message.image_references.forEach((imgSrc, index) => {
            const imgItem = document.createElement('div');
            imgItem.className = 'message-image-item';
            
            const imgTag = document.createElement('img');
            imgTag.src = imgSrc;
            imgTag.alt = translate('chat_image_alt', 'Chat Image');
            imgTag.loading = 'lazy';
            imgTag.onclick = () => viewImage(imgSrc);
            
            // Add image loading states
            imgTag.onload = () => imgItem.classList.add('loaded');
            imgTag.onerror = () => imgItem.classList.add('error');
            
            imgItem.appendChild(imgTag);
            imagesContainer.appendChild(imgItem);
        });
        
        bubbleDiv.appendChild(imagesContainer);
    }

    // Handle content with enhanced processing
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    bubbleDiv.appendChild(contentDiv);

    if (message.content || (aiMessageStreaming && messageId === currentAiMessageId) || (message.steps && message.steps.length > 0) || (message.metadata && message.metadata.length > 0)) {
        renderEnhancedContent(contentDiv, message.content || "", messageId, message.steps, message.metadata, message); 
        if (messageId === currentAiMessageId && (aiMessageStreaming || generationInProgress)) {
             currentAiMessageContainer = messageContainer; 
        }
    } else if ((!message.image_references || message.image_references.length === 0)) {
        contentDiv.innerHTML = `<p class="empty-message">${translate('empty_message_placeholder')}</p>`;
    }

    // Enhanced footer with better layout
    const footerDiv = document.createElement('div');
    footerDiv.className = 'message-footer';
    bubbleDiv.appendChild(footerDiv);

    // Message details
    const detailsContainer = document.createElement('div');
    detailsContainer.className = 'message-details';
    
    if (message.token_count) {
        const tokenBadge = document.createElement('span');
        tokenBadge.className = 'detail-badge token-badge';
        tokenBadge.innerHTML = `<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg> ${message.token_count}`;
        detailsContainer.appendChild(tokenBadge);
    }
    
    if (message.processing_time) {
        const timeBadge = document.createElement('span');
        timeBadge.className = 'detail-badge time-badge';
        timeBadge.innerHTML = `<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/></svg> ${formatProcessingTime(message.processing_time)}`;
        detailsContainer.appendChild(timeBadge);
    }

    // Actions container
    const actionsContainer = document.createElement('div');
    actionsContainer.className = 'message-actions-container';
    
    if (!messageId.startsWith('temp-')) {
        const actionsGroup = document.createElement('div');
        actionsGroup.className = 'message-actions';
        
        // Copy button
        const copyBtn = createActionButton('copy', translate('copy_content_tooltip'), () => {
            navigator.clipboard.writeText(message.content || "")
                .then(() => showStatus(translate('status_content_copied', "Content copied!"), "success"))
                .catch(err => showStatus(translate('status_copy_failed', "Copy failed."), "error"));
        });
        
        // Edit button
        const editBtn = createActionButton('edit', translate('edit_message_tooltip'), () => {
            initiateEditMessage(messageId);
        });
        
        // Delete button
        const deleteBtn = createActionButton('delete', translate('delete_message_tooltip'), () => {
            deleteMessage(messageId);
        }, 'destructive');
        
        // Regenerate button (for AI messages)
        if (bubbleClass === 'ai-bubble') {
            const regenerateBtn = createActionButton('refresh', translate('regenerate_message_tooltip'), () => {
                regenerateMessage(messageId);
            });
            actionsGroup.appendChild(regenerateBtn);
        }
        
        actionsGroup.appendChild(copyBtn);
        actionsGroup.appendChild(editBtn);
        actionsGroup.appendChild(deleteBtn);
        
        actionsContainer.appendChild(actionsGroup);
    }

    // Rating system for AI messages
    if (showGrade) {
        const ratingContainer = document.createElement('div');
        ratingContainer.className = 'message-rating';
        
        const userGrade = message.user_grade || 0;
        
        const upvoteBtn = document.createElement('button');
        upvoteBtn.className = `rating-btn upvote ${userGrade > 0 ? 'active' : ''}`;
        upvoteBtn.innerHTML = `<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M3.293 9.707a1 1 0 010-1.414l6-6a1 1 0 011.414 0l6 6a1 1 0 01-1.414 1.414L10 4.414 4.707 9.707a1 1 0 01-1.414 0z" clip-rule="evenodd"/></svg>`;
        upvoteBtn.title = translate('grade_good_tooltip');
        upvoteBtn.onclick = () => gradeMessage(messageId, 1);
        
        const gradeDisplay = document.createElement('span');
        gradeDisplay.className = 'rating-score';
        gradeDisplay.textContent = userGrade;
        
        const downvoteBtn = document.createElement('button');
        downvoteBtn.className = `rating-btn downvote ${userGrade < 0 ? 'active' : ''}`;
        downvoteBtn.innerHTML = `<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 10.293a1 1 0 010 1.414l-6 6a1 1 0 01-1.414 0l-6-6a1 1 0 111.414-1.414L10 15.586l5.293-5.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>`;
        downvoteBtn.title = translate('grade_bad_tooltip');
        downvoteBtn.onclick = () => gradeMessage(messageId, -1);
        
        ratingContainer.appendChild(upvoteBtn);
        ratingContainer.appendChild(gradeDisplay);
        ratingContainer.appendChild(downvoteBtn);
        
        actionsContainer.appendChild(ratingContainer);
    }

    // Assemble footer
    const footerContent = document.createElement('div');
    footerContent.className = 'footer-content';
    footerContent.appendChild(detailsContainer);
    footerContent.appendChild(actionsContainer);
    footerDiv.appendChild(footerContent);
}

// Enhanced content rendering with syntax highlighting
function renderEnhancedContent(contentDiv, content, messageId, steps, metadata, message) {
    if (!content && (!steps || steps.length === 0) && (!metadata || metadata.length === 0)) {
        return;
    }

    // Process markdown with enhanced code block handling
    const processedContent = enhanceMarkdownContent(content);
    contentDiv.innerHTML = processedContent;
    
    // Apply syntax highlighting to code blocks
    applySyntaxHighlighting(contentDiv);
    
    // Handle steps and metadata if present
    if (steps && steps.length > 0) {
        renderSteps(contentDiv, steps);
    }
    
    if (metadata && metadata.length > 0) {
        renderMetadata(contentDiv, metadata);
    }
    
    // Add copy buttons to code blocks
    addCodeBlockCopyButtons(contentDiv);
    
    // Process mathematical expressions if present
    if (typeof MathJax !== 'undefined') {
        MathJax.typesetPromise([contentDiv]).catch(err => console.warn('MathJax error:', err));
    }
}

// Enhanced markdown processing (continued)
function enhanceMarkdownContent(content) {
    if (!content) return '';

    // Enhanced code block regex to capture language
    const codeBlockRegex = /```(\w+)?\n?([\s\S]*?)```/g;

    return content.replace(codeBlockRegex, (match, language, code) => {
        const lang = language || 'text';
        const escapedCode = escapeHtml(code.trim());
        return `<div class="code-block-container">
            <div class="code-block-header">
                <span class="code-language">${lang}</span>
                <button class="code-copy-btn" data-code="${escapeHtml(code.trim())}">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M8 3a1 1 0 011-1h2a1 1 0 110 2H9a1 1 0 01-1-1z"/>
                        <path d="M6 3a2 2 0 00-2 2v11a2 2 0 002 2h8a2 2 0 002-2V5a2 2 0 00-2-2 1 1 0 000 2h1v10H7V5a1 1 0 000-2z"/>
                    </svg>
                    Copy
                </button>
            </div>
            <pre class="code-block language-${lang}"><code class="language-${lang}">${escapedCode}</code></pre>
        </div>`;
    });
}

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

// Basic syntax highlighting fallback
function applyBasicSyntaxHighlighting(codeElement, language) {
    let code = codeElement.textContent;
    
    switch (language.toLowerCase()) {
        case 'javascript':
        case 'js':
            code = highlightJavaScript(code);
            break;
        case 'python':
        case 'py':
            code = highlightPython(code);
            break;
        case 'html':
            code = highlightHTML(code);
            break;
        case 'css':
            code = highlightCSS(code);
            break;
        case 'json':
            code = highlightJSON(code);
            break;
        case 'sql':
            code = highlightSQL(code);
            break;
        case 'bash':
        case 'shell':
            code = highlightBash(code);
            break;
        default:
            // Basic highlighting for unknown languages
            code = highlightGeneric(code);
    }
    
    codeElement.innerHTML = code;
}

// Language-specific highlighting functions
function highlightJavaScript(code) {
    const keywords = ['function', 'const', 'let', 'var', 'if', 'else', 'for', 'while', 'return', 'class', 'extends', 'import', 'export', 'async', 'await', 'try', 'catch', 'finally'];
    const builtins = ['console', 'document', 'window', 'Array', 'Object', 'String', 'Number', 'Boolean', 'Date', 'Math', 'JSON'];
    
    return code
        .replace(new RegExp(`\\b(${keywords.join('|')})\\b`, 'g'), '<span class="syntax-keyword">$1</span>')
        .replace(new RegExp(`\\b(${builtins.join('|')})\\b`, 'g'), '<span class="syntax-builtin">$1</span>')
        .replace(/\/\/.*$/gm, '<span class="syntax-comment">$&</span>')
        .replace(/\/\*[\s\S]*?\*\//g, '<span class="syntax-comment">$&</span>')
        .replace(/"([^"\\]|\\.)*"/g, '<span class="syntax-string">$&</span>')
        .replace(/'([^'\\]|\\.)*'/g, '<span class="syntax-string">$&</span>')
        .replace(/`([^`\\]|\\.)*`/g, '<span class="syntax-template">$&</span>')
        .replace(/\b\d+\.?\d*\b/g, '<span class="syntax-number">$&</span>');
}

function highlightPython(code) {
    const keywords = ['def', 'class', 'if', 'elif', 'else', 'for', 'while', 'try', 'except', 'finally', 'with', 'as', 'import', 'from', 'return', 'yield', 'lambda', 'and', 'or', 'not', 'in', 'is'];
    const builtins = ['print', 'len', 'range', 'str', 'int', 'float', 'list', 'dict', 'tuple', 'set', 'bool', 'type', 'isinstance', 'hasattr', 'getattr', 'setattr'];
    
    return code
        .replace(new RegExp(`\\b(${keywords.join('|')})\\b`, 'g'), '<span class="syntax-keyword">$1</span>')
        .replace(new RegExp(`\\b(${builtins.join('|')})\\b`, 'g'), '<span class="syntax-builtin">$1</span>')
        .replace(/#.*$/gm, '<span class="syntax-comment">$&</span>')
        .replace(/"""[\s\S]*?"""/g, '<span class="syntax-docstring">$&</span>')
        .replace(/"([^"\\]|\\.)*"/g, '<span class="syntax-string">$&</span>')
        .replace(/'([^'\\]|\\.)*'/g, '<span class="syntax-string">$&</span>')
        .replace(/f"([^"\\]|\\.)*"/g, '<span class="syntax-fstring">$&</span>')
        .replace(/\b\d+\.?\d*\b/g, '<span class="syntax-number">$&</span>');
}

function highlightHTML(code) {
    return code
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/&lt;!--[\s\S]*?--&gt;/g, '<span class="syntax-comment">$&</span>')
        .replace(/&lt;(\/?[\w-]+)([^&gt;]*)&gt;/g, (match, tag, attrs) => {
            const highlightedAttrs = attrs.replace(/([\w-]+)=("[^"]*"|'[^']*')/g, 
                '<span class="syntax-attr-name">$1</span>=<span class="syntax-attr-value">$2</span>');
            return `&lt;<span class="syntax-tag">${tag}</span>${highlightedAttrs}&gt;`;
        });
}

function highlightCSS(code) {
    return code
        .replace(/\/\*[\s\S]*?\*\//g, '<span class="syntax-comment">$&</span>')
        .replace(/([.#]?[\w-]+)\s*{/g, '<span class="syntax-selector">$1</span> {')
        .replace(/([\w-]+)\s*:/g, '<span class="syntax-property">$1</span>:')
        .replace(/:\s*([^;]+);/g, ': <span class="syntax-value">$1</span>;')
        .replace(/"([^"\\]|\\.)*"/g, '<span class="syntax-string">$&</span>')
        .replace(/'([^'\\]|\\.)*'/g, '<span class="syntax-string">$&</span>');
}

function highlightJSON(code) {
    return code
        .replace(/"([^"\\]|\\.)*"\s*:/g, '<span class="syntax-key">$&</span>')
        .replace(/:\s*"([^"\\]|\\.)*"/g, ': <span class="syntax-string">$&</span>')
        .replace(/:\s*(true|false|null)/g, ': <span class="syntax-literal">$1</span>')
        .replace(/:\s*(-?\d+\.?\d*)/g, ': <span class="syntax-number">$1</span>');
}

function highlightSQL(code) {
    const keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'INNER', 'LEFT', 'RIGHT', 'OUTER', 'ON', 'GROUP', 'BY', 'ORDER', 'HAVING', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'TABLE', 'INDEX', 'VIEW'];
    
    return code
        .replace(new RegExp(`\\b(${keywords.join('|')})\\b`, 'gi'), '<span class="syntax-keyword">$1</span>')
        .replace(/--.*$/gm, '<span class="syntax-comment">$&</span>')
        .replace(/'([^'\\]|\\.)*'/g, '<span class="syntax-string">$&</span>')
        .replace(/\b\d+\.?\d*\b/g, '<span class="syntax-number">$&</span>');
}

function highlightBash(code) {
    const commands = ['ls', 'cd', 'pwd', 'mkdir', 'rmdir', 'rm', 'cp', 'mv', 'cat', 'grep', 'find', 'chmod', 'chown', 'sudo', 'apt', 'yum', 'git', 'npm', 'pip'];
    
    return code
        .replace(new RegExp(`\\b(${commands.join('|')})\\b`, 'g'), '<span class="syntax-command">$1</span>')
        .replace(/#.*$/gm, '<span class="syntax-comment">$&</span>')
        .replace(/"([^"\\]|\\.)*"/g, '<span class="syntax-string">$&</span>')
        .replace(/'([^'\\]|\\.)*'/g, '<span class="syntax-string">$&</span>')
        .replace(/--?\w+/g, '<span class="syntax-option">$&</span>');
}

function highlightGeneric(code) {
    return code
        .replace(/"([^"\\]|\\.)*"/g, '<span class="syntax-string">$&</span>')
        .replace(/'([^'\\]|\\.)*'/g, '<span class="syntax-string">$&</span>')
        .replace(/\b\d+\.?\d*\b/g, '<span class="syntax-number">$&</span>')
        .replace(/#.*$/gm, '<span class="syntax-comment">$&</span>')
        .replace(/\/\/.*$/gm, '<span class="syntax-comment">$&</span>');
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

function getSenderAvatar(senderName) {
    // Generate a simple avatar based on sender name
    const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8'];
    const colorIndex = senderName.length % colors.length;
    const initial = senderName.charAt(0).toUpperCase();
    
    return `<div class="sender-avatar" style="background-color: ${colors[colorIndex]}">${initial}</div>`;
}

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

// Enhanced renderMessages function
function renderMessages(messagesToRender) {
    chatMessages.innerHTML = ''; 
    
    if (messagesToRender.length === 0 && currentDiscussionId) {
        const emptyState = document.createElement('div');
        emptyState.className = 'chat-empty-state';
        emptyState.innerHTML = `
            <div class="empty-state-content">
                <svg class="empty-state-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                </svg>
                <h3 class="empty-state-title">${translate('chat_area_no_messages_yet', 'No messages yet')}</h3>
                <p class="empty-state-description">${translate('chat_area_start_conversation', 'Start a conversation by typing a message below.')}</p>
            </div>
        `;
        chatMessages.appendChild(emptyState);
        return;
    }

    // Group messages by date for better organization
    const messagesByDate = groupMessagesByDate(messagesToRender);
    
    Object.entries(messagesByDate).forEach(([date, messages]) => {
        // Add date separator
        if (Object.keys(messagesByDate).length > 1) {
            const dateSeparator = document.createElement('div');
            dateSeparator.className = 'date-separator';
            dateSeparator.innerHTML = `
                <div class="date-separator-line"></div>
                <div class="date-separator-text">${formatDateSeparator(new Date(date))}</div>
                <div class="date-separator-line"></div>
            `;
            chatMessages.appendChild(dateSeparator);
        }

        // Render messages for this date
        messages.forEach((msg, index) => {
            msg.addSpacing = (index > 0 && messages[index-1].sender !== msg.sender);
            renderMessage(msg);
        });
    });

    // Smooth scroll to bottom
    requestAnimationFrame(() => {
        scrollChatToBottom();
    });
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

// Enhanced scroll function with smooth animation
function scrollChatToBottom(smooth = true) {
    if (smooth) {
        chatMessages.scrollTo({
            top: chatMessages.scrollHeight,
            behavior: 'smooth'
        });
    } else {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}



function renderMessages(messagesToRender) {
    chatMessages.innerHTML = ''; 
    if (messagesToRender.length === 0 && currentDiscussionId) {
        chatMessages.innerHTML = `<p class="text-gray-500 text-center italic mt-10">${translate('chat_area_no_messages_yet')}</p>`;
        return;
    }
    messagesToRender.forEach((msg, index) => {
            msg.addSpacing = (index > 0 && messagesToRender[index-1].sender !== msg.sender);
            renderMessage(msg);
    });
    scrollChatToBottom();
}

function renderProcessedContent(element, rawContent, messageId, steps = [], metadata = [], messageObject = {}) {
    // console.log("renderProcessedContent: Called for ID:", messageId, "Raw content length:", rawContent.length, "Streaming:", aiMessageStreaming, "GenInProg:", generationInProgress);
    element.innerHTML = ''; // Start fresh for content area

    let currentContent = rawContent;
    
    const thinkBlockRegex = /<think>([\s\S]*?)<\/think>/gs;
    let lastIndex = 0;
    let match;

    // Render "think" blocks first
    while ((match = thinkBlockRegex.exec(currentContent)) !== null) {
        const textBefore = currentContent.substring(lastIndex, match.index);
        if (textBefore.trim()) {
            const regularContentDiv = document.createElement('div');
            regularContentDiv.innerHTML = marked.parse(textBefore);
            element.appendChild(regularContentDiv);
        }

        const thinkDetails = document.createElement('details');
        thinkDetails.className = 'think-block my-2';
        const thinkSummary = document.createElement('summary');
        thinkSummary.className = 'px-2 py-1 text-xs italic text-gray-400 cursor-pointer hover:bg-gray-750 rounded';
        thinkSummary.textContent = translate('assistant_thoughts_summary', "Assistant's Thoughts");
        const thinkContentDiv = document.createElement('div');
        thinkContentDiv.className = 'think-content p-2 border-t border-gray-700 prose prose-sm max-w-none prose-invert';
        thinkContentDiv.innerHTML = marked.parse(match[1]);
        
        thinkDetails.appendChild(thinkSummary);
        thinkDetails.appendChild(thinkContentDiv);
        element.appendChild(thinkDetails);
        
        lastIndex = thinkBlockRegex.lastIndex;
    }

    const remainingContent = currentContent.substring(lastIndex);
    if (remainingContent.trim()) {
        const finalContentDiv = document.createElement('div');
        finalContentDiv.innerHTML = marked.parse(remainingContent);
        element.appendChild(finalContentDiv);
    }
    
    // Render Steps
    if (steps && steps.length > 0) {
        // console.log("renderProcessedContent: Rendering steps for ID:", messageId, steps.length, "steps");
        const stepsContainer = document.createElement('div');
        stepsContainer.className = 'steps-container my-2'; // Removed extra padding/border from here, style via CSS
        
        steps.forEach((step) => {
            const stepDiv = document.createElement('div');
            stepDiv.className = 'step-item flex items-center text-xs py-0.5';
            const iconSpan = document.createElement('span');
            iconSpan.className = 'mr-2 w-4 h-4 flex-shrink-0 flex items-center justify-center'; // Added justify-center
            if (step.done && step.status === 'success') {
                iconSpan.innerHTML = `<svg class="w-full h-full text-green-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>`;
            } else if (step.done && step.status === 'failure') {
                iconSpan.innerHTML = `<svg class="w-full h-full text-red-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path></svg>`;
            } else { 
                iconSpan.innerHTML = `<div class="w-2.5 h-2.5 bg-blue-500 rounded-full animate-pulse"></div>`;
            }
            stepDiv.appendChild(iconSpan);
            const textSpan = document.createElement('span');
            textSpan.textContent = step.text || 'Processing...';
            textSpan.className = step.done && step.status==='failure' ? 'text-red-400 line-through' : (step.done ? 'text-gray-400 line-through' : 'text-gray-200');
            stepDiv.appendChild(textSpan);
            if(step.description){
                const descSpan = document.createElement('span');
                descSpan.textContent = ` (${step.description})`;
                descSpan.className = 'text-gray-500 ml-1';
                stepDiv.appendChild(descSpan);
            }
            stepsContainer.appendChild(stepDiv);
        });
        element.appendChild(stepsContainer);
    }

    // Logic for Typing Indicator or Empty Placeholder
    const isCurrentlyStreamingMainContent = aiMessageStreaming && messageId === currentAiMessageId && currentAiMessageContentAccumulator !== "";
    const isWaitingForFirstToken = generationInProgress && messageId === currentAiMessageId && currentAiMessageContentAccumulator === "" && !isCurrentlyStreamingMainContent;
    
    if (isWaitingForFirstToken) {
        // console.log("renderProcessedContent: Adding typing indicator for ID:", messageId);
        // Check if an indicator already exists to prevent duplicates during rapid re-renders
        if (!element.querySelector('.typing-indicator')) {
            const typingIndicatorDiv = document.createElement('div');
            typingIndicatorDiv.className = 'typing-indicator flex items-center space-x-1 h-5 my-1'; // Added my-1 for spacing
            for (let i = 0; i < 3; i++) {
                const dot = document.createElement('span');
                typingIndicatorDiv.appendChild(dot);
            }
            element.appendChild(typingIndicatorDiv);
        }
    } else if (element.innerHTML.trim() === "" && 
               (!messageObject.image_references || messageObject.image_references.length === 0) && 
               (!steps || steps.length === 0) && 
               (!metadata || metadata.length === 0) &&
               !(messageId === currentAiMessageId && (aiMessageStreaming || generationInProgress)) 
        ) {
        // console.log("renderProcessedContent: Adding empty message placeholder for ID:", messageId);
        element.innerHTML = `<p class="italic text-gray-500">${translate('empty_message_placeholder')}</p>`;
    }
    
    try { renderMathInElement(element, { delimiters: [ {left: '$$', right: '$$', display: true}, {left: '$', right: '$', display: false}, {left: '\\(', right: '\\)', display: false}, {left: '\\[', right: '\\]', display: true} ], throwOnError: false }); }
    catch(e) { /* KaTeX rendering error logged by KaTeX */ }
    
    renderCustomCodeBlocks(element, messageId);
    // console.log("renderProcessedContent: Finished processing for ID:", messageId);
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
async function gradeMessage(messageId, change) { 
        if (!currentDiscussionId || !messageId || messageId.startsWith('temp-')) return;
        const messageElement = document.getElementById(`message-${messageId}`); if (!messageElement) return;
        try {
        const response = await apiRequest(`/api/discussions/${currentDiscussionId}/messages/${messageId}/grade`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ change: change })
        });
            const updatedMessage = await response.json();
            const gradeSpan = messageElement.querySelector('.grade-score');
            const upBtn = messageElement.querySelector('.grade-btn:first-of-type'); 
            const downBtn = messageElement.querySelector('.grade-btn:last-of-type');
            if (gradeSpan) gradeSpan.textContent = updatedMessage.user_grade;
            if (upBtn) upBtn.classList.toggle('selected-up', updatedMessage.user_grade > 0); else if (upBtn) upBtn.classList.remove('selected-up');
            if (downBtn) downBtn.classList.toggle('selected-down', updatedMessage.user_grade < 0); else if (downBtn) downBtn.classList.remove('selected-down');
            const msgIndex = currentMessages.findIndex(m => m.id === messageId);
            if (msgIndex > -1) currentMessages[msgIndex].user_grade = updatedMessage.user_grade;
        } catch (error) { showStatus(translate('status_grade_update_failed'), 'error'); }
}

// --- Message Edit/Delete ---
function initiateEditMessage(messageId) { 
    const messageData = currentMessages.find(m => m.id === messageId);
    if (!messageData) { showStatus(translate('status_cannot_find_message_to_edit'), "error"); return; }
    editMessageIdInput.value = messageId; editMessageInput.value = messageData.content;
    showStatus('', 'info', editMessageStatus); openModal('editMessageModal');
}
async function confirmMessageEdit() { 
    const messageId = editMessageIdInput.value; const newContent = editMessageInput.value;
    if (!messageId || !currentDiscussionId) return;
    showStatus(translate('status_saving_changes', 'Saving changes...'), 'info', editMessageStatus); confirmEditMessageBtn.disabled = true;
    try {
        const response = await apiRequest(`/api/discussions/${currentDiscussionId}/messages/${messageId}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: newContent }), statusElement: editMessageStatus
        });
        const updatedMessageData = await response.json(); 
        const msgIndex = currentMessages.findIndex(m => m.id === messageId);
        if (msgIndex > -1) {
            currentMessages[msgIndex] = {...currentMessages[msgIndex], ...updatedMessageData, steps: currentMessages[msgIndex].steps, metadata: currentMessages[msgIndex].metadata}; 
        }
        
        const messageElementContainer = document.getElementById(`message-${messageId}`)?.closest('.message-container');
        if (messageElementContainer) { 
            const tempMsg = { ...currentMessages[msgIndex], addSpacing: messageElementContainer.classList.contains('mt-3') };
            const oldScroll = chatMessages.scrollTop; 
            renderMessage(tempMsg); 
            chatMessages.scrollTop = oldScroll;
        }
        if(discussions[currentDiscussionId] && updatedMessageData.created_at) {
            discussions[currentDiscussionId].last_activity_at = updatedMessageData.created_at;
            renderDiscussionList();
        }
        showStatus(translate('status_message_updated_success', 'Message updated successfully.'), 'success', editMessageStatus);
        setTimeout(() => closeModal('editMessageModal'), 1000);
    } catch (error) { /* Handled by apiRequest */ }
    finally { confirmEditMessageBtn.disabled = false; }
}
async function deleteMessage(messageId) { 
        if (!currentDiscussionId || !messageId || messageId.startsWith('temp-')) return;
        const messageElement = document.getElementById(`message-${messageId}`);
        const msgPreview = messageElement ? (messageElement.querySelector('.message-content')?.textContent || translate('image_message_placeholder', 'Image message')).substring(0,50)+'...' : translate('message_id_placeholder', `message ${messageId}`, {id: messageId});
        if (confirm(translate('confirm_delete_message', `Are you sure you want to delete this message?\n\n"${msgPreview}"`, {preview: msgPreview}))) {
            showStatus(translate('status_deleting_message', 'Deleting message...'), 'info');
            try {
                await apiRequest(`/api/discussions/${currentDiscussionId}/messages/${messageId}`, { method: 'DELETE' });
                currentMessages = currentMessages.filter(m => m.id !== messageId);
                messageElement?.closest('.message-container')?.remove();
                showStatus(translate('status_message_deleted_success', 'Message deleted successfully.'), 'success');
                await refreshMessagesAfterStream();
            } catch (error) { /* Handled by apiRequest */ }
        }
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
