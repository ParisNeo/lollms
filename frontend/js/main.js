// --- Localization State ---
let currentTranslations = {};
let currentLang = 'en';
let availableLanguages = { 'en': 'English', 'fr': 'Français' };

// --- Global State ---
let currentUser = null;
let currentDiscussionId = null;
// --- NEW STATE for Branching ---
let discussions = {}; // Enhanced: { discId: { title, is_starred, rag_datastore_id, last_activity_at, branches: { branchId: [messages] }, activeBranchId, messages_loaded_fully: {branchId: bool} } }
let currentMessages = []; // Points to discussions[currentDiscussionId].branches[activeBranchId]
let activeBranchId = null; // Global active branch ID for the current discussion
const backendCapabilities = { // NEW: To track backend features
    supportsBranches: false,
    checked: false
};
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

let currentSortMethod = 'date_desc'; // Default sort method: Most Recent


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
const saveLLMParamsBtn = document.getElementById('saveLLMParamsBtn');

const settingsContextSize = document.getElementById('settingsContextSize');
const settingsTemperature = document.getElementById('settingsTemperature');
const settingsTopK = document.getElementById('settingsTopK');
const settingsTopP = document.getElementById('settingsTopP');
const settingsRepeatPenalty = document.getElementById('settingsRepeatPenalty');
const settingsRepeatLastN = document.getElementById('settingsRepeatLastN');

const settingsStatus_llmConfig = document.getElementById('settingsStatus_llmConfig');
const settingsStatus_llmParams = document.getElementById('settingsStatus_llmParams');
const settingsCurrentPassword = document.getElementById('settingsCurrentPassword');
const settingsNewPassword = document.getElementById('settingsNewPassword');
const settingsConfirmPassword = document.getElementById('settingsConfirmPassword');
const changePasswordBtn = document.getElementById('changePasswordBtn');
const passwordChangeStatus = document.getElementById('passwordChangeStatus');
const dataStoresModal = document.getElementById('dataStoresModal');
const createDataStoreForm = document.getElementById('createDataStoreForm');
const btnCreateDataStore = document.getElementById('btnCreateDataStore');

const btnCancelCreateDataStore = document.getElementById('btnCancelCreateDataStore');
const btnOpenCreateStore = document.getElementById('btnOpenCreateStore');


const newDataStoreNameInput = document.getElementById('newDataStoreName');
const newDataStoreDescriptionInput = document.getElementById('newDataStoreDescription');

const editDataStoreForm = document.getElementById('editDataStoreForm');
const btnEditDataStore = document.getElementById('btnEditDataStore');
const btnCancelEditDataStore = document.getElementById('btnCancelEditDataStore');

const editDataStoreNameInput = document.getElementById('editDataStoreName');
const editDataStoreNewNameInput = document.getElementById('editDataStoreNewName');

const editDataStoreDescriptionInput = document.getElementById('editDataStoreDescription');

const createDataStoreStatus = document.getElementById('createDataStoreStatus');
const editDataStoreStatus = document.getElementById('editDataStoreStatus');

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


const settingsFirstName = document.getElementById('settingsFirstName');
const settingsFamilyName = document.getElementById('settingsFamilyName');
const settingsEmail = document.getElementById('settingsEmail');
const settingsBirthDate = document.getElementById('settingsBirthDate');
const saveProfileBtn = document.getElementById('saveProfileBtn');
const settingsStatus_profile = document.getElementById('settingsStatus_profile');

const settingsActivePersonality = document.getElementById('settingsActivePersonality');
const userPersonalitiesList = document.getElementById('userPersonalitiesList');
const createNewPersonalityBtn = document.getElementById('createNewPersonalityBtn');
const publicPersonalitiesList = document.getElementById('publicPersonalitiesList');
const saveActivePersonalityBtn = document.getElementById('saveActivePersonalityBtn');
const settingsStatus_personalities = document.getElementById('settingsStatus_personalities');

const personalityEditorModal = document.getElementById('personalityEditorModal');
const personalityEditorTitle = document.getElementById('personalityEditorTitle');
const personalityEditorId = document.getElementById('personalityEditorId');
const personalityName = document.getElementById('personalityName');
const personalityCategory = document.getElementById('personalityCategory');
const personalityAuthor = document.getElementById('personalityAuthor');
const personalityDescription = document.getElementById('personalityDescription');
const personalityPromptText = document.getElementById('personalityPromptText');
const personalityDisclaimer = document.getElementById('personalityDisclaimer');
const personalityScriptCode = document.getElementById('personalityScriptCode');
const personalityIconUpload = document.getElementById('personalityIconUpload');
const personalityIconPreview = document.getElementById('personalityIconPreview');
const personalityIconBase64 = document.getElementById('personalityIconBase64');
const savePersonalityBtn = document.getElementById('savePersonalityBtn');
const personalityEditorStatus = document.getElementById('personalityEditorStatus');


const settingsPutThoughts = document.getElementById('settingsPutThoughts'); // For LLM Params


const settingsRagTopK = document.getElementById('settingsRagTopK');
const settingsRagMAXLEN = document.getElementById('settingsRagMAXLEN');
const settingsRagNBHops = document.getElementById('settingsRagNBHops');

const settingsRagMinSimPercent = document.getElementById('settingsRagMinSimPercent');

const settingsRagUseGraph = document.getElementById('settingsRagUseGraph');
const settingsRagGraphResponseTypeBlock = document.getElementById('settingsRagGraphResponseTypeBlock');
const settingsRagGraphResponseType = document.getElementById('settingsRagGraphResponseType');
const saveRagParamsBtn = document.getElementById('saveRagParamsBtn');
const settingsStatus_ragParams = document.getElementById('settingsStatus_ragParams');

const friendsMessagesBtn = document.getElementById('friendsMessagesBtn');
const friendsMessagesModal = document.getElementById('friendsMessagesModal');
const addFriendInput = document.getElementById('addFriendInput');
const sendFriendRequestBtn = document.getElementById('sendFriendRequestBtn');
const addFriendStatus = document.getElementById('addFriendStatus');
const friendsListContainerFM = document.getElementById('friendsListContainerFM');
const pendingRequestsContainer = document.getElementById('pendingRequestsContainer');
const friendRequestsBadge = document.getElementById('friendRequestsBadge');
// directMessagesContainer (if you add specific elements for it later)


// Add to DOM constants
const dmSearchUsersInput = document.getElementById('dmSearchUsersInput');
const dmSearchResults = document.getElementById('dmSearchResults');
const dmConversationsList = document.getElementById('dmConversationsList');
const dmChatArea = document.getElementById('dmChatArea');
const dmChatHeader = document.getElementById('dmChatHeader');
const dmChatMessages = document.getElementById('dmChatMessages');
const dmChatInputContainer = document.getElementById('dmChatInputContainer');
const directMessageInput = document.getElementById('directMessageInput');
const sendDirectMessageBtn = document.getElementById('sendDirectMessageBtn');
const dmSendStatus = document.getElementById('dmSendStatus');
const dmNoConversationSelected = document.getElementById('dmNoConversationSelected');

// DOM Constants
const sendPersonalityModal = document.getElementById('sendPersonalityModal');
const sendPersonalityModalTitle = document.getElementById('sendPersonalityModalTitle');
const sendPersonalityTargetUsername = document.getElementById('sendPersonalityTargetUsername');
const sendPersonalityStatus = document.getElementById('sendPersonalityStatus');
const sendPersonalityIdInput = document.getElementById('sendPersonalityIdInput');
const confirmSendPersonalityBtn = document.getElementById('confirmSendPersonalityBtn');

const chatArea = document.getElementById('chatArea');
const ragControls = document.getElementById('ragControls');



let currentDmPartner = null; // { userId, username }
let dmConversationsCache = [];

// --- Helper: Check if element is in DOM ---
function isElementInDocument(element) {
    return element && document.body.contains(element);
}

function toggleRagGraphResponseTypeVisibility() {
    if (settingsRagUseGraph && settingsRagGraphResponseTypeBlock) {
        console.log("changing visibility")
        settingsRagGraphResponseTypeBlock.style.display = settingsRagUseGraph.checked ? 'block' : 'none';
        console.log(settingsRagGraphResponseTypeBlock.style.display)
    }
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
    } else {
        discussionTitle.textContent = translate('default_discussion_title');
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
        availableLanguages = { 'en': 'English', 'fr': 'Français' }; // Fallback
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
// Ensure these are accessible or passed in if they live elsewhere
// externals: openModal, loginModal, appContainer, appLoadingMessage, currentUser, showStatus, translate, statusMessage

async function apiRequest(url, options = {}) {
    if (!options.statusElement && typeof statusMessage !== 'undefined' && statusMessage) {
        showStatus('', 'info', statusMessage); // Clear global status if statusMessage exists
    }

    const fetchOptions = { ...options };
    fetchOptions.headers = { ...options.headers }; // Clone headers from options

    const token = localStorage.getItem('lollms_chat_accessToken');

    // Add JWT Bearer token if available AND it's not the token acquisition endpoint itself
    if (token && url !== '/api/auth/token') {
        fetchOptions.headers['Authorization'] = `Bearer ${token}`;
    }

    // Automatically set Content-Type for JSON bodies if not FormData and not already set
    if (fetchOptions.body && !(fetchOptions.body instanceof FormData) && typeof fetchOptions.body === 'object') {
        if (!fetchOptions.headers['Content-Type']) {
            fetchOptions.headers['Content-Type'] = 'application/json';
        }
        // Stringify the body if it's an object and Content-Type is application/json
        if (fetchOptions.headers['Content-Type'] === 'application/json') {
             fetchOptions.body = JSON.stringify(fetchOptions.body);
        }
    }
    // Note: If options.body is already a string (e.g. pre-stringified JSON), this won't re-stringify.
    // If options.body is FormData, Content-Type is set automatically by fetch.

    try {
        const response = await fetch(url, fetchOptions);

        if (!response.ok) {
            let errorDetail = `HTTP error ${response.status}`;
            let errorData = null;
            try {
                errorData = await response.json();
                errorDetail = errorData.detail || errorDetail;
            } catch (e) {
                // Error response was not JSON, or other parsing error
                console.warn("Could not parse error response as JSON:", e);
            }

            // Specific handling for 401 Unauthorized (likely expired/invalid token)
            // Do not trigger this for the login attempt itself if it fails with 401
            if (response.status === 401 && url !== '/api/auth/token') {
                console.warn('API request 401: Token invalid or expired. Clearing token and prompting login.');
                localStorage.removeItem('lollms_chat_accessToken');
                if (typeof currentUser !== 'undefined') currentUser = null; // Reset current user state

                // Show login modal and hide app content
                if (typeof openModal === 'function' && typeof loginModal !== 'undefined') {
                    openModal('loginModal', false);
                }
                if (typeof appContainer !== 'undefined' && appContainer) appContainer.style.display = 'none';
                if (typeof appLoadingMessage !== 'undefined' && appLoadingMessage) appLoadingMessage.style.display = 'flex';

                showStatus(
                    translate('session_expired_login_again', "Your session has expired. Please log in again."),
                    "error",
                    options.statusElement || (typeof loginStatus !== 'undefined' ? loginStatus : statusMessage) // Prefer loginStatus for auth errors
                );
            } else {
                // For other errors, show the general error message
                const errorMsg = translate('api_error_prefix', "API Error:") + ` ${errorDetail}`;
                showStatus(errorMsg, "error", options.statusElement || (typeof statusMessage !== 'undefined' ? statusMessage : undefined));
            }

            const error = new Error(errorDetail);
            error.status = response.status;
            error.data = errorData; // Attach parsed error data if available
            throw error;
        }

        if (response.status === 204) return null; // No content

        // Try to parse as JSON, but return the raw response if not JSON
        // This is a slight change from your original which always returned response object.
        // Most of the time you'll want the JSON data.
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
            return response;
        }
        return response; // Return raw response for non-JSON content types (e.g., file downloads)

    } catch (error) {
        if (error.name === 'AbortError') {
            console.log("API Request Aborted:", url);
            if (typeof showStatus === 'function') {
                showStatus(
                    translate('api_request_aborted', "Request aborted by user."),
                    "warning",
                    options.statusElement || (typeof statusMessage !== 'undefined' ? statusMessage : undefined)
                );
            }
        } else if (error.status) { // HTTP error already handled (status set)
            console.error("API Request HTTP Error:", url, error.status, error.message, error.data || '');
        }
        else { // Network error or other exception before/during fetch
            console.error("API Request Network/Generic Error:", url, error);
            if (typeof showStatus === 'function') {
                 showStatus(
                    translate('api_request_failed_prefix', "Request failed:") + ` ${error.message}`,
                    "error",
                    options.statusElement || (typeof statusMessage !== 'undefined' ? statusMessage : undefined)
                );
            }
        }
        throw error; // Re-throw to be handled by the caller
    }
    // The 'finally' block for clearing tempLoginUsername/Password is no longer needed
    // as Basic Auth is not the primary mechanism.
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
    if (friendsMessagesBtn) friendsMessagesBtn.onclick = () => openFriendsMessagesModal();
    
    // Event listeners from your original code
    if (confirmRenameBtn) confirmRenameBtn.onclick = confirmInlineRename;
    if (confirmSendDiscussionBtn) confirmSendDiscussionBtn.onclick = confirmSendDiscussion;
    if (confirmEditMessageBtn) confirmEditMessageBtn.onclick = confirmMessageEdit;
    if (logoutBtn) logoutBtn.onclick = handleLogout;
    if (loginSubmitBtn) loginSubmitBtn.onclick = handleLoginAttempt;
    if (loginPasswordInput) loginPasswordInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') handleLoginAttempt(); });
    if (createDataStoreForm) createDataStoreForm.addEventListener('submit', handleCreateDataStore);
    if (btnOpenCreateStore) btnOpenCreateStore.onclick = () => {
        closeModal('dataStoresModal')
        openModal('createDataStoreModal');
    }
    if (btnCancelCreateDataStore) btnCancelCreateDataStore.onclick = () => {
        closeModal('createDataStoreModal')
        openModal('dataStoresModal');
    }

    if (changePasswordBtn) changePasswordBtn.onclick = handleChangePassword;

    if (editDataStoreForm) editDataStoreForm.addEventListener('submit', handleEditDataStore);
    if (btnCancelEditDataStore) btnCancelEditDataStore.onclick = closeModal("editDataStoresModal");
    
    

    // For Profile Tab
    if (settingsFirstName) settingsFirstName.oninput = () => { if(saveProfileBtn) saveProfileBtn.disabled = false; };
    if (settingsFamilyName) settingsFamilyName.oninput = () => { if(saveProfileBtn) saveProfileBtn.disabled = false; };
    if (settingsEmail) settingsEmail.oninput = () => { if(saveProfileBtn) saveProfileBtn.disabled = false; };
    if (settingsBirthDate) settingsBirthDate.oninput = () => { if(saveProfileBtn) saveProfileBtn.disabled = false; };
    if (saveProfileBtn) saveProfileBtn.onclick = handleSaveProfile;

    // For Personalities Tab
    if (settingsActivePersonality) settingsActivePersonality.onchange = () => { if(saveActivePersonalityBtn) saveActivePersonalityBtn.disabled = false; };
    if (saveActivePersonalityBtn) saveActivePersonalityBtn.onclick = handleSaveActivePersonality;
    if (createNewPersonalityBtn) createNewPersonalityBtn.onclick = () => openPersonalityEditor(null); // null for new
    if (savePersonalityBtn) savePersonalityBtn.onclick = handleSavePersonality;
    if (personalityIconUpload) personalityIconUpload.onchange = handlePersonalityIconChange;


    // For LLM Params Tab (put_thoughts_in_context)
    if (settingsPutThoughts) settingsPutThoughts.onchange = () => { if(saveLLMParamsBtn) saveLLMParamsBtn.disabled = false; };
    if (confirmSendPersonalityBtn) confirmSendPersonalityBtn.onclick = handleConfirmSendPersonality;

    // For RAG Params Tab
    if (settingsRagTopK) settingsRagTopK.oninput = () => { if(saveRagParamsBtn) saveRagParamsBtn.disabled = false; };
    if (settingsRagNBHops) settingsRagNBHops.oninput = () => { if(saveRagParamsBtn) saveRagParamsBtn.disabled = false; };
    if (settingsRagMAXLEN) settingsRagMAXLEN.oninput = () => { if(saveRagParamsBtn) saveRagParamsBtn.disabled = false; };
    if (settingsRagMinSimPercent) settingsRagMinSimPercent.oninput = () => { if(saveRagParamsBtn) saveRagParamsBtn.disabled = false; };
    if (settingsRagUseGraph) {
        settingsRagUseGraph.onchange = () => { 
            console.log("Changing graphrag status")
            if(saveRagParamsBtn) saveRagParamsBtn.disabled = false; 
            toggleRagGraphResponseTypeVisibility(); // Call on change
        };
    }
    if (settingsRagGraphResponseType) settingsRagGraphResponseType.onchange = () => { if(saveRagParamsBtn) saveRagParamsBtn.disabled = false; };
    if (saveRagParamsBtn) saveRagParamsBtn.onclick = handleSaveRagParams;  
    
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
    
    document.querySelectorAll('#friendsMessagesModal .friends-messages-tab-btn').forEach(button => {
        button.addEventListener('click', () => handleFriendsMessagesTabSwitch(button.dataset.tab));
    });
    if (sendFriendRequestBtn) sendFriendRequestBtn.onclick = handleSendFriendRequest;
    if (dmSearchUsersInput) {
        dmSearchUsersInput.addEventListener('input', debounce(handleDmUserSearch, 300));
        dmSearchUsersInput.addEventListener('focus', () => { if(dmSearchResults.children.length > 0) dmSearchResults.classList.remove('hidden'); });
    }
    // Hide search results when clicking outside
    document.addEventListener('click', (event) => {
        if (dmSearchUsersInput && dmSearchResults && !dmSearchUsersInput.contains(event.target) && !dmSearchResults.contains(event.target)) {
            dmSearchResults.classList.add('hidden');
        }
    });
    if (sendDirectMessageBtn) sendDirectMessageBtn.onclick = handleSendDirectMessage;
    if (directMessageInput) directMessageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendDirectMessage();
        }
    });

    function debounce(func, delay) {
        let timeout;
        return function(...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), delay);
        };
    }
    
    // RAG Toggle
    if (ragToggleBtn) ragToggleBtn.onclick = () => {
        if (!currentDiscussionId) {
            showStatus(translate('status_select_discussion_first_warning'), 'warning');
            return;
        }
        if (availableDataStoresForRag.length === 0) {
            showStatus(translate('rag_cannot_enable_no_stores_warning'), 'warning');
            return;
        }
        const disc = discussions[currentDiscussionId];
        const isCurrentlyOn = !!disc.rag_datastore_id;
        let newRagDatastoreId = null;

        if (isCurrentlyOn) {
            newRagDatastoreId = null; // Turn it off
        } else {
            newRagDatastoreId = ragDataStoreSelect.value || (availableDataStoresForRag[0] ? availableDataStoresForRag[0].id : null);
        }
        
        disc.rag_datastore_id = newRagDatastoreId;
        updateDiscussionRagStoreOnBackend(currentDiscussionId, newRagDatastoreId);
        updateRagToggleButtonState();
        
        const ragStatusMessage = newRagDatastoreId ? translate('status_rag_active') : translate('status_rag_inactive');
        showStatus(ragStatusMessage, 'info');
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
    if(saveLLMParamsBtn) saveLLMParamsBtn.onclick = handleSaveModelAndVectorizer;


    // Initial render of empty chat area (if applicable)
    if (!currentDiscussionId && chatMessages) {
        chatMessages.innerHTML = `<div class="text-center text-gray-500 italic mt-10">${translate('chat_area_empty_placeholder')}</div>`;
    }
};

// --- Theme Management Functions ---
function applyTheme(theme) { /* As provided */
    if (theme === 'dark') {
        document.documentElement.classList.add('dark');
        if (themeIconMoon) themeIconMoon.classList.remove('hidden');
        if (themeIconSun) themeIconSun.classList.add('hidden');
    } else {
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


// --- Authentication Logic ---
async function handleLoginAttempt() {
    console.log("Attempting JWT login");

    const username = loginUsernameInput.value.trim();
    const password = loginPasswordInput.value;

    if (!username || !password) {
        showStatus(translate('login_username_password_required', "Username and password are required."), "error", loginStatus);
        return;
    }

    showStatus(translate('login_attempting_status', "Attempting login..."), "info", loginStatus);
    loginSubmitBtn.disabled = true;

    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    try {
        let data = await apiRequest('/api/auth/token', {
            method: 'POST',
            body: formData, // FormData is not JSON, apiRequest handles it
            statusElement: loginStatus
        });
        data = await data.json();
        if (data && data.access_token) {
            localStorage.setItem('lollms_chat_accessToken', data.access_token);
            showStatus(translate('login_successful_status', "Login successful! Loading your data..."), "success", loginStatus);
            // Now that token is stored, attempt to load user data and initialize app
            await attemptInitialAuthAndLoad(); // This function will now use the token via apiRequest
            window.location.reload();
        } else {
            // Should be caught by apiRequest's !response.ok if server returns non-200
            // but as a safeguard:
            showStatus(translate('login_failed_no_token', "Login failed: No token received."), "error", loginStatus);
        }
    } catch (error) {
        console.error("Login error:", error);
        let message = translate('login_error_status', `Login error: ${error.message}`, { message: error.message });
        if (error.status === 401) { // Specifically for /api/auth/token failing
            message = translate('login_invalid_credentials', "Invalid username or password.");
        }
        showStatus(message, "error", loginStatus);
    } finally {
        loginSubmitBtn.disabled = false;
    }
}

async function handleLogout() {
    showStatus(translate('logout_status_logging_out', "Logging out..."), "info", loginStatus); // Use loginStatus for consistency
    console.log("Current token before logout:", localStorage.getItem('lollms_chat_accessToken'));

    try {
        // The apiRequest function will automatically include the Authorization header
        await apiRequest('/api/auth/logout', { method: 'POST' });
        showStatus(translate('logout_server_success', "Logged out from server."), "info", loginStatus);
    } catch (error) {
        console.warn('Logout from server failed or user was already unauthenticated:', error);
        showStatus(
            translate('logout_server_failed_status', "Server logout acknowledged or failed, resetting UI."),
            "warning",
            loginStatus
        );
    } finally {
        localStorage.removeItem('lollms_chat_accessToken'); // <<< MOST IMPORTANT STEP FOR JWT LOGOUT
        currentUser = null;
        discussions = {};
        currentMessages = [];
        currentDiscussionId = null;

        aiMessageStreaming = false;
        currentAiMessageContainer = null;
        currentAiMessageContentAccumulator = "";
        currentAiMessageId = null;
        currentAiMessageData = null;

        isRagActive = false;
        uploadedImageServerPaths = [];

        ownedDataStores = [];
        sharedDataStores = [];
        availableDataStoresForRag = [];

        generationInProgress = false;
        if (activeGenerationAbortController) {
            activeGenerationAbortController.abort();
        }
        usernameDisplay.textContent =
            translate('username_display_default');
        adminBadge.style.display = 'none';
        adminLink.style.display = 'none';

        discussionListContainer.innerHTML = `
            <p class="text-gray-500 text-sm text-center italic p-4">
                ${translate('login_required_placeholder')}
            </p>
        `;

        clearChatArea(true);
        sendMessageBtn.disabled = true;
        messageInput.value = '';
        autoGrowTextarea(messageInput);

        ragToggleBtn.classList.remove('rag-toggle-on');
        ragToggleBtn.classList.add('rag-toggle-off');

        ragDataStoreSelect.style.display = 'none';
        ragDataStoreSelect.innerHTML = `
            <option value="">${translate('rag_select_default_option')}</option>
        `;

        imageUploadPreviewContainer.innerHTML = '';
        imageUploadPreviewContainer.style.display = 'none';

        updateRagToggleButtonState();

        userMenuDropdown.style.display = 'none';
        userMenuArrow.classList.remove('rotate-180');

        appContainer.style.display = 'none';
        appLoadingMessage.style.opacity = '1';
        appLoadingMessage.style.display = 'flex';
        appLoadingProgress.style.width = '0%';
        appLoadingStatus.textContent =
            translate('app_loading_status_default');

        showStatus('', 'info', statusMessage);
        showStatus('', 'info', pyodideStatus);

        loginUsernameInput.value = '';
        loginPasswordInput.value = '';
        loginSubmitBtn.disabled = false;

        usernameDisplay.textContent = translate('username_display_default');
        adminBadge.style.display = 'none';
        adminLink.style.display = 'none';
        discussionListContainer.innerHTML = `<p class="text-gray-500 text-sm text-center italic p-4">${translate('login_required_placeholder')}</p>`;
        clearChatArea(true);
        sendMessageBtn.disabled = true;

        appContainer.style.display = 'none';
        // appLoadingMessage.style.opacity = '1'; // This might be your login screen container
        //appLoadingMessage.style.display = 'flex';
        // appLoadingProgress.style.width = '0%';
        // appLoadingStatus.textContent = translate('app_loading_status_default');

        loginUsernameInput.value = '';
        loginPasswordInput.value = '';
        loginSubmitBtn.disabled = false;

        showStatus(
            translate('logout_success_status', "You have been logged out."),
            "info",
            loginStatus
        );
        window.location.reload(); // Reload can be an option for a very thorough reset,
                                   // but a good SPA reset should make it unnecessary.
                                   // If you keep it, it ensures no old state lingers.
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
    else{
        console.error("Unknown modal")
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
                activeBranchId: d_info.active_branch_id || 'main', // Use from backend if available
                messages_loaded_fully: {} // Per-branch loading status: { branchId: boolean }
            };
            // Detect branching support from the API response
            if (!backendCapabilities.checked && typeof d_info.active_branch_id === 'string') {
                backendCapabilities.supportsBranches = true;
            }
        });
        
        // Mark capability check as done after processing the list
        backendCapabilities.checked = true;

        renderDiscussionList();
        if (currentDiscussionId && discussions[currentDiscussionId]) {
            await selectDiscussion(currentDiscussionId); // Reselect if one was active
        } else if (currentDiscussionId) { // Was active, but now gone
            clearChatArea(true); 
            currentDiscussionId = null;
        }
    } catch (error) {
        if (discussionListContainer) discussionListContainer.innerHTML = `<p class="text-red-500 text-sm text-center p-4">${translate('failed_to_load_discussions_error')}</p>`;
    }
}
function initiateInlineRename(id) {
    const discussion = discussions[id];
    if (!discussion) return;

    const renameInput = document.getElementById('renameInput');
    const renameDiscussionIdInput = document.getElementById('renameDiscussionIdInput');
    const confirmRenameBtn = document.getElementById('confirmRenameBtn');
    const cancelRenameBtn = document.getElementById('cancelRenameBtn');

    // Set the initial values
    renameInput.value = discussion.title;
    renameDiscussionIdInput.value = id;

    console.log("Showing rename modal")
    // Show the modal
    openModal("renameModal", false);

    // Event listener for the confirm button
    confirmRenameBtn.onclick = async () => {
        await confirmInlineRename();
    };

    // Event listener for the cancel button
    cancelRenameBtn.onclick = () => {
        closeModal('renameModal');
    };
}
async function confirmInlineRename() {
    const idToRename = renameDiscussionIdInput.value;
    if (!idToRename || !discussions[idToRename]) return;

    const newTitle = renameInput.value.trim();
    if (!newTitle) {
        showStatus(translate('rename_title_empty_error'), 'error', renameStatus);
        return;
    }

    showStatus(translate('status_renaming', 'Renaming...'), 'info', renameStatus);

    try {
        const response = await apiRequest(`/api/discussions/${idToRename}/title`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: newTitle }),
            statusElement: renameStatus
        });

        const updatedInfo = await response.json(); // This is DiscussionInfo
        discussions[idToRename].title = updatedInfo.title;
        discussions[idToRename].last_activity_at = updatedInfo.last_activity_at || new Date().toISOString();

        if (idToRename === currentDiscussionId && discussionTitle) {
            discussionTitle.textContent = updatedInfo.title;
        }

        renderDiscussionList();
        showStatus(translate('status_renamed_success', 'Renamed successfully.'), 'success', renameStatus);
        setTimeout(() => closeModal('renameModal'), 1000);
    } catch (error) {
        // Handled by apiRequest
    }
}

function createDiscussionItemElement(d) {
    const item = document.createElement('div');
    item.className = `discussion-item p-2.5 rounded-lg cursor-pointer flex justify-between items-center text-sm transition-colors duration-150 ${d.id === currentDiscussionId ? 'bg-blue-700 font-medium text-blue-100 hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-500' : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'}`;
    item.dataset.id = d.id;
    item.onclick = () => selectDiscussion(d.id);

    const titleSpan = document.createElement('span');
    titleSpan.textContent = d.title || translate('untitled_discussion_prefix', `Discussion ${d.id.substring(0, 6)}`, {id_short: d.id.substring(0,6)});
    titleSpan.className = 'truncate mr-2 flex-1 text-xs';

    const controlsDiv = document.createElement('div');
    controlsDiv.className = 'flex items-center flex-shrink-0';

    const actionsContainer = document.createElement('div');
    actionsContainer.className = 'discussion-item-actions-container';

    const sendBtn = document.createElement('button');
    sendBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" /></svg>`;
    sendBtn.title = translate('send_discussion_tooltip');
    sendBtn.className = 'discussion-action-btn';
    sendBtn.onclick = (e) => { e.stopPropagation(); initiateSendDiscussion(d.id); };
    actionsContainer.appendChild(sendBtn);

    const renameBtn = document.createElement('button');
    renameBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125" /></svg>`;
    renameBtn.title = translate('rename_discussion_tooltip');
    renameBtn.className = 'discussion-action-btn';
    renameBtn.onclick = (e) => { e.stopPropagation(); initiateInlineRename(d.id); };
    actionsContainer.appendChild(renameBtn);

    const deleteBtn = document.createElement('button');
    deleteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12.508 0A48.067 48.067 0 0 1 7.8 5.397m7.454 0M12 10.75h.008v.008H12v-.008Z" /></svg>`;
    deleteBtn.title = translate('delete_discussion_tooltip');
    deleteBtn.className = 'discussion-action-btn destructive';
    deleteBtn.querySelector('svg')?.classList.add('text-red-500', 'dark:text-red-400');
    deleteBtn.onclick = (e) => { e.stopPropagation(); deleteInlineDiscussion(d.id); };
    actionsContainer.appendChild(deleteBtn);

    controlsDiv.appendChild(actionsContainer);

    const starSpan = document.createElement('button');
    starSpan.className = `discussion-action-btn p-1 ml-1 star-icon ${d.is_starred ? 'starred' : ''}`;
    starSpan.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="${d.is_starred ? 'currentColor' : 'none'}" viewBox="0 0 24 24" stroke-width="1.5" stroke="${d.is_starred ? 'none' : 'currentColor'}" class="w-4 h-4 transition-colors duration-150"><path stroke-linecap="round" stroke-linejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 21.1a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" /></svg>`;
    starSpan.title = d.is_starred ? translate('unstar_discussion_tooltip') : translate('star_discussion_tooltip');
    
    // --- BUG FIX IS HERE ---
    // Removed the premature renderDiscussionList() call. The toggleStarDiscussion function
    // will now handle re-rendering on its own after the API call completes.
    starSpan.onclick = (e) => { e.stopPropagation(); toggleStarDiscussion(d.id, d.is_starred); };
    // --- END BUG FIX ---

    actionsContainer.appendChild(starSpan);

    item.appendChild(titleSpan);
    item.appendChild(controlsDiv);
    return item;
}
function renderDiscussionList() {
    if (!discussionListContainer || !discussions) return;
    discussionListContainer.innerHTML = '';
    const searchTerm = discussionSearchInput ? discussionSearchInput.value.toLowerCase() : "";
    const allDiscussionValues = Object.values(discussions);

    const filteredDiscussions = searchTerm
        ? allDiscussionValues.filter(d => (d.title || '').toLowerCase().includes(searchTerm))
        : allDiscussionValues;

    // --- NEW: Dynamic Sorting Logic ---
    const sortFunctions = {
        'date_desc': (a, b) => new Date(b.last_activity_at || 0) - new Date(a.last_activity_at || 0),
        'date_asc': (a, b) => new Date(a.last_activity_at || 0) - new Date(b.last_activity_at || 0),
        'title_asc': (a, b) => (a.title || '').localeCompare(b.title || ''),
        'title_za': (a, b) => (b.title || '').localeCompare(a.title || '')
    };

    // Get the selected sort function, with a fallback to the default
    const selectedSortFunction = sortFunctions[currentSortMethod] || sortFunctions['date_desc'];

    const starredDiscussions = filteredDiscussions.filter(d => d.is_starred).sort(selectedSortFunction);
    const regularDiscussions = filteredDiscussions.filter(d => !d.is_starred).sort(selectedSortFunction);
    // --- END: Dynamic Sorting Logic ---


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
        
        // Initialize with the new branching structure
        discussions[newDiscussionInfo.id] = {
            id: newDiscussionInfo.id,
            title: newDiscussionInfo.title,
            is_starred: newDiscussionInfo.is_starred,
            rag_datastore_id: newDiscussionInfo.rag_datastore_id,
            last_activity_at: newDiscussionInfo.last_activity_at || new Date().toISOString(),
            branches: { main: [] }, // Initialize with an empty main branch
            activeBranchId: 'main',
            messages_loaded_fully: { main: true } // New discussion starts with a "fully loaded" empty main branch
        };
        
        renderDiscussionList();
        await selectDiscussion(newDiscussionInfo.id); // selectDiscussion now handles branches
        showStatus(translate('status_new_discussion_created', 'New discussion created.'), 'success');
    } catch (error) { /* apiRequest handles showing status */ }
};

/**
 * CORRECTED: Processes a list of messages to distribute branch information to all
 * sibling messages. When a message has multiple responses (branches), the backend
 * might only attach the list of branch IDs to one of them. This function ensures
 * that *all* messages in that sibling group receive the same list of branches,
 * so they can all render the navigation UI correctly.
 *
 * @param {Array<object>} rawMessages The list of messages as received from the API.
 * @returns {Array<object>} A new list of messages with branch data correctly distributed.
 */
function processAndDistributeBranches(rawMessages) {
    if (!rawMessages || rawMessages.length === 0) {
        return [];
    }
    console.log("Processing branches")
    // Create a mutable map of messages for efficient lookups and updates.
    const messageMap = new Map(rawMessages.map(msg => [msg.id, { ...msg }]));

    // Find any message that contains the "source of truth" branches array.
    for (const message of messageMap.values()) {
        if (message.branches && message.branches.length > 1) {
            
            // This is the list of all sibling IDs for this group.
            const siblingBranchIds = message.branches;

            // Now, iterate through this list and ensure every sibling has this same array.
            for (const siblingId of siblingBranchIds) {
                const siblingMessage = messageMap.get(siblingId);
                
                // If the sibling exists in our current message list...
                if (siblingMessage) {
                    //...assign the complete list of branches to it.
                    siblingMessage.branches = siblingBranchIds;
                }
            }
        }
    }
    
    // Return the corrected list of messages from the map.
    return Array.from(messageMap.values());
}

async function selectDiscussion(id) {
    if (!discussions[id] || aiMessageStreaming) return;

    currentDiscussionId = id;
    // CRITICAL: Define discussionData here, at the top level of the function.
    // This ensures it is available in the try, catch, and finally blocks.
    const discussionData = discussions[id];

    if (!discussionData.branches) discussionData.branches = { main: [] };
    if (!discussionData.activeBranchId) discussionData.activeBranchId = 'main';
    if (!discussionData.branch_map) discussionData.branch_map = {}; // Initialize the map

    let branchToLoad = discussionData.activeBranchId;
    activeBranchId = branchToLoad;
    currentMessages = discussionData.branches[branchToLoad] || [];

    if (discussionTitle) discussionTitle.textContent = discussionData.title;
    if (sendMessageBtn) sendMessageBtn.disabled = generationInProgress;
    renderDiscussionList();
    clearChatArea(false);
    if (chatMessages) chatMessages.innerHTML = `<p class="text-gray-500 dark:text-gray-400 text-center italic mt-10">${translate('chat_area_loading_messages')}</p>`;
    
    updateRagToggleButtonState();

    // Use the tip ID from the map if we already know it.
    const knownTipId = discussionData.branch_map[branchToLoad];
    if (knownTipId && discussionData.messages_loaded_fully[knownTipId]) {
         branchToLoad = knownTipId;
         discussionData.activeBranchId = knownTipId;
         activeBranchId = knownTipId;
         currentMessages = discussionData.branches[knownTipId] || [];
    }
    
    if (!discussionData.messages_loaded_fully || !discussionData.messages_loaded_fully[branchToLoad]) {
        try {
            const messagesResponse = await apiRequest(`/api/discussions/${id}?branch_id=${branchToLoad}`);
            const loadedMessages = await messagesResponse.json();

            // Distribute branch info to all sibling messages in a group.
            const distributedMessages = processAndDistributeBranches(loadedMessages);
            const processedMessages = distributedMessages.map(msg => ({ ...msg, steps: msg.steps || [], metadata: msg.metadata || [] }));

            if (processedMessages.length > 0) {
                const actualTipId = processedMessages[processedMessages.length - 1].id;
                
                discussionData.branch_map[branchToLoad] = actualTipId;
                
                if (branchToLoad !== actualTipId) {
                    discussionData.activeBranchId = actualTipId;
                    activeBranchId = actualTipId;
                }
                
                discussionData.branches[actualTipId] = processedMessages;
                currentMessages = processedMessages;
                discussionData.messages_loaded_fully[actualTipId] = true;

                const lastMessage = currentMessages[currentMessages.length - 1];
                if (lastMessage.created_at && new Date(lastMessage.created_at) > new Date(discussionData.last_activity_at || 0)) {
                    discussionData.last_activity_at = lastMessage.created_at;
                    renderDiscussionList();
                }

            } else {
                discussionData.branches[branchToLoad] = [];
                currentMessages = [];
                discussionData.messages_loaded_fully[branchToLoad] = true;
            }
        } catch (error) {
            if (chatMessages) chatMessages.innerHTML = `<p class="text-red-500 dark:text-red-400 text-center py-10">${translate('chat_area_error_loading_messages')}</p>`;
            // This line now works correctly because discussionData is in scope.
            discussionData.messages_loaded_fully[branchToLoad] = false;
        }
    }
    
    renderMessages(currentMessages);
    chatArea.classList.remove("hidden");
    ragControls.classList.remove("hidden");
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
    if (!discussions[id]) return;

    const originalStarredState = discussions[id].is_starred;

    // --- 1. Optimistic Update ---
    // Immediately update the local data and re-render the list for a snappy UI.
    discussions[id].is_starred = !isCurrentlyStarred;
    discussions[id].last_activity_at = new Date().toISOString(); // Update activity time to help with sorting
    renderDiscussionList();

    // --- 2. Sync with Server ---
    // Perform the API request in the background.
    const method = isCurrentlyStarred ? 'DELETE' : 'POST';
    try {
        const response = await apiRequest(`/api/discussions/${id}/star`, { method: method });
        // After success, we can optionally re-sync the state from the server's response
        // to ensure consistency, though it's not strictly necessary if the API is reliable.
        const updatedInfo = await response.json();
        discussions[id].is_starred = updatedInfo.is_starred;
        discussions[id].last_activity_at = updatedInfo.last_activity_at || discussions[id].last_activity_at;

        // We can do a final re-render to be perfectly in sync, though often it's not visually noticeable
        // renderDiscussionList(); 

    } catch (error) {
        // --- 3. Rollback on Error ---
        // If the API call fails, revert the change and notify the user.
        showStatus(translate(isCurrentlyStarred ? 'status_unstar_failed' : 'status_star_failed', `Failed to ${isCurrentlyStarred ? 'unstar' : 'star'} discussion.`), 'error');
        
        discussions[id].is_starred = originalStarredState; // Revert to the original state
        renderDiscussionList(); // Re-render again to show the reverted state
    }
}

// --- Chat Interaction ---

function autoGrowTextarea(element) { 
    element.style.height = 'auto';
    const maxHeight = 200;
    element.style.height = Math.min(element.scrollHeight, maxHeight) + 'px';
    element.style.overflowY = element.scrollHeight > maxHeight ? 'auto' : 'hidden';
}

/**
 * Checks if a container is scrolled to the bottom.
 * A small threshold is used for leniency.
 * @param {HTMLElement} el The container element.
 * @returns {boolean} True if scrolled to the bottom.
 */
function isScrolledToBottom(el) {
    if (!el) return false;
    const threshold = 15; // px
    return el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
}

/**
 * Scrolls the chat to the bottom only if the user is already there.
 * This prevents interrupting a user who has scrolled up to read.
 */
function smartScrollToBottom() {
    const chatContainer = document.getElementById('chatMessages');
    if (chatContainer && isScrolledToBottom(chatContainer)) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
}

/**
 * Forces the chat container to scroll to the very bottom.
 * Used when a user sends a message or a full history is loaded.
 */
function forceScrollToBottom() {
    const chatContainer = document.getElementById('chatMessages');
    if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
}

async function sendMessage(branchFromUserMessageId = null, resendData = null) {
    if (generationInProgress || !currentDiscussionId) return;

    const currentDisc = discussions[currentDiscussionId];
    if (!currentDisc || !currentDisc.branches || !currentDisc.branches[activeBranchId]) {
        showStatus(translate('error_active_discussion_branch_missing', "Error: Active discussion branch missing."), "error");
        return;
    }
    currentMessages = currentDisc.branches[activeBranchId];

    let prompt;
    let imagePayloadForBackend = [];

    if (resendData) {
        prompt = resendData.prompt;
        imagePayloadForBackend = resendData.image_server_paths || [];
    } else {
        prompt = messageInput.value.trim();
        imagePayloadForBackend = uploadedImageServerPaths.map(img => img.server_path);
        if (!prompt && imagePayloadForBackend.length === 0) return;
    }

    generationInProgress = true;
    activeGenerationAbortController = new AbortController();
    if (sendMessageBtn) sendMessageBtn.style.display = 'none';
    if (stopGenerationBtn) { stopGenerationBtn.style.display = 'inline-flex'; stopGenerationBtn.disabled = false; }

    if (!resendData) {
        const tempUserMessageId = `temp-user-${Date.now()}`;
        const userMessageData = {
            id: tempUserMessageId,
            sender: currentUser.username || 'User',
            content: prompt,
            user_grade: 0, token_count: null, model_name: null,
            image_references: uploadedImageServerPaths.map(img => URL.createObjectURL(img.file_obj)),
            server_image_paths: imagePayloadForBackend,
            steps: [], metadata: [],
            created_at: new Date().toISOString(),
            branch_id: activeBranchId,
            discussion_id: currentDiscussionId
        };
        currentMessages.push(userMessageData);
        renderMessage(userMessageData);
    }
    const useRag = !!(currentDisc && currentDisc.rag_datastore_id);
    const formData = new FormData();
    formData.append('prompt', prompt);
    formData.append('image_server_paths_json', JSON.stringify(imagePayloadForBackend));
    formData.append('use_rag', useRag.toString());
    if (useRag && currentDisc.rag_datastore_id) {
        formData.append('rag_datastore_id', currentDisc.rag_datastore_id);
    }

    const isBranchingOrResending = !!(resendData || branchFromUserMessageId);
    if (backendCapabilities.supportsBranches && isBranchingOrResending) {
        formData.append('is_resend', 'true');
        formData.append('branch_from_message_id', branchFromUserMessageId);
    } else {
        formData.append('is_resend', 'false');
    }

    if (!resendData) {
        if (messageInput) messageInput.value = '';
        uploadedImageServerPaths = [];
        if (imageUploadPreviewContainer) {
            imageUploadPreviewContainer.innerHTML = '';
            imageUploadPreviewContainer.style.display = 'none';
        }
        if (messageInput) autoGrowTextarea(messageInput);
    }
    forceScrollToBottom();

    aiMessageStreaming = true;
    currentAiMessageContentAccumulator = "";
    currentAiMessageId = `temp-ai-${Date.now()}`;
    currentAiMessageData = {
        id: currentAiMessageId,
        sender: currentUser.lollms_client_ai_name || 'Assistant',
        content: "", user_grade: 0, token_count: null, model_name: null,
        image_references: [], steps: [], metadata: [],
        created_at: new Date().toISOString(),
        branch_id: activeBranchId,
        discussion_id: currentDiscussionId
    };
    renderMessage(currentAiMessageData);
    currentDisc.last_activity_at = new Date().toISOString();
    renderDiscussionList();

    try {
        const response = await apiRequest(`/api/discussions/${currentDiscussionId}/chat`, {
            method: 'POST',
            body: formData,
            signal: activeGenerationAbortController.signal
        });

        if (!response.ok || !response.body) {
            let errorDetailMessage = `HTTP error ${response.status}`;
            try { const errorData = await response.json(); errorDetailMessage = errorData.detail || errorDetailMessage; } catch (e) {}
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
                    const data = JSON.parse(line);
                    
                    // --- Re-integrated logic from handleStreamChunk ---
                    if (!currentAiMessageData) { return; }

                    if (!isElementInDocument(currentAiMessageDomBubble)) {
                        currentMessages.push(currentAiMessageData);
                        renderMessage(currentAiMessageData);
                        forceScrollToBottom();
                    }
                
                    const bubbleExists = isElementInDocument(currentAiMessageDomBubble);
                
                    switch (data.type) {
                        case 'chunk':
                            currentAiMessageContentAccumulator += data.content;
                            currentAiMessageData.content = currentAiMessageContentAccumulator;
                            if (bubbleExists) {
                                if (currentAiMessageContentAccumulator === data.content) {
                                    const contentDiv = currentAiMessageDomBubble.querySelector('.message-content');
                                    if (contentDiv) {
                                        const typingIndicator = contentDiv.querySelector('.typing-indicator');
                                        if (typingIndicator) typingIndicator.remove();
                                    }
                                }
                                const contentDiv = currentAiMessageDomBubble.querySelector('.message-content');
                                if (contentDiv) renderEnhancedContent(contentDiv, currentAiMessageData.content, currentAiMessageData.id, [], currentAiMessageData.metadata, currentAiMessageData);
                            }
                            break;
                        case 'sources':
                            if (!currentAiMessageData.metadata) currentAiMessageData.metadata = {};
                            currentAiMessageData.metadata.sources = data.sources || [];
                            if (bubbleExists) renderMessage(currentAiMessageData, currentAiMessageDomContainer, currentAiMessageDomBubble);
                            break;
                        case 'step':
                        case 'step_start':
                            currentAiMessageData.steps.push(data);
                            if (bubbleExists) {
                                const contentDiv = currentAiMessageDomBubble.querySelector('.message-content');
                                if (contentDiv) renderOrUpdateSteps(contentDiv, currentAiMessageData.steps);
                            }
                            break;
                        case 'step_end':
                            const stepToUpdate = currentAiMessageData.steps.find(step => step.id === data.id && step.type === 'step_start');
                            if (stepToUpdate) {
                                stepToUpdate.status = 'done';
                                if (data.content) stepToUpdate.content = data.content;
                            } else {
                                currentAiMessageData.steps.push({ ...data, status: 'done', type: 'step_start' });
                            }
                            if (bubbleExists) {
                                const contentDiv = currentAiMessageDomBubble.querySelector('.message-content');
                                if (contentDiv) renderOrUpdateSteps(contentDiv, currentAiMessageData.steps);
                            }
                            break;
                        case 'error':
                            const errorMsgData = {
                                id: `err-stream-${Date.now()}`, sender: 'system',
                                content: translate('llm_error_prefix', `LLM Error: ${data.content}`, { content: data.content }),
                                steps: [], metadata: [], branch_id: activeBranchId, discussion_id: currentDiscussionId
                            };
                            currentMessages.push(errorMsgData);
                            renderMessage(errorMsgData);
                            handleStreamEnd(true);
                            return;
                        case 'info':
                             if (data.content === "Generation stopped by user.") {
                                showStatus(translate('status_generation_stopped_by_user', 'Generation stopped by user.'), 'info');
                             }
                             break;
                    }
                    if (bubbleExists) smartScrollToBottom();
                    // --- End of re-integrated logic ---

                } catch (e) {
                    console.error("sendMessage: Error parsing stream line:", line, e);
                }
            });
        }
        if (generationInProgress) handleStreamEnd(false);
    } catch (error) {
        if (error.name === 'AbortError') {
            if (generationInProgress) handleStreamEnd(true, true);
        } else {
            if (generationInProgress) handleStreamEnd(true);
        }
    } finally {
        if (generationInProgress) generationInProgress = false;
        if(sendMessageBtn) sendMessageBtn.style.display = 'inline-flex';
        if(stopGenerationBtn) stopGenerationBtn.style.display = 'none';
        if(sendMessageBtn && messageInput) sendMessageBtn.disabled = !(messageInput.value.trim() || uploadedImageServerPaths.length > 0);
        activeGenerationAbortController = null;
    }
}
/**
 * Finalizes the UI after a chat stream ends, either by completion, error, or user cancellation.
 * It ensures the final state of the AI message bubble is rendered correctly with all its data.
 *
 * @param {boolean} [errorOccurred=false] - True if the stream ended due to an error.
 * @param {boolean} [wasAbortedByStopButton=false] - True if the user explicitly clicked the stop button.
 */
function handleStreamEnd(errorOccurred = false, wasAbortedByStopButton = false) {
    aiMessageStreaming = false;
    if (generationInProgress) generationInProgress = false;

    // --- Core Fix ---
    // If we have the streaming message data and its DOM element exists, do one final, full re-render.
    // This call to renderMessage() will correctly display all accumulated data:
    // - Final content from the accumulator.
    // - Sources received from the 'sources' event.
    // - Steps, ratings, and all other metadata.
    if (currentAiMessageData && isElementInDocument(currentAiMessageDomBubble)) {
        renderMessage(currentAiMessageData, currentAiMessageDomContainer, currentAiMessageDomBubble);
        // Clean up streaming-specific states on the bubble.
        currentAiMessageDomBubble.classList.remove('is-streaming');
        currentAiMessageDomBubble.querySelectorAll('.message-footer button').forEach(btn => btn.disabled = false);
    }
    
    // Schedule a full refresh from the server to get canonical message IDs and branch states.
    setTimeout(() => refreshMessagesAfterStream(), 100);

    // Clean up all temporary streaming state variables.
    currentAiMessageContentAccumulator = "";
    currentAiMessageData = null;
    currentAiMessageId = null;
    currentAiMessageDomContainer = null;
    currentAiMessageDomBubble = null;

    // Restore UI button states.
    if(sendMessageBtn) sendMessageBtn.style.display = 'inline-flex';
    if(stopGenerationBtn) stopGenerationBtn.style.display = 'none';
    if(sendMessageBtn && messageInput) sendMessageBtn.disabled = !(messageInput.value.trim() || uploadedImageServerPaths.length > 0);

    // Show a status message if the generation was manually stopped.
    if (wasAbortedByStopButton) {
        showStatus(translate('status_generation_process_halted', 'Generation process halted.'), 'info');
    }
}
/**
 * Displays the content of a RAG source document in a modal, styled with Tailwind CSS
 * and supporting dark mode.
 * @param {object} source The source object containing document, similarity, and content.
 * @param {string} messageId The ID of the message the source belongs to, for creating a unique modal ID.
 */
function showSourceModal(source, messageId) {
    // Generate a unique ID for the modal to prevent duplicates.
    const modalId = `source-modal-${messageId}-${source.document.replace(/[^a-zA-Z0-9]/g, '')}`;
    if (document.getElementById(modalId)) return; // Don't open if already open

    // --- Create Modal Elements with Tailwind Classes ---

    // Modal Overlay - THIS IS THE CORRECTED LINE
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 z-50 flex items-center justify-center p-4 opacity-0 transition-opacity duration-300 ease-in-out backdrop-blur-sm';

    // Modal Content Panel
    const modalContent = document.createElement('div');
    modalContent.className = 'relative flex flex-col w-full max-w-3xl max-h-[85vh] p-6 space-y-4 modal-content border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl';

    // Close Button
    const closeButton = document.createElement('button');
    closeButton.innerHTML = '×';
    closeButton.className = 'absolute top-3 right-3 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors text-2xl leading-none';
    closeButton.title = 'Close (Esc)';

    // Header section for Title and Similarity
    const header = document.createElement('div');
    header.className = 'flex-shrink-0'; // Prevents header from shrinking if content is long

    // Title
    const title = document.createElement('h2');
    title.textContent = source.document;
    title.className = 'text-xl font-semibold modal-content';
    
    // Similarity Score
    const similarityP = document.createElement('p');
    similarityP.innerHTML = `${translate('similarity_label', 'Similarity')}: <strong class="font-medium">${Math.round(source.similarity)}%</strong>`;
    similarityP.className = 'text-sm modal-content mt-1';

    // Main Content Area (Scrollable)
    const contentContainer = document.createElement('div');
    contentContainer.className = 'overflow-y-auto pr-2'; // Added padding-right for scrollbar space

    const contentDivModal = document.createElement('div');
    // These classes correctly leverage the Tailwind Typography plugin for markdown styling
    contentDivModal.className = 'markdown-content prose prose-sm max-w-none dark:prose-invert';
    contentDivModal.innerHTML = marked.parse(source.content || `<p><em>${translate('no_content_available', 'No content available.')}</em></p>`);

    // --- Assemble the Modal ---
    header.appendChild(title);
    header.appendChild(similarityP);

    contentContainer.appendChild(contentDivModal);

    modalContent.appendChild(closeButton);
    modalContent.appendChild(header);
    modalContent.appendChild(contentContainer);

    modal.appendChild(modalContent);
    document.body.appendChild(modal);
    
    // --- Animate In and Add Event Listeners ---
    requestAnimationFrame(() => {
        modal.classList.remove('opacity-0');
        modal.classList.add('opacity-100');
    });

    // Event Handlers for Closing
    const closeModalFunc = () => {
        modal.classList.remove('opacity-100');
        modal.classList.add('opacity-0');
        modal.addEventListener('transitionend', () => modal.remove(), { once: true });
        document.removeEventListener('keydown', escapeListener);
    };

    const escapeListener = (e) => { if (e.key === 'Escape') closeModalFunc(); };

    closeButton.onclick = closeModalFunc;
    modal.onclick = (e) => { if (e.target === modal) closeModalFunc(); };
    document.addEventListener('keydown', escapeListener);
}
async function stopGeneration() {
    if (!generationInProgress || !currentDiscussionId) return;

    if(stopGenerationBtn) stopGenerationBtn.disabled = true;
    showStatus(translate('status_stopping_generation', 'Attempting to stop generation...'), 'info');

    if (activeGenerationAbortController) {
        activeGenerationAbortController.abort();
    }
    const wasInProgress = generationInProgress;
    generationInProgress = false; 

    try {
        await apiRequest(`/api/discussions/${currentDiscussionId}/stop_generation`, {
            method: 'POST'
        });
        showStatus(translate('status_stop_signal_sent', 'Stop signal sent to server.'), 'info');
    } catch (error) {
        showStatus(translate('status_stop_signal_failed_client_halted', `Stop signal to server failed, but client generation halted. ${error.message}`), 'warning');
    } finally {
        if (wasInProgress) {
            handleStreamEnd(false, true);
        }
        if(sendMessageBtn) sendMessageBtn.style.display = 'inline-flex';
        if(stopGenerationBtn) { stopGenerationBtn.style.display = 'none'; stopGenerationBtn.disabled = false; }
        if(sendMessageBtn && messageInput) sendMessageBtn.disabled = !(messageInput.value.trim() || uploadedImageServerPaths.length > 0);
        smartScrollToBottom();
    }
}

/**
 * Fetches the latest message list for the current branch after a stream ends.
 * This ensures the UI is in sync with the server, including message IDs and branch data.
 * @param {string|null} lastStreamedAiMessageId The ID of the message that just finished streaming.
 */
async function refreshMessagesAfterStream(lastStreamedAiMessageId = null) {
    if (!currentDiscussionId || aiMessageStreaming || generationInProgress) {
        return;
    }

    const currentDisc = discussions[currentDiscussionId];
    if (!currentDisc) {
        return;
    }

    // A small delay to allow the backend to fully commit the new messages.
    await new Promise(resolve => setTimeout(resolve, 250));

    try {
        // First, get the latest state of discussions to find the true active branch ID.
        // This is important because a regeneration might have changed it.
        const discussionsResponse = await apiRequest('/api/discussions');
        const allDiscs = await discussionsResponse.json();
        const updatedDiscInfo = allDiscs.find(d => d.id === currentDiscussionId);
        
        if (updatedDiscInfo) {
            // Update our local cache of the active branch ID.
            currentDisc.activeBranchId = updatedDiscInfo.active_branch_id || currentDisc.activeBranchId;
        }

        // --- THE FIX IS HERE ---
        // Define `branchToFetch` using the up-to-date activeBranchId from our discussion object.
        const branchToFetch = currentDisc.activeBranchId;

        // Now, fetch the messages for that specific branch.
        const messagesResponse = await apiRequest(`/api/discussions/${currentDiscussionId}?branch_id=${branchToFetch}`);
        const loadedMessagesRaw = await messagesResponse.json();

        if (!Array.isArray(loadedMessagesRaw)) {
             console.error("API did not return a valid list of messages for the branch.", loadedMessagesRaw);
             throw new Error("Invalid message data received from server.");
        }
        
        // Distribute branch info to all sibling messages in a group.
        const distributedMessages = processAndDistributeBranches(loadedMessagesRaw);
        const processedMessages = distributedMessages.map(msg => ({ ...msg, steps: msg.steps || [], metadata: msg.metadata || [] }));

        // Update the client-side cache with the fully confirmed data.
        currentDisc.branches[branchToFetch] = processedMessages;
        currentDisc.messages_loaded_fully[branchToFetch] = true;
        currentMessages = processedMessages;

        // Re-render the chat and discussion list with the fresh data.
        renderMessages(currentMessages);
        renderDiscussionList();
    } catch (error) {
        console.error("Error refreshing messages after stream:", error);
        showStatus("Could not refresh discussion state. Please select it again.", "error");
    }
}

// --- Message Rendering and Helpers ---
function clearChatArea(clearHeader = true) {
    if (chatMessages) {
        chatMessages.innerHTML = '';
    }
    if (clearHeader) {
        if (discussionTitle) {
            discussionTitle.textContent = translate('default_discussion_title');
        }
        if (sendMessageBtn) {
            sendMessageBtn.disabled = true;
        }
        if (ragToggleBtn) {
            ragToggleBtn.classList.remove('rag-toggle-on');
            ragToggleBtn.classList.add('rag-toggle-off');
        }
        if (ragDataStoreSelect) {
            ragDataStoreSelect.style.display = 'none';
            ragDataStoreSelect.value = '';
        }
        updateRagToggleButtonState();
        currentMessages = [];
        currentDiscussionId = null;
        activeBranchId = null;
    }
}

/**
 * Displays an image in a custom, zoomable modal viewer with UI controls.
 * @param {string} imgSrc The source URL of the image to display.
 */
function viewImage(imgSrc) {
    // Prevent creating multiple modals
    if (document.querySelector('.image-modal-overlay-js')) return;

    // --- Create All Modal Elements ---
    const overlay = document.createElement('div');
    overlay.className = 'image-modal-overlay-js';

    const content = document.createElement('div'); // This is the container we'll zoom/pan
    content.className = 'image-modal-content-js';

    const img = document.createElement('img');
    img.src = imgSrc;

    const closeBtn = document.createElement('button');
    closeBtn.className = 'image-modal-close-btn-js';
    closeBtn.innerHTML = '×';
    closeBtn.title = 'Close (Esc)';

    // --- Create the Toolbar ---
    const toolbar = document.createElement('div');
    toolbar.className = 'image-modal-toolbar-js';

    const zoomOutBtn = document.createElement('button');
    zoomOutBtn.textContent = '−';
    zoomOutBtn.title = 'Zoom Out';
    
    const zoomLevelText = document.createElement('span');
    zoomLevelText.className = 'image-modal-zoom-level-js';
    
    const zoomInBtn = document.createElement('button');
    zoomInBtn.textContent = '+';
    zoomInBtn.title = 'Zoom In';
    
    const zoomResetBtn = document.createElement('button');
    zoomResetBtn.innerHTML = '↺'; // Reset arrow icon
    zoomResetBtn.title = 'Reset Zoom';

    // --- Apply Styles Programmatically to Avoid Conflicts ---
    overlay.style.cssText = `position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(0, 0, 0, 0.85); display: flex; align-items: center; justify-content: center; z-index: 1000; cursor: zoom-out; opacity: 0; transition: opacity 0.2s ease;`;
    content.style.cssText = `display: flex; transition: transform 0.3s ease; cursor: grab;`;
    img.style.cssText = `max-width: 90vw; max-height: 90vh; object-fit: contain; user-select: none; -webkit-user-drag: none;`;
    closeBtn.style.cssText = `position: absolute; top: 10px; right: 20px; color: white; background: none; border: none; font-size: 3rem; cursor: pointer;`;
    toolbar.style.cssText = `position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); background-color: rgba(30, 30, 30, 0.7); color: white; padding: 8px; border-radius: 8px; display: flex; align-items: center; gap: 10px; backdrop-filter: blur(5px); -webkit-backdrop-filter: blur(5px);`;
    const buttonStyles = `background: transparent; border: 1px solid white; color: white; border-radius: 50%; width: 32px; height: 32px; font-size: 1.2rem; display: flex; align-items: center; justify-content: center; cursor: pointer;`;
    zoomInBtn.style.cssText = buttonStyles;
    zoomOutBtn.style.cssText = buttonStyles;
    zoomResetBtn.style.cssText = buttonStyles;
    zoomLevelText.style.cssText = `font-size: 0.9rem; min-width: 50px; text-align: center;`;

    // --- Assemble and Display ---
    toolbar.appendChild(zoomOutBtn);
    toolbar.appendChild(zoomLevelText);
    toolbar.appendChild(zoomInBtn);
    toolbar.appendChild(zoomResetBtn);
    
    content.appendChild(img);
    overlay.appendChild(content);
    overlay.appendChild(closeBtn);
    overlay.appendChild(toolbar);
    document.body.appendChild(overlay);

    requestAnimationFrame(() => overlay.style.opacity = '1');

    // --- State and Event Handlers ---
    let isDragging = false;
    let startX, startY, posX = 0, posY = 0;
    let scale = 1;

    function updateZoom(newScale) {
        scale = Math.min(Math.max(1, newScale), 10); // Clamp scale 1x - 10x
        const isZoomed = scale > 1;

        content.style.cursor = isZoomed ? 'move' : 'grab';
        
        if (!isZoomed) { // Reset position if not zoomed
            posX = 0;
            posY = 0;
        }
        content.style.transform = `translate(${posX}px, ${posY}px) scale(${scale})`;
        zoomLevelText.textContent = `${Math.round(scale * 100)}%`;
    }
    
    function closeModal() {
        overlay.style.opacity = '0';
        overlay.addEventListener('transitionend', () => {
            overlay.remove();
            document.removeEventListener('keydown', keydownHandler);
            window.removeEventListener('mousemove', drag);
            window.removeEventListener('mouseup', stopDrag);
        }, { once: true });
    }

    const keydownHandler = (e) => { if (e.key === 'Escape') closeModal(); };
    const wheelHandler = (e) => { e.preventDefault(); updateZoom(scale + e.deltaY * -0.01); };
    const startDrag = (e) => {
        if (scale > 1) { // Only allow dragging when zoomed
            e.preventDefault();
            isDragging = true;
            startX = e.clientX - posX;
            startY = e.clientY - posY;
            content.style.transition = 'none';
        }
    };
    const drag = (e) => {
        if (isDragging) {
            e.preventDefault();
            posX = e.clientX - startX;
            posY = e.clientY - startY;
            content.style.transform = `translate(${posX}px, ${posY}px) scale(${scale})`;
        }
    };
    const stopDrag = () => {
        isDragging = false;
        content.style.transition = 'transform 0.3s ease';
    };

    // --- Add Event Listeners ---
    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });
    closeBtn.addEventListener('click', closeModal);
    document.addEventListener('keydown', keydownHandler);

    // Zoom and Pan Listeners
    content.addEventListener('wheel', wheelHandler);
    content.addEventListener('mousedown', startDrag);
    window.addEventListener('mousemove', drag);
    window.addEventListener('mouseup', stopDrag);
    
    // Toolbar Button Listeners
    zoomInBtn.addEventListener('click', () => updateZoom(scale + 0.25));
    zoomOutBtn.addEventListener('click', () => updateZoom(scale - 0.25));
    zoomResetBtn.addEventListener('click', () => updateZoom(1));
    
    // Initial zoom level display
    updateZoom(1);
}

function renderMessage(message, existingContainer = null, existingBubble = null) {
    if (!message || typeof message.sender === 'undefined') {
        return;
    }

    const messageId = message.id || `temp-render-${Date.now()}`;
    const domIdForBubble = `message-${messageId}`;

    let messageContainerToUse = isElementInDocument(existingContainer) ? existingContainer : document.querySelector(`.message-container[data-message-id="${messageId}"]`);
    let bubbleDivToUse = isElementInDocument(existingBubble) && existingBubble.id === domIdForBubble ? existingBubble : null;

    if (isElementInDocument(messageContainerToUse) && !isElementInDocument(bubbleDivToUse)) {
        bubbleDivToUse = messageContainerToUse.querySelector(`#${domIdForBubble}`);
    }

    const isUpdate = isElementInDocument(messageContainerToUse) && isElementInDocument(bubbleDivToUse);

    if (isUpdate) {
        const senderInfo = bubbleDivToUse.querySelector('.sender-info');
        if (senderInfo) senderInfo.remove();
        
        const imagesContainer = bubbleDivToUse.querySelector('.message-images-container');
        if (imagesContainer) imagesContainer.remove();

        const contentDiv = bubbleDivToUse.querySelector('.message-content');
        if (contentDiv) contentDiv.innerHTML = '';

        const footerDiv = bubbleDivToUse.querySelector('.message-footer');
        if (footerDiv) footerDiv.remove();

    } else {
        messageContainerToUse = document.createElement('div');
        messageContainerToUse.className = 'message-container flex flex-col';
        messageContainerToUse.dataset.messageId = messageId;
        bubbleDivToUse = document.createElement('div');
        messageContainerToUse.appendChild(bubbleDivToUse);

        if (chatMessages) {
            chatMessages.appendChild(messageContainerToUse);
        } else {
            console.error("renderMessage: chatMessages DOM element not found!");
            return;
        }

        messageContainerToUse.style.opacity = '0';
        messageContainerToUse.style.transform = 'translateY(20px)';
        requestAnimationFrame(() => {
            messageContainerToUse.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
            messageContainerToUse.style.opacity = '1';
            messageContainerToUse.style.transform = 'translateY(0)';
        });
    }

    bubbleDivToUse.id = domIdForBubble;

    const isStreamingThisMessage = message.id === currentAiMessageId && (aiMessageStreaming || generationInProgress);
    let bubbleClass;
    let senderDisplayName;
    let senderType;
    const userSenderNames = [currentUser.username, 'user', 'User', 'You', translate('sender_you', 'You'), translate('sender_user', 'User')];

    if (userSenderNames.some(name => name.toLowerCase() === (message.sender || '').toLowerCase())) {
        bubbleClass = 'user-bubble';
        senderDisplayName = currentUser.username || translate('sender_you', 'You');
        senderType = 'user';
    } else if (message.sender && (message.sender.toLowerCase() === 'system' || message.sender.toLowerCase() === 'error')) {
        bubbleClass = 'system-bubble';
        senderDisplayName = message.sender;
        senderType = 'system';
    } else {
        bubbleClass = 'ai-bubble';
        senderDisplayName = getSenderNameText(message);
        senderType = 'ai';
    }

    bubbleDivToUse.className = `message-bubble ${bubbleClass} ${isStreamingThisMessage ? 'is-streaming' : ''}`;
    if (message.addSpacing) {
        messageContainerToUse.classList.add('mt-4');
    }

    if (senderDisplayName && bubbleClass !== 'system-bubble') {
        const senderInfoDiv = document.createElement('div');
        senderInfoDiv.className = 'sender-info';
        let modelBadgeHTML = '';
        if (senderType === 'ai' && message.model_name) {
            modelBadgeHTML = `<span class="model-badge">${escapeHtml(message.model_name)}</span>`;
        }
        let timestampHTML = '';
        if (message.created_at) {
            timestampHTML = `<span class="message-timestamp">${formatTimestamp(new Date(message.created_at))}</span>`;
        }
        let avatarHTML = getSenderAvatar(senderDisplayName, senderType, message.sender);
        senderInfoDiv.innerHTML = `
            ${avatarHTML}
            <div class="sender-details">
                <span class="sender-text">${escapeHtml(senderDisplayName)}</span>
                ${modelBadgeHTML}
            </div>
            ${timestampHTML}
        `;
        bubbleDivToUse.insertBefore(senderInfoDiv, bubbleDivToUse.firstChild);
    }

    if (message.image_references && message.image_references.length > 0) {
        const imagesContainer = document.createElement('div');
        imagesContainer.className = 'message-images-container';
        const header = bubbleDivToUse.querySelector('.sender-info');
        bubbleDivToUse.insertBefore(imagesContainer, header ? header.nextSibling : bubbleDivToUse.firstChild);
        (async () => {
            for (const imgSrc of message.image_references) {
                const imgItem = document.createElement('div');
                imgItem.className = 'message-image-item';
                const imgTag = document.createElement('img');
                imgTag.alt = translate('chat_image_alt', 'Chat Image');
                imgTag.loading = 'lazy';
                try {
                    imgTag.src = imgSrc;
                    imgTag.onclick = () => viewImage(imgSrc);
                    imgTag.onload = () => imgItem.classList.add('loaded');
                    imgItem.appendChild(imgTag);
                    imagesContainer.appendChild(imgItem);
                } catch (err) {
                    console.error("Image failed to load:", imgSrc, err);
                    imgItem.classList.add('error');
                    imagesContainer.appendChild(imgItem);
                }
            }
        })();
    }

    let contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    bubbleDivToUse.appendChild(contentDiv);
    renderEnhancedContent(contentDiv, message.content || "", message.id, message.steps, message.metadata, message);

    const footerDiv = document.createElement('div');
    footerDiv.className = 'message-footer';
    const footerContent = document.createElement('div');
    footerContent.className = 'footer-content';
    const detailsContainer = document.createElement('div');
    detailsContainer.className = 'message-details';

    if (message.token_count || (bubbleClass === 'ai-bubble' && isStreamingThisMessage)) {
        const tokenBadge = document.createElement('span');
        tokenBadge.className = 'detail-badge token-badge';
        tokenBadge.dataset.placeholder = 'token-count';
        tokenBadge.style.display = message.token_count ? 'inline-flex' : 'none';
        tokenBadge.innerHTML = `<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg> ${message.token_count || ''} ${translate('tokens_label', 'tokens')}`;
        detailsContainer.appendChild(tokenBadge);
    }
    
    if (message.branches && message.branches.length > 1) {
        console.log(message.branches)
        const branchNav = createBranchNavUI(message);
        detailsContainer.appendChild(branchNav);
    }

    const sources = message.sources;
    if (Array.isArray(sources) && sources.length > 0) {
        sources.forEach(source => {
            // Basic validation for the source object
            if (!source || typeof source.document === 'undefined' || typeof source.similarity === 'undefined') {
                console.warn("Skipping malformed RAG source:", source);
                return;
            }

            const sourceBadge = document.createElement('button');
            const maxLength = 25;
            const truncatedText = source.document.length > maxLength ? source.document.substring(0, maxLength) + '…' : source.document;

            sourceBadge.innerHTML = `
                <svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true"><path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 0v12h8V7.414L11.414 4H6z" clip-rule="evenodd" /></svg>
                <span>${escapeHtml(truncatedText)}</span>
                <span class="source-similarity-chip">${Math.round(source.similarity)}%</span>`;
            sourceBadge.className = 'detail-badge source-badge';
            sourceBadge.title = `${translate('view_source_document', 'View source')}: ${escapeHtml(source.document)} (${translate('similarity_label', 'Similarity')}: ${Math.round(source.similarity * 100)}%)`;

            // Use the new helper function for the click event
            sourceBadge.onclick = () => showSourceModal(source, message.id);
            detailsContainer.appendChild(sourceBadge);
        });
    }    

    footerContent.appendChild(detailsContainer);

    const footerActionsContainer = document.createElement('div');
    footerActionsContainer.className = 'message-footer-actions';
    const isDisabled = isStreamingThisMessage;
    const actionsGroup = document.createElement('div');
    actionsGroup.className = 'message-actions-group';
    const currentMessageBranchId = message.branch_id || activeBranchId || 'main';

    actionsGroup.appendChild(createActionButton('copy', translate('copy_content_tooltip', "Copy content"), () => { navigator.clipboard.writeText(message.content).then(() => showStatus(translate('status_copied_to_clipboard', 'Copied!'), 'success')); }, 'default', isDisabled));
    actionsGroup.appendChild(createActionButton('edit', translate('edit_message_tooltip', "Edit message"), () => initiateEditMessage(message.id, currentMessageBranchId), 'default', isDisabled));

    if (senderType === 'user') {
        actionsGroup.appendChild(createActionButton('refresh', translate('resend_branch_tooltip', 'Resend/Branch'), () => initiateBranch(currentDiscussionId, message.id, currentMessageBranchId), 'primary', isDisabled));
    } else if (senderType === 'ai') {
        actionsGroup.appendChild(createActionButton('refresh', translate('regenerate_message_tooltip', 'Regenerate'), () => regenerateMessage(message.id, currentMessageBranchId), 'primary', isDisabled));
    }
    actionsGroup.appendChild(createActionButton('delete', translate('delete_message_tooltip', "Delete"), () => deleteMessage(message.id, currentMessageBranchId), 'destructive', isDisabled));

    if (actionsGroup.hasChildNodes()) footerActionsContainer.appendChild(actionsGroup);

    if (senderType === 'ai') {
        const ratingContainer = document.createElement('div');
        ratingContainer.className = 'message-rating';
        const userGrade = message.user_grade || 0;
        const upvoteBtn = document.createElement('button');
        const gradeDisplay = document.createElement('span');
        const downvoteBtn = document.createElement('button');
        upvoteBtn.className = `rating-btn upvote ${userGrade > 0 ? 'active' : ''}`;
        upvoteBtn.innerHTML = `<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 3a1 1 0 01.707.293l5 5a1 1 0 01-1.414 1.414L11 6.414V16a1 1 0 11-2 0V6.414L5.707 9.707a1 1 0 01-1.414-1.414l5-5A1 1 0 0110 3z" clip-rule="evenodd" /></svg>`;
        upvoteBtn.title = translate('grade_good_tooltip', 'Good response');
        upvoteBtn.setAttribute('aria-pressed', userGrade > 0 ? 'true' : 'false');
        upvoteBtn.onclick = () => gradeMessage(message.id, 1, currentMessageBranchId);
        upvoteBtn.disabled = isDisabled;
        gradeDisplay.className = 'rating-score';
        gradeDisplay.textContent = userGrade;
        gradeDisplay.setAttribute('aria-live', 'polite');
        downvoteBtn.className = `rating-btn downvote ${userGrade < 0 ? 'active' : ''}`;
        downvoteBtn.innerHTML = `<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 17a1 1 0 01-.707-.293l-5-5a1 1 0 011.414-1.414L9 13.586V4a1 1 0 112 0v9.586l3.293-3.293a1 1 0 011.414 1.414l-5 5A1 1 0 0110 17z" clip-rule="evenodd" /></svg>`;
        downvoteBtn.title = translate('grade_bad_tooltip', 'Bad response');
        downvoteBtn.setAttribute('aria-pressed', userGrade < 0 ? 'true' : 'false');
        downvoteBtn.onclick = () => gradeMessage(message.id, -1, currentMessageBranchId);
        downvoteBtn.disabled = isDisabled;
        ratingContainer.appendChild(upvoteBtn);
        ratingContainer.appendChild(gradeDisplay);
        ratingContainer.appendChild(downvoteBtn);
        footerActionsContainer.appendChild(ratingContainer);
    }

    if (footerActionsContainer.hasChildNodes()) footerContent.appendChild(footerActionsContainer);
    if (footerContent.hasChildNodes()) {
        footerDiv.appendChild(footerContent);
        bubbleDivToUse.appendChild(footerDiv);
    }

    if (isStreamingThisMessage) {
        currentAiMessageDomContainer = messageContainerToUse;
        currentAiMessageDomBubble = bubbleDivToUse;
    }
}
/**
 * FIX: Processes a list of messages to move branch information from a child message
 * to its rightful parent. The backend sometimes incorrectly attaches the list of
 * sibling branches to the first child, instead of attaching the list of children
 * to the parent. This function corrects that data structure before rendering.
 *
 * @param {Array<object>} rawMessages The list of messages as received from the API.
 * @returns {Array<object>} A new list of messages with branch data correctly mapped to parent messages.
 */
function processAndRemapBranches(rawMessages) {
    if (!rawMessages || rawMessages.length === 0) {
        return [];
    }

    // Create a map for quick ID-based lookups.
    const messageMap = new Map(rawMessages.map(msg => [msg.id, { ...msg }]));

    // Iterate over a copy of the keys to avoid issues with map modification
    for (const message of messageMap.values()) {
        // Find any message that has the incorrectly placed 'branches' array.
        if (message.branches && message.branches.length > 0) {
            
            // Find this message's parent.
            if (message.parent_message_id) {
                const parentMessage = messageMap.get(message.parent_message_id);


            }
        }
    }
    
    // Return the corrected list of messages from the map.
    return Array.from(messageMap.values());
}
/**
 * Creates the navigation UI for switching between message branches. This version uses a robust
 * method to correctly identify the currently active branch.
 * 
 * @param {object} message The message object that has multiple branches.
 * @returns {HTMLElement} The container element for the branch navigation UI.
 */
function createBranchNavUI(message) {
    const discussionData = discussions[currentDiscussionId];
    // Don't render if there's no branching data, only one branch, or the discussion map is missing.
    if (!discussionData || !discussionData.branch_map || !message.branches || message.branches.length <= 1) {
        return document.createElement('div');
    }

    // The ground truth: The list of START IDs for all possible child branches from this message.
    const childBranchStartIds = message.branches;

    // --- Helper to find the current branch's info ---
    const getCurrentBranchInfo = () => {
        const activeTipId = discussionData.activeBranchId; // The ID of the LAST message in the active branch.
        const branchMap = discussionData.branch_map;   // The map of { startId: tipId }.

        // PRIMARY METHOD: Reverse lookup in the branch map.
        // Find which startId in our map points to the currently active tipId.
        const currentStartId = Object.keys(branchMap).find(startId => branchMap[startId] === activeTipId);

        if (currentStartId) {
            // We found the startId that corresponds to our active branch.
            // Now, find its index within the list of possible branches for *this specific message*.
            const index = childBranchStartIds.indexOf(currentStartId);
            if (index !== -1) {
                // Success! We know our current branch index.
                return { index: index, startId: currentStartId };
            }
        }
        
        // FALLBACK METHOD: If the map lookup fails (e.g., data is momentarily stale),
        // scan the active message list. This is slower but provides robustness.
        const activeBranchMessages = discussionData.branches[activeTipId];
        if (activeBranchMessages) {
            for (const msg of activeBranchMessages) {
                const index = childBranchStartIds.indexOf(msg.id);
                if (index !== -1) {
                    // Found a match by scanning.
                    return { index: index, startId: msg.id };
                }
            }
        }
        
        // If both methods fail, we can't determine the branch.
        return { index: -1, startId: null };
    };

    // --- Create UI Elements ---
    const navContainer = document.createElement('div');
    navContainer.className = 'branch-nav-container';

    const prevBtn = document.createElement('button');
    prevBtn.className = 'branch-nav-btn';
    prevBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" /></svg>';
    prevBtn.title = translate('previous_branch_tooltip', 'Previous Branch');

    const statusText = document.createElement('span');
    statusText.className = 'branch-nav-status';

    const nextBtn = document.createElement('button');
    nextBtn.className = 'branch-nav-btn';
    nextBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" /></svg>';
    nextBtn.title = translate('next_branch_tooltip', 'Next Branch');

    // --- Update and Navigation Logic ---
    const updateStatus = () => {
        const { index } = getCurrentBranchInfo();
        if (index !== -1) {
            statusText.textContent = `${index + 1} / ${childBranchStartIds.length}`;
        } else {
            statusText.textContent = `? / ${childBranchStartIds.length}`;
        }
    };

    const navigate = (direction) => {
        const { index } = getCurrentBranchInfo();

        if (index === -1) {
            console.warn("Could not determine current branch index for navigation. Defaulting to first branch.");
            switchBranch(currentDiscussionId, childBranchStartIds[0]);
            return;
        }

        const nextIndex = (index + direction + childBranchStartIds.length) % childBranchStartIds.length;
        const nextBranchStartId = childBranchStartIds[nextIndex];
        
        switchBranch(currentDiscussionId, nextBranchStartId);
    };

    prevBtn.onclick = () => navigate(-1);
    nextBtn.onclick = () => navigate(1);

    navContainer.appendChild(prevBtn);
    navContainer.appendChild(statusText);
    navContainer.appendChild(nextBtn);
    
    updateStatus();

    return navContainer;
}

/**
 * Switches the active branch for the current discussion and reloads the chat view.
 * @param {string} discussionId The ID of the current discussion.
 * @param {string} newBranchStartId The starting message ID of the branch to switch to.
 */
async function switchBranch(discussionId, newBranchStartId) {
    if (!discussionId || !newBranchStartId || aiMessageStreaming) return;
    
    const discussionData = discussions[discussionId];
    if (!discussionData) return;

    // Set the new active branch ID. `selectDiscussion` will handle loading it.
    discussionData.activeBranchId = newBranchStartId;
    
    // We can "forget" that this branch was fully loaded to force a fresh fetch from the server.
    // This is safer in case the tip ID has changed since we last loaded it.
    const knownTipId = discussionData.branch_map[newBranchStartId];
    if (knownTipId && discussionData.messages_loaded_fully) {
        delete discussionData.messages_loaded_fully[knownTipId];
    }
    if (discussionData.messages_loaded_fully) {
        delete discussionData.messages_loaded_fully[newBranchStartId];
    }
    
    // Calling selectDiscussion will now fetch and render the correct new branch.
    await selectDiscussion(discussionId);
}
function renderMessages(messagesToRender) {
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
        if (Object.keys(messagesByDate).length > 1 || (new Date(date).toDateString() !== new Date().toDateString())) {
            const dateSeparator = document.createElement('div');
            dateSeparator.className = 'date-separator';
            dateSeparator.innerHTML = `<div class="date-separator-line"></div><div class="date-separator-text">${formatDateSeparator(new Date(date))}</div><div class="date-separator-line"></div>`;
            chatMessages.appendChild(dateSeparator);
        }
        messagesOnDate.forEach((msg, index) => {
            msg.addSpacing = (index > 0 && messagesOnDate[index - 1].sender !== msg.sender);
            console.log(msg)
            renderMessage(msg);
        });
    });
    requestAnimationFrame(() => { forceScrollToBottom(); });
}

// --- All Other Helper Functions ---
// (The rest of your original helpers from your first post are included here for completeness)
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
/**
 * Creates an HTML string for a sender's avatar.
 * @param {string} senderDisplayName The name to display.
 * @param {string} senderType 'user' or 'ai'.
 * @param {string} originalSender The original sender name from the message object.
 * @returns {string} The HTML string for the <img> tag.
 */
function getSenderAvatar(senderDisplayName, senderType, originalSender) {
    let avatarSrc = '';
    let altText = senderDisplayName;

    if (senderType === 'user') {
        // Use user's avatar or fall back to a UI-Avatar
        avatarSrc = currentUser.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(senderDisplayName)}&background=0D8ABC&color=fff&size=48`;
    } else if (senderType === 'ai') {
        // Use a specific AI avatar if available, otherwise fall back to a UI-Avatar
        avatarSrc = (window.uiValues && window.uiValues.aiAvatar) ? window.uiValues.aiAvatar : `https://ui-avatars.com/api/?name=${encodeURIComponent(senderDisplayName.substring(0,2))}&background=10B981&color=fff&size=48`;
        altText = `${senderDisplayName} AI`;
    } else { 
        return ''; // No avatar for system messages
    }
    return `<img src="${avatarSrc}" alt="${escapeHtml(altText)}" class="sender-avatar">`;
}
// You should have a more robust version of this
function getSenderAvatar(senderDisplayName, senderType, originalSender) {
    let avatarSrc = '';
    let altText = senderDisplayName;

    if (senderType === 'user') {
        avatarSrc = currentUser.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(senderDisplayName)}&background=0D8ABC&color=fff&size=48`;
    } else if (senderType === 'ai') {
        // You might have a mapping of AI names to avatars
        // For now, a generic AI avatar or based on lollms_client_ai_name
        avatarSrc = (originalSender === currentUser.lollms_client_ai_name && window.uiValues && window.uiValues.aiAvatar) ? window.uiValues.aiAvatar : `https://ui-avatars.com/api/?name=${encodeURIComponent(senderDisplayName.substring(0,2))}&background=10B981&color=fff&size=48`;
        altText = `${senderDisplayName} AI`;
    } else { // system or other
        return ''; // No avatar for system messages, or a generic icon
    }
    return `<img src="${avatarSrc}" alt="${escapeHtml(altText)}" class="sender-avatar">`;
}
/**
 * Renders a new step by PREPENDING it, ensuring the latest step is always at the top.
 * This makes the collapse/expand behavior more intuitive for the user.
 *
 * @param {HTMLElement} bubbleDiv The parent message bubble element.
 * @param {object} stepData The data for the new step.
 */
function renderNewStep(bubbleDiv, stepData) {
    const contentDiv = bubbleDiv.querySelector('.message-content');
    if (!contentDiv) return;

    let stepsContainer = contentDiv.querySelector('.steps-container');
    let toggleButton = contentDiv.querySelector('.steps-toggle-button');

    // --- Create container and button on first step ---
    if (!stepsContainer) {
        stepsContainer = document.createElement('div');
        stepsContainer.className = 'steps-container';
        // The button now goes AFTER the container in the DOM
        contentDiv.appendChild(stepsContainer);

        toggleButton = document.createElement('button');
        toggleButton.className = 'steps-toggle-button';
        toggleButton.innerHTML = `
            <span class="toggle-text"></span>
            <svg class="toggle-arrow" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
        `;
        contentDiv.appendChild(toggleButton);

        toggleButton.onclick = () => {
            const isCollapsed = stepsContainer.classList.toggle('collapsed');
            const textEl = toggleButton.querySelector('.toggle-text');
            const stepCount = stepsContainer.children.length;
            if (isCollapsed) {
                textEl.textContent = `Show ${stepCount - 1} older steps...`;
            } else {
                textEl.textContent = 'Show only latest step';
                // Animate to full height when manually expanded
                stepsContainer.style.maxHeight = stepsContainer.scrollHeight + 'px';
            }
        };
    }
    
    // --- Create and PREPEND the new step item ---
    const stepEl = document.createElement('div');
    stepEl.className = 'step-item status-pending';
    stepEl.dataset.stepId = stepData.id;
    const stepText = escapeHtml(stepData.content || stepData.chunk || '');
    stepEl.innerHTML = `
        <div class="step-icon">
            <svg class="spinner" viewBox="0 0 50 50"><circle class="path" cx="25" cy="25" r="20" fill="none" stroke-width="5"></circle></svg>
        </div>
        <div class="step-text">${stepText}</div>
    `;
    // THIS IS THE KEY CHANGE:
    stepsContainer.prepend(stepEl);

    // --- Update state and collapse logic ---
    const stepCount = stepsContainer.children.length;
    const textEl = toggleButton.querySelector('.toggle-text');

    if (stepCount > 1) {
        stepsContainer.classList.add('collapsed');
        textEl.textContent = `Show ${stepCount - 1} older steps...`;
        toggleButton.style.display = 'flex';
    } else {
        stepsContainer.classList.remove('collapsed');
        toggleButton.style.display = 'none'; // No need to show button for one step
    }
}

/**
 * Updates a step's status and expands the container if all steps are done.
 *
 * @param {HTMLElement} bubbleDiv The parent message bubble element.
 * @param {string} stepId The ID of the step to update.
 * @param {string} newStatus The new status.
 */
function updateStepStatus(bubbleDiv, stepId, newStatus) {
    const stepEl = bubbleDiv.querySelector(`.step-item[data-step-id="${stepId}"]`);
    if (stepEl) {
        stepEl.className = `step-item status-${newStatus}`;
        const iconDiv = stepEl.querySelector('.step-icon');
        if (iconDiv && newStatus === 'done') {
            iconDiv.innerHTML = `<svg fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>`;
        }
    }
    
    // --- Check if all steps are done to auto-expand ---
    const stepsContainer = bubbleDiv.querySelector('.steps-container');
    const toggleButton = bubbleDiv.querySelector('.steps-toggle-button');
    if (stepsContainer && toggleButton) {
        const allSteps = Array.from(stepsContainer.children);
        const allDone = allSteps.every(s => s.classList.contains('status-done'));
        // We only auto-expand if the process completes naturally
        if (allDone && allSteps.length > 1 && aiMessageStreaming === false) {
            stepsContainer.classList.remove('collapsed');
            stepsContainer.style.maxHeight = stepsContainer.scrollHeight + 'px'; // Animate to full height
            toggleButton.style.display = 'none'; // Hide button when process is complete
        }
    }
}
/**
 * Renders the main body of a message with all enhancements.
 * This version treats the steps container as persistent and does not clear it
 * during content-only re-renders, fixing the bug where steps disappeared.
 */
function renderEnhancedContent(contentDivElement, rawContent, messageId, steps = [], metadata = [], messageObject = {}) {
    // --- Find or Create the Main Content Wrapper ---
    let mainContentWrapper = contentDivElement.querySelector('.prose');
    if (!mainContentWrapper) {
        mainContentWrapper = document.createElement('div');
        mainContentWrapper.classList.add('prose', 'prose-sm', 'max-w-none', 'dark:prose-invert');
        contentDivElement.prepend(mainContentWrapper); // Prepend to ensure it's before steps
    }

    // --- Logic for Typing Indicator ---
    const isStreamingThisMessage = aiMessageStreaming && messageId === currentAiMessageId;
    const isEffectivelyEmpty = !(rawContent && rawContent.trim()) && (!steps || steps.length === 0) && (!metadata || metadata.length === 0);

    // Check if the steps container already exists.
    const stepsContainerExists = !!contentDivElement.querySelector('.steps-container');

    if (isStreamingThisMessage && isEffectivelyEmpty && !stepsContainerExists) {
        // Only show typing indicator if there's no content AND no steps have been rendered yet.
        mainContentWrapper.innerHTML = ''; // Clear any previous prose content
        const typingIndicatorDiv = document.createElement('div');
        typingIndicatorDiv.className = 'typing-indicator';
        for (let i = 0; i < 3; i++) {
            typingIndicatorDiv.appendChild(document.createElement('span'));
        }
        mainContentWrapper.appendChild(typingIndicatorDiv);
        return; // We are done for this render cycle.
    }

    // --- Render Main Content (Markdown, Think Blocks) ---
    // This section now *only* updates the mainContentWrapper, leaving other elements untouched.
    let currentSegment = rawContent || "";
    const thinkBlockRegex = /<think>([\s\S]*?)<\/think>/gs;
    let lastIndex = 0;
    let match;
    mainContentWrapper.innerHTML = ''; // Clear ONLY the prose content for re-rendering

    while ((match = thinkBlockRegex.exec(currentSegment)) !== null) {
        const textBefore = currentSegment.substring(lastIndex, match.index);
        if (textBefore.trim()) {
            const regularContentSegmentDiv = document.createElement('div');
            regularContentSegmentDiv.innerHTML = marked.parse(textBefore);
            mainContentWrapper.appendChild(regularContentSegmentDiv);
        }

        const thinkDetails = document.createElement('details');
        thinkDetails.className = 'think-block my-2';
        const thinkSummary = document.createElement('summary');
        thinkSummary.className = 'px-2 py-1 text-xs italic text-gray-500 dark:text-gray-400 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-750 rounded focus:outline-none focus:ring-2 focus:ring-blue-500';
        thinkSummary.textContent = translate('assistant_thoughts_summary', "Assistant's Thoughts");
        const thinkContentDiv = document.createElement('div');
        thinkContentDiv.className = 'think-content p-2 border-t border-gray-200 dark:border-gray-700 prose prose-sm max-w-none dark:prose-invert';
        thinkContentDiv.innerHTML = marked.parse(match[1].trim());

        thinkDetails.appendChild(thinkSummary);
        thinkDetails.appendChild(thinkContentDiv);
        mainContentWrapper.appendChild(thinkDetails);
        lastIndex = thinkBlockRegex.lastIndex;
    }

    const remainingText = currentSegment.substring(lastIndex);
    if (remainingText.trim()) {
        const finalContentSegmentDiv = document.createElement('div');
        finalContentSegmentDiv.innerHTML = marked.parse(remainingText);
        mainContentWrapper.appendChild(finalContentSegmentDiv);
    }
    
    // --- Render Steps and Metadata (only if provided) ---
    // This part is now additive. It won't clear the steps container if the `steps` array is empty.
    if (steps && steps.length > 0) {
        renderOrUpdateSteps(contentDivElement, steps, true); // true for initialRender from history
    }
    if (metadata && metadata.length > 0) {
        // This assumes renderMetadata is also additive and doesn't clear its container.
        renderMetadata(contentDivElement, metadata);
    }

    // --- Fallback for completely empty, non-streaming messages ---
    if (isEffectivelyEmpty && !stepsContainerExists && (!messageObject.image_references || messageObject.image_references.length === 0)) {
        mainContentWrapper.innerHTML = `<p class="empty-message-placeholder">${translate('empty_message_placeholder', 'Empty message')}</p>`;
    }

    // --- Post-processing for dynamic content ---
    // This now runs on the entire message-content div to catch content in both prose and steps.
    if (typeof renderMathInElement === 'function') {
        try {
            renderMathInElement(contentDivElement, { delimiters: [{ left: '$$', right: '$$', display: true }, { left: '$', right: '$', display: false }, { left: '\\(', right: '\\)', display: false }, { left: '\\[', right: '\\]', display: true }], throwOnError: false });
        } catch (e) { console.warn("KaTeX rendering error:", e); }
    }

    renderCustomCodeBlocks(contentDivElement, messageId);
    applySyntaxHighlighting(contentDivElement);
    addCodeBlockCopyButtons(contentDivElement);
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
        refresh: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>`,
        chat_bubble: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.76c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 0 1 1.037-.443 48.282 48.282 0 0 0 5.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018Z" /></svg>`,
        person_remove: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4"><path stroke-linecap="round" stroke-linejoin="round" d="M18 18.72a9.094 9.094 0 0 0 3.741-.479 3 3 0 0 0-4.682-2.72m-.243-3.72a9.094 9.094 0 0 1-3.741-.479 3 3 0 0 1-4.682-2.72M12 12.75a3 3 0 1 1 0-6 3 3 0 0 1 0 6Zm-7.5 3.75a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm0 0h.01M12 12.75a9.094 9.094 0 0 0-3.741-.479 3 3 0 0 0-4.682-2.72m0 0a9.094 9.094 0 0 1 3.741-.479m0 0a3 3 0 1 0-4.682-2.72m4.682 2.72M3.055 11.676A9.094 9.094 0 0 1 6.795 11.2a3 3 0 0 1 4.682 2.719m0 0a3 3 0 0 1-4.682 2.72m4.682-2.72m6.945-5.438A9.094 9.094 0 0 1 17.205 11.2a3 3 0 0 1 4.682 2.719m0 0a3 3 0 0 1-4.682 2.72m4.682-2.72M12 12.75a3 3 0 1 1 0-6 3 3 0 0 1 0 6Z" /></svg>`, // This is a complex group icon, find simpler ones
        block: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4"><path stroke-linecap="round" stroke-linejoin="round" d="M18.364 18.364A9 9 0 0 0 5.636 5.636m12.728 12.728A9 9 0 0 1 5.636 5.636m12.728 12.728L5.636 5.636" /></svg>`
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
/**
 * A helper function to update the toggle button's text and visibility.
 * @param {HTMLElement} toggleButton The button element to update.
 * @param {HTMLElement} stepsContainer The container holding the step items.
 */
function updateToggleButtonText(toggleButton, stepsContainer) {
    const stepCount = stepsContainer.children.length;

    if (stepCount <= 1) {
        toggleButton.style.display = 'none';
        return;
    }

    toggleButton.style.display = 'flex';
    const textEl = toggleButton.querySelector('.toggle-text');
    const isCollapsed = stepsContainer.classList.contains('collapsed');

    if (isCollapsed) {
        const olderStepsCount = stepCount - 1;
        textEl.textContent = translate('show_older_steps_btn', `Show ${olderStepsCount} older step(s)...`, { count: olderStepsCount });
    } else {
        textEl.textContent = translate('hide_steps_btn', 'Hide steps');
    }
}


/**
 * Renders or updates a list of steps, with the latest step always on top.
 * Manages a collapsible container to show/hide the history of older steps.
 * Differentiates between 'process' steps (with states) and 'info' steps.
 *
 * @param {HTMLElement} parentContainer The element to attach the steps to (e.g., message-content).
 * @param {Array<object>} steps The array of step objects to render or update.
 * @param {boolean} isInitialRenderFromHistory If true, sets the initial state from saved data.
 */
function renderOrUpdateSteps(parentContainer, steps, isInitialRenderFromHistory = false) {
    if (!steps || steps.length === 0) return;

    let stepsContainer = parentContainer.querySelector('.steps-container');
    let toggleButton = parentContainer.querySelector('.steps-toggle-button');

    if (!stepsContainer) {
        stepsContainer = document.createElement('div');
        stepsContainer.className = 'steps-container';
        toggleButton = document.createElement('button');
        toggleButton.className = 'steps-toggle-button';
        toggleButton.innerHTML = `
            <span class="toggle-text"></span>
            <svg class="toggle-arrow" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
        `;
        parentContainer.appendChild(stepsContainer);
        parentContainer.appendChild(toggleButton);

        toggleButton.onclick = () => {
            const isCollapsing = !stepsContainer.classList.contains('collapsed');
            stepsContainer.classList.toggle('collapsed', isCollapsing);

            if (!isCollapsing) {
                requestAnimationFrame(() => {
                    stepsContainer.style.maxHeight = stepsContainer.scrollHeight + 'px';
                });
            } else {
                stepsContainer.style.maxHeight = null;
            }
            updateToggleButtonText(toggleButton, stepsContainer);
        };
        
        // **THE FIX, Part 1:** When a message is from history, set its initial state and we are done.
        // For new messages, we start it expanded and let the user decide when to collapse.
        if (isInitialRenderFromHistory) {
             stepsContainer.classList.add('collapsed');
        }
    }

    steps.forEach(stepData => {
        if (!stepData || !stepData.id) return;
        let stepEl = stepsContainer.querySelector(`.step-item[data-step-id="${stepData.id}"]`);
        if (!stepEl) {
            stepEl = document.createElement('div');
            stepEl.dataset.stepId = stepData.id;
            const stepText = escapeHtml(stepData.content || stepData.chunk || '');
            let iconHTML = '';
            let itemClass = '';
            if (stepData.type === 'step') {
                itemClass = 'step-item step-item-info';
                iconHTML = `<svg class="w-4 h-4 text-blue-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" /></svg>`;
            } else {
                itemClass = 'step-item step-item-process status-pending';
                iconHTML = `<svg class="spinner" viewBox="0 0 50 50"><circle class="path" cx="25" cy="25" r="20" fill="none" stroke-width="5"></circle></svg>`;
            }
            stepEl.className = itemClass;
            stepEl.innerHTML = `<div class="step-icon">${iconHTML}</div><div class="step-text">${stepText}</div>`;
            stepsContainer.prepend(stepEl);
        }
        if (stepEl.classList.contains('step-item-process') && stepData.status === 'done') {
            const wasPending = stepEl.classList.contains('status-pending');
            if (wasPending) {
                stepEl.classList.remove('status-pending');
                stepEl.classList.add('status-done');
                const iconDiv = stepEl.querySelector('.step-icon');
                if (iconDiv) {
                    iconDiv.innerHTML = `<svg fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>`;
                }
                const textDiv = stepEl.querySelector('.step-text');
                if (textDiv && stepData.content) {
                    textDiv.textContent = escapeHtml(stepData.content);
                }
            }
        }
    });

    // **THE FIX, Part 2:** If the container is currently expanded (not collapsed),
    // we must update its maxHeight to animate the new step in. We no longer automatically
    // add the 'collapsed' class here during live streaming.
    if (!stepsContainer.classList.contains('collapsed')) {
        requestAnimationFrame(() => {
            stepsContainer.style.maxHeight = stepsContainer.scrollHeight + 'px';
        });
    }

    updateToggleButtonText(toggleButton, stepsContainer);
}

/**
 * Helper function to update the toggle button's text based on the current state.
 * @param {HTMLElement} toggleButton The button to update.
 * @param {HTMLElement} stepsContainer The container with the steps.
 */
function updateToggleButtonText(toggleButton, stepsContainer) {
    const stepCount = stepsContainer.children.length;
    if (stepCount <= 1) {
        toggleButton.style.display = 'none';
        return;
    }
    
    toggleButton.style.display = 'flex';
    const textEl = toggleButton.querySelector('.toggle-text');
    const isCollapsed = stepsContainer.classList.contains('collapsed');

    if (isCollapsed) {
        // Show the text of the latest (first) step, which is visible
        const latestStepText = stepsContainer.firstElementChild.querySelector('.step-text').textContent;
        textEl.textContent = latestStepText;
    } else {
        textEl.textContent = `Show less (${stepCount} steps)`;
    }
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
    
    // Find the message in the correct branch's message list
    const branchMessages = discussions[currentDiscussionId].branches[branchId];
    if (!branchMessages) {
        console.error("Branch not found in client-side cache for editing:", branchId);
        return;
    }

    const messageData = branchMessages.find(m => m.id === messageId);
    if (!messageData) { 
        showStatus(translate('status_cannot_find_message_to_edit'), "error"); 
        return; 
    }

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

    // Use the new endpoint that includes branch_id
    let apiUrl = `/api/discussions/${currentDiscussionId}/messages/${messageId}?branch_id=${encodeURIComponent(branchId)}`;

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
                const originalMsg = disc.branches[branchId][msgIndex];
                disc.branches[branchId][msgIndex] = { ...originalMsg, ...updatedMessageData };
            }
        }
        
        // This is a branching action, so we should refresh the current branch view
        await selectDiscussion(currentDiscussionId);
        
        showStatus(translate('status_message_updated_success', 'Message updated successfully.'), 'success', editMessageStatus);
        setTimeout(() => closeModal('editMessageModal'), 1000);
    } catch (error) { /* apiRequest handles status */
    } finally {
        if(confirmEditMessageBtn) confirmEditMessageBtn.disabled = false;
    }
}

async function deleteMessage(messageId, branchId) {
    console.log(`Attempting to delete message with ID: ${messageId} in branch: ${branchId}`);
    if (!currentDiscussionId || !messageId || messageId.startsWith('temp-') || !branchId) {
        if (messageId && messageId.startsWith('temp-')) {
            console.warn("Delete aborted: Message ID is still temporary.", messageId);
        }
        return;
    }

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
            
            if (disc.branches[branchId].length === 0 && branchId !== 'main') {
            }
            currentMessages = disc.branches[activeBranchId] || [];
            renderMessages(currentMessages);

            showStatus(translate('status_message_deleted_success', 'Message deleted successfully.'), 'success');
        } catch (error) { }
    }
}

async function regenerateMessage(messageId, branchId) {
    if (!currentDiscussionId || !branchId || generationInProgress) return;

    const disc = discussions[currentDiscussionId];
    if (!disc || !disc.branches[branchId]) return;

    const branchMessages = disc.branches[branchId];
    const aiMessageIndex = branchMessages.findIndex(msg => msg.id === messageId);
    if (aiMessageIndex === -1 || aiMessageIndex === 0) {
        showStatus(translate('status_cannot_regenerate_message', "Cannot regenerate this message."), "warning");
        return;
    }

    const userPromptMessage = branchMessages[aiMessageIndex - 1];
    const userNamesForCheck = [currentUser.username, 'User', 'user', translate('sender_you', 'You'), translate('sender_user', 'User')];
    if (!userPromptMessage || !userNamesForCheck.some(name => name.toLowerCase() === (userPromptMessage.sender || '').toLowerCase())) {
        showStatus(translate('status_cannot_regenerate_no_user_prompt', "Cannot regenerate without a preceding user prompt."), "warning");
        return;
    }
    
    showStatus(translate('status_regenerating_response', "Regenerating response..."), "info");

    disc.branches[branchId] = branchMessages.slice(0, aiMessageIndex);
    currentMessages = disc.branches[branchId];
    renderMessages(currentMessages);
    forceScrollToBottom();

    const resendPayload = {
        prompt: userPromptMessage.content,
        image_server_paths: userPromptMessage.server_image_paths || []
    };
    
    // The message to branch from is the PARENT of the user message that prompted the AI.
    const parentOfUserPrompt = userPromptMessage.parent_message_id;

    await sendMessage(parentOfUserPrompt, resendPayload);
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
/**
 * Handles the "Resend/Branch" action from a user message.
 * This function will truncate the conversation at that message, and then resend the
 * user's prompt to generate a new response, effectively creating a new branch.
 *
 * @param {string} discussionId The ID of the current discussion.
 * @param {string} userMessageId The ID of the user's message to branch from.
 * @param {string} branchId The specific branch ID this user message belongs to.
 */
async function initiateBranch(discussionId, userMessageId, branchId) {
    if (!discussionId || !userMessageId || !branchId || generationInProgress) return;

    const disc = discussions[discussionId];
    if (!disc || !disc.branches || !disc.branches[branchId]) {
        console.error("initiateBranch: Source branch not found in client data:", branchId);
        showStatus("Error: Could not find the source branch for this message.", "error");
        return;
    }

    // Find the message in its specific, correct branch, not just the "active" one.
    const sourceBranchMessages = disc.branches[branchId];
    const userMessageIndex = sourceBranchMessages.findIndex(msg => msg.id === userMessageId);

    if (userMessageIndex === -1) {
        // This is the error you were seeing. This check remains as a safeguard.
        console.error("initiateBranch: User message to branch from not found in its own branch:", userMessageId, "in branch", branchId);
        showStatus("Error: Could not find the message to branch from. Please refresh.", "error");
        return;
    }

    const userMessageData = sourceBranchMessages[userMessageIndex];
    const parentMessageId = userMessageData.parent_message_id; // The message we will branch OFF of.

    showStatus(translate('status_creating_new_branch', "Creating new branch..."), "info");

    // Truncate the branch's message array to remove the user message and everything after it.
    disc.branches[branchId] = sourceBranchMessages.slice(0, userMessageIndex);
    
    // The branch we just modified now becomes the active one for rendering purposes.
    activeBranchId = branchId;
    currentMessages = disc.branches[branchId];

    // Re-render the UI to show the truncated history.
    renderMessages(currentMessages);
    forceScrollToBottom();

    // Prepare the payload to resend the user's prompt.
    const resendPayload = {
        prompt: userMessageData.content,
        image_server_paths: userMessageData.server_image_paths || []
    };
    
    // Send the message. The backend will handle creating the new branch history
    // because we are sending from an older parent message ID.
    await sendMessage(parentMessageId, resendPayload);
}

async function switchBranch(discussionId, branchIdentifier) {
    const disc = discussions[discussionId];
    if (!disc || !branchIdentifier || disc.activeBranchId === branchIdentifier || generationInProgress) {
        return;
    }

    showStatus(translate('status_switching_branch', `Switching branch...`), 'info');

    // Set the target branch to load. selectDiscussion will handle fetching and state correction.
    disc.activeBranchId = branchIdentifier;
    
    try {
        // selectDiscussion will now fetch messages using branchIdentifier, find the true tip,
        // and correct the local state (disc.activeBranchId).
        await selectDiscussion(discussionId);

        // After selectDiscussion has corrected the state, we send the *correct* tip ID to the backend
        // to ensure the session is in sync for future loads.
        await apiRequest(`/api/discussions/${discussionId}/active_branch`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ active_branch_id: disc.activeBranchId })
        });
        
        showStatus(translate('status_branch_switched_success', 'Branch switched.'), 'success');
    } catch (error) {
        showStatus(translate('status_failed_to_switch_branch', "Failed to switch branch."), "error");
    }
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

if (ragDataStoreSelect) ragDataStoreSelect.onchange = async () => {
    if (!currentDiscussionId || !discussions[currentDiscussionId]) return;
    const disc = discussions[currentDiscussionId];
    const selectedDataStoreId = ragDataStoreSelect.value || null;
    
    if (disc.rag_datastore_id !== selectedDataStoreId) {
        disc.rag_datastore_id = selectedDataStoreId;
        await updateDiscussionRagStoreOnBackend(currentDiscussionId, selectedDataStoreId);
    }
    updateRagToggleButtonState();
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
    closeModal('createDataStoreModal')
    openModal("dataStoresModal")
}

async function handleEditDataStore(event) {
    event.preventDefault();
    const name = editDataStoreNameInput.value.trim();
    const new_name = editDataStoreNewNameInput.value.trim();
    const description = editDataStoreDescriptionInput.value.trim();
    if (!name) { showStatus(translate('datastores_name_required_error'), "error", editDataStoreStatus); return; }
    showStatus(translate('status_creating_datastore', "Creating data store..."), "info", editDataStoreStatus);
    try {
        await apiRequest('/api/datastores/edit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, new_name, description }),
            statusElement: editDataStoreStatus
        });
        showStatus(translate('status_datastore_edited_success', `Data Store "${name}" edited.`, {name: name}), "success", editDataStoreStatus);
        editDataStoreForm.reset();
        openModal('dataStoresModal');
        closeModal("editDataStoresModal")
        await loadDataStores(); 
    } catch (error) { /* Handled by apiRequest */ }
}

function initiateEditDataStore(id, name, description) { 
    closeModal('dataStoresModal'); 
    editDataStoreNameInput.value = name;
    editDataStoreNewNameInput.value = name;
    editDataStoreDescriptionInput.value = description;
    showStatus(translate('status_editing_datastore_note', `Editing store: ${name}.`, {name: name}), 'info', createDataStoreStatus);
    openModal("editDataStoresModal")
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
    if (!ragToggleBtn || !ragDataStoreSelect) return;
    
    const hasDataStores = availableDataStoresForRag.length > 0;
    const disc = currentDiscussionId ? discussions[currentDiscussionId] : null;
    const ragIsOn = disc && disc.rag_datastore_id;

    ragToggleBtn.disabled = !hasDataStores;
    
    if (!hasDataStores) {
        ragToggleBtn.classList.remove('rag-toggle-on');
        ragToggleBtn.classList.add('rag-toggle-off');
        ragToggleBtn.title = translate('rag_toggle_btn_title_no_stores');
        ragDataStoreSelect.style.display = 'none';
        return;
    }

    ragDataStoreSelect.style.display = 'inline-block';
    
    if (ragIsOn) {
        ragToggleBtn.classList.remove('rag-toggle-off');
        ragToggleBtn.classList.add('rag-toggle-on');
        const selectedDS = availableDataStoresForRag.find(ds => ds.id === disc.rag_datastore_id);
        const datastoreNameText = selectedDS ? `(Using: ${selectedDS.name})` : '(Store selected)';
        ragToggleBtn.title = translate('rag_toggle_btn_title_on', `RAG Active ${datastoreNameText} - Click to disable`, {datastore_name: datastoreNameText});
    } else {
        ragToggleBtn.classList.remove('rag-toggle-on');
        ragToggleBtn.classList.add('rag-toggle-off');
        ragToggleBtn.title = translate('rag_toggle_btn_title_off');
    }

    if (disc) {
        ragDataStoreSelect.value = disc.rag_datastore_id || "";
    } else {
        ragDataStoreSelect.value = "";
    }
}
function renderCustomCodeBlocks(element, messageId) {
    element.querySelectorAll('pre').forEach((preElement) => {
        if (preElement.parentElement.classList.contains('code-block-wrapper')) return;

        const codeElement = preElement.querySelector('code');
        if (!codeElement) return;

        // Determine language
        let language = 'plaintext';
        const langClass = Array.from(codeElement.classList).find(cls => cls.startsWith('language-'));
        if (langClass) {
            language = langClass.replace('language-', '');
        } else {
            const hljsLang = Array.from(codeElement.classList).find(cls => hljs.getLanguage(cls));
            if (hljsLang) language = hljsLang;
        }

        const code = codeElement.textContent || '';

        // Create wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'code-block-wrapper';

        // Create header
        const header = document.createElement('div');
        header.className = 'code-block-header';

        const langLabel = document.createElement('span');
        langLabel.className = 'text-xs font-semibold';
        langLabel.textContent = language;

        const buttons = document.createElement('div');
        buttons.className = 'code-block-buttons';

        // Copy button
        const copyBtn = document.createElement('button');
        copyBtn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 inline-block mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            <span data-translate-key="copy_code_btn_text">${translate('copy_code_btn_text', 'Copy')}</span>
        `;
        copyBtn.title = translate('copy_code_tooltip');

        const showCopied = () => {
            const span = copyBtn.querySelector('span');
            const original = span.textContent;
            span.textContent = translate('copied_code_btn_text', 'Copied!');
            setTimeout(() => (span.textContent = original), 1500);
        };

        const fallbackCopy = (text) => {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.top = '0';
            textarea.style.left = '0';
            document.body.appendChild(textarea);
            textarea.focus();
            textarea.select();
            try {
                document.execCommand('copy');
            } catch (err) {
                console.error('Fallback copy failed', err);
            }
            document.body.removeChild(textarea);
            showCopied();
        };

        copyBtn.onclick = () => {
            if (navigator.clipboard?.writeText) {
                navigator.clipboard.writeText(code)
                    .then(showCopied)
                    .catch(err => {
                        console.error('Clipboard API failed', err);
                        fallbackCopy(code);
                    });
            } else {
                fallbackCopy(code);
            }
        };

        buttons.appendChild(copyBtn);

        // Optional: Python run button
        if (language.toLowerCase() === 'python') {
            const execBtn = document.createElement('button');
            execBtn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 inline-block mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                    <path stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span data-translate-key="run_code_btn_text">${translate('run_code_btn_text', 'Run')}</span>
            `;
            execBtn.title = translate('execute_python_code_tooltip');
            execBtn.onclick = () => executePythonCode(code, wrapper);
            buttons.appendChild(execBtn);
        }

        // Final assembly
        header.appendChild(langLabel);
        header.appendChild(buttons);
        wrapper.appendChild(header);

        preElement.classList.add('relative');
        wrapper.appendChild(preElement.cloneNode(true));

        // Replace pre with wrapper
        preElement.parentNode.replaceChild(wrapper, preElement);

        // Highlight after insertion
        const newCodeElement = wrapper.querySelector('code');
        if (newCodeElement) hljs.highlightElement(newCodeElement);
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
    ragDataStoreSelect.style.display = (hasDataStores) ? 'inline-block' : 'none';

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

settingsLollmsModelSelect.onchange = () => { saveLLMParamsBtn.disabled = (settingsLollmsModelSelect.value === currentUser.lollms_model_name); };

saveLLMParamsBtn.onclick = async () => {
    const selectedModel = settingsLollmsModelSelect.value;
    let modelChanged = selectedModel && selectedModel !== currentUser.lollms_model_name;
    if (!modelChanged) return;

    showStatus(translate('status_saving_model', 'Saving model...'), 'info', settingsStatus_llmConfig); 
    saveLLMParamsBtn.disabled = true;
    try {
        if (modelChanged) {
            const formData = new FormData(); formData.append('model_name', selectedModel);
            await apiRequest('/api/config/lollms-model', { method: 'POST', body: formData, statusElement: settingsStatus_llmConfig });
            currentUser.lollms_model_name = selectedModel;
        }
        showStatus(translate('status_model_saved_success', 'Model saved. LLM Client will re-init if model changed.'), 'success', settingsStatus_llmConfig);
    } catch (error) { /* Handled by apiRequest */ 
    } finally {
        saveLLMParamsBtn.disabled = (settingsLollmsModelSelect.value === currentUser.lollms_model_name);
    }
};

[settingsTemperature, settingsTopK, settingsTopP, settingsRepeatPenalty, settingsRepeatLastN, settingsContextSize].forEach(el => {
    el.oninput = () => { saveLLMParamsBtn.disabled = false; };
});

saveLLMParamsBtn.onclick = async () => {
    const params = {
        llm_ctx_size: parseInt(settingsContextSize.value) || null,
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
    if (!settingsLollmsModelSelect || !currentUser || !saveLLMParamsBtn || !settingsContextSize || !settingsTemperature || !settingsTopK || !settingsTopP || !settingsRepeatPenalty || !settingsRepeatLastN || !saveLLMParamsBtn) return;

    const selectedModel = settingsLollmsModelSelect.value;
    let modelChanged = selectedModel && selectedModel !== currentUser.lollms_model_name;
    if (modelChanged) {
        showStatus(translate('status_saving_model', 'Saving model...'), 'info', settingsStatus_llmConfig);
        saveLLMParamsBtn.disabled = true;
        try {
            const formData = new FormData(); formData.append('model_name', selectedModel);
            await apiRequest('/api/config/lollms-model', { method: 'POST', body: formData, statusElement: settingsStatus_llmConfig });
            currentUser.lollms_model_name = selectedModel; // Update local currentUser state
            showStatus(translate('status_model_saved_success', 'Model saved. LLM Client will re-init if model changed.'), 'success', settingsStatus_llmConfig);
        } catch (error) {
            // apiRequest should handle showing the error status
            saveLLMParamsBtn.disabled = false; // Re-enable on error
        } finally {
            // Disable button again only if selection matches current user setting (or it was re-enabled by error)
            if (settingsLollmsModelSelect.value === currentUser.lollms_model_name && !saveLLMParamsBtn.disabled) {
                 saveLLMParamsBtn.disabled = true;
            }
        }        
    }
    handleSaveLLMParams()

}

// **RENAMED AND DEFINED AS SEPARATE FUNCTION**
async function handleSaveLLMParams() {

    const params = {
        llm_ctx_size: parseInt(settingsContextSize.value) || null,
        llm_temperature: parseFloat(settingsTemperature.value) || null,
        llm_top_k: parseInt(settingsTopK.value) || null,
        llm_top_p: parseFloat(settingsTopP.value) || null,
        llm_repeat_penalty: parseFloat(settingsRepeatPenalty.value) || null,
        llm_repeat_last_n: parseInt(settingsRepeatLastN.value) || null,
        put_thoughts_in_context: settingsPutThoughts.checked,
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

    showStatus(translate('status_saving_llm_params', 'Saving LLM parameters...'), 'info', settingsStatus_llmConfig);
    saveLLMParamsBtn.disabled = true;
    try {
        await apiRequest('/api/config/llm-params', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            statusElement: settingsStatus_llmParams
        });
        if (currentUser) Object.assign(currentUser, payload); // Update local state
        showStatus(translate('status_llm_params_saved_success', 'LLM parameters saved.'), 'success', settingsStatus_llmConfig);
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

async function populateSettingsModal() {
    if (!currentUser) return;
    populateDropdown(settingsLollmsModelSelect, availableLollmsModels, currentUser.lollms_model_name, translate('settings_no_models_found'));
    saveLLMParamsBtn.disabled = true;
    showStatus('', 'info', settingsStatus_llmConfig);
    
    // LLM Parameters Tab
    
    if(settingsContextSize) settingsContextSize.value = currentUser.llm_ctx_size ?? '';
    if(settingsTemperature) settingsTemperature.value = currentUser.llm_temperature ?? '';
    if(settingsTopK) settingsTopK.value = currentUser.llm_top_k ?? '';
    if(settingsTopP) settingsTopP.value = currentUser.llm_top_p ?? '';
    if(settingsRepeatPenalty) settingsRepeatPenalty.value = currentUser.llm_repeat_penalty ?? '';
    if(settingsRepeatLastN) settingsRepeatLastN.value = currentUser.llm_repeat_last_n ?? '';
    if(settingsPutThoughts) settingsPutThoughts.checked = currentUser.put_thoughts_in_context || false; // New
    if(saveLLMParamsBtn) saveLLMParamsBtn.disabled = true;
    showStatus('', 'info', settingsStatus_llmParams);

    // Profile Tab
    if(settingsFirstName) settingsFirstName.value = currentUser.first_name || '';
    if(settingsFamilyName) settingsFamilyName.value = currentUser.family_name || '';
    if(settingsEmail) settingsEmail.value = currentUser.email || '';
    if(settingsBirthDate) settingsBirthDate.value = currentUser.birth_date || ''; // Format: YYYY-MM-DD
    if(saveProfileBtn) saveProfileBtn.disabled = true;
    showStatus('', 'info', settingsStatus_profile);

    // Personalities Tab
    await loadAndPopulatePersonalitiesTab(); // New function
    if(saveActivePersonalityBtn) saveActivePersonalityBtn.disabled = true;
    showStatus('', 'info', settingsStatus_personalities);


    // RAG Parameters Tab
    if(settingsRagTopK) settingsRagTopK.value = currentUser.rag_top_k ?? '';
    if(settingsRagMAXLEN) settingsRagMAXLEN.value = currentUser.max_rag_len ?? '';
    if(settingsRagNBHops) settingsRagNBHops.value = currentUser.rag_n_hops ?? '';
    
    if(settingsRagMinSimPercent) settingsRagMinSimPercent.value = currentUser.rag_min_sim_percent ?? '';
    
    if(settingsRagUseGraph) settingsRagUseGraph.checked = currentUser.rag_use_graph || false;
    if(settingsRagGraphResponseType) settingsRagGraphResponseType.value = currentUser.rag_graph_response_type || 'chunks_summary';

    toggleRagGraphResponseTypeVisibility();

    if(saveRagParamsBtn) saveRagParamsBtn.disabled = true;
    showStatus('', 'info', settingsStatus_ragParams);


    // Account Tab (Password)
    if(settingsCurrentPassword) settingsCurrentPassword.value = '';
    if(settingsNewPassword) settingsNewPassword.value = '';
    if(settingsConfirmPassword) settingsConfirmPassword.value = '';
    if(changePasswordBtn) changePasswordBtn.disabled = true;
    showStatus('', 'info', passwordChangeStatus);
    
    handleSettingsTabSwitch('llmConfigTab'); // Default to first tab or a preferred one
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

async function handleSaveProfile() {
    if (!currentUser || !saveProfileBtn) return;
    const payload = {
        first_name: settingsFirstName.value || null,
        family_name: settingsFamilyName.value || null,
        email: settingsEmail.value || null,
        birth_date: settingsBirthDate.value || null,
    };
    showStatus(translate('status_saving_profile', 'Saving profile...'), 'info', settingsStatus_profile);
    saveProfileBtn.disabled = true;
    try {
        // API endpoint: PUT /api/users/me/profile (or similar)
        const response = await apiRequest('/api/auth/me', { // CORRECTED URL
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            statusElement: settingsStatus_profile // Or the relevant status element
        });
        const updatedUser = await response.json(); // Backend should return updated UserAuthDetails or UserPublic
        Object.assign(currentUser, updatedUser); // Update local currentUser
        // Update usernameDisplay if first/last name is used there
        if (usernameDisplay && currentUser.first_name) usernameDisplay.textContent = `${currentUser.first_name} (${currentUser.username})`;
        else if (usernameDisplay) usernameDisplay.textContent = currentUser.username;

        showStatus(translate('status_profile_saved_success', 'Profile saved successfully.'), 'success', settingsStatus_profile);
    } catch (error) { /* apiRequest handles status */
    } finally {
        saveProfileBtn.disabled = true; // Disable again after attempt
    }
}

async function handleSaveActivePersonality() {
    if (!currentUser || !saveActivePersonalityBtn) return;
    const selectedPersonalityId = settingsActivePersonality.value || null;
    
    showStatus(translate('status_saving_active_personality', 'Saving active personality...'), 'info', settingsStatus_personalities);
    saveActivePersonalityBtn.disabled = true;
    try {
        const response = await apiRequest('/api/auth/me', { // CORRECTED URL
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ active_personality_id: selectedPersonalityId }),
            statusElement: settingsStatus_personalities
        });
        const updatedUser = await response.json();
        currentUser.active_personality_id = updatedUser.active_personality_id;
        // If the active personality changed, you might need to update the session prompt in JS too
        // or rely on the backend to have updated it and the next /me call to reflect it.
        // For immediate effect:
        if (updatedUser.active_personality_id) {
            const activePers = [...userPersonalitiesCache, ...publicPersonalitiesCache].find(p => p.id === updatedUser.active_personality_id);
            if (activePers) {
                // This assumes the full personality object is cached client-side
                // A more robust way would be to fetch the prompt if not already available
                // Or the backend could return the new prompt text as part of UserAuthDetails
                // For now, let's assume the frontend needs to manage this if not returned by /api/auth/me
            }
        } else {
            // Clear active personality prompt if it was unset
        }

        showStatus(translate('status_active_personality_saved_success', 'Active personality saved.'), 'success', settingsStatus_personalities);
    } catch (error) { /* apiRequest handles status */
    } finally {
        saveActivePersonalityBtn.disabled = true;
    }
}

async function handleSaveRagParams() {
    if (!currentUser || !saveRagParamsBtn) return;
    const payload = {
        rag_top_k: parseInt(settingsRagTopK.value) || null,
        max_rag_len: parseInt(settingsRagMAXLEN.value) || null,
        rag_n_hops: parseInt(settingsRagNBHops.value) || null,
        rag_min_sim_percent: parseFloat(settingsRagMinSimPercent.value) || null,
        rag_use_graph: settingsRagUseGraph.checked,
        rag_graph_response_type: settingsRagGraphResponseType.value,
    };
    showStatus(translate('status_saving_rag_params', 'Saving RAG parameters...'), 'info', settingsStatus_ragParams);
    saveRagParamsBtn.disabled = true;
    try {
        // API endpoint: PUT /api/users/me/settings (or similar)
        const response = await apiRequest('/api/auth/me', { // Assuming general update endpoint
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            statusElement: settingsStatus_ragParams
        });
        const updatedUser = await response.json();
        Object.assign(currentUser, updatedUser); // Update local currentUser
        userDefaultVectorizer = currentUser.safe_store_vectorizer; // Update global if changed
        showStatus(translate('status_rag_params_saved_success', 'RAG parameters saved.'), 'success', settingsStatus_ragParams);
    } catch (error) { /* apiRequest handles status */
    } finally {
        saveRagParamsBtn.disabled = true;
    }
}

// --- Personality Management Functions (Stubs) ---
let userPersonalitiesCache = [];
let publicPersonalitiesCache = [];


async function loadAndPopulatePersonalitiesTab() {
    if (!settingsActivePersonality || !userPersonalitiesList || !publicPersonalitiesList) {
        console.error("Personality tab elements not found.");
        return;
    }
    
    // Clear previous content and show loading state
    settingsActivePersonality.innerHTML = `<option value="">${translate('settings_personalities_none_active', 'None (Default)')}</option>`;
    userPersonalitiesList.innerHTML = `<p class="italic text-sm text-gray-400">${translate('loading_personalities_placeholder', 'Loading your personalities...')}</p>`;
    publicPersonalitiesList.innerHTML = `<p class="italic text-sm text-gray-400">${translate('loading_personalities_placeholder', 'Loading public personalities...')}</p>`;
    if(saveActivePersonalityBtn) saveActivePersonalityBtn.disabled = true; // Disable save until populated

    try {
        // Fetch user's owned personalities
        const ownedResponse = await apiRequest('/api/personalities/my');
        userPersonalitiesCache = await ownedResponse.json();
        
        // Fetch public personalities
        const publicResponse = await apiRequest('/api/personalities/public');
        publicPersonalitiesCache = await publicResponse.json();

        // Populate active personality dropdown
        // Combine owned and public, ensuring public ones are only added if not already "owned" by the user
        // (though with UUIDs, an owned one shouldn't have the same ID as a system public one unless cloned with same ID, which is unlikely here)
        
        const activePersonalityOptions = [];
        // Add user's personalities first
        userPersonalitiesCache.forEach(p => {
            activePersonalityOptions.push({ id: p.id, name: p.name, author: p.author || currentUser.username, is_owned: true });
        });

        // Add public personalities, avoiding duplicates by name if an owned one has the same name (user might have cloned)
        // A better approach for "using" public ones might be just referencing their ID, not cloning by default.
        publicPersonalitiesCache.forEach(pp => {
            if (!userPersonalitiesCache.some(up => up.id === pp.id)) { // Check by ID for system personalities
                 activePersonalityOptions.push({ id: pp.id, name: pp.name, author: pp.author || 'System', is_owned: false });
            }
        });
        
        activePersonalityOptions.sort((a, b) => a.name.localeCompare(b.name));

        activePersonalityOptions.forEach(p => {
            const option = document.createElement('option');
            option.value = p.id;
            let displayName = p.name;
            if (!p.is_owned && p.author && p.author.toLowerCase() !== 'system') {
                displayName += ` (${translate('personality_author_prefix', 'by')} ${p.author})`;
            } else if (!p.is_owned) {
                displayName += ` (${translate('personality_public_suffix', 'Public')})`;
            }
            option.textContent = displayName;
            settingsActivePersonality.appendChild(option);
        });

        if (currentUser.active_personality_id) {
            settingsActivePersonality.value = currentUser.active_personality_id;
        } else {
            settingsActivePersonality.value = ""; // Ensure "None" is selected if no active ID
        }

        renderUserPersonalitiesList(); // Uses userPersonalitiesCache
        renderPublicPersonalitiesList(); // Uses publicPersonalitiesCache

    } catch (error) {
        console.error("Error loading personalities for tab:", error);
        showStatus(translate('error_loading_personalities', 'Error loading personalities.'), 'error', settingsStatus_personalities);
        userPersonalitiesList.innerHTML = `<p class="italic text-sm text-red-400">${translate('error_loading_personalities')}</p>`;
        publicPersonalitiesList.innerHTML = `<p class="italic text-sm text-red-400">${translate('error_loading_personalities')}</p>`;
    }
}

function renderUserPersonalitiesList() {
    userPersonalitiesList.innerHTML = '';
    if (userPersonalitiesCache.length === 0) {
        userPersonalitiesList.innerHTML = `<p class="italic text-sm text-gray-400">${translate('no_user_personalities_placeholder', 'You have not created any personalities yet.')}</p>`;
        return;
    }
    userPersonalitiesCache.sort((a,b) => a.name.localeCompare(b.name)).forEach(p => {
        const item = createPersonalityListItem(p, true); // true for owned
        userPersonalitiesList.appendChild(item);
    });
    updateUIText();
}

function renderPublicPersonalitiesList() {
    publicPersonalitiesList.innerHTML = '';
    if (publicPersonalitiesCache.length === 0) {
        publicPersonalitiesList.innerHTML = `<p class="italic text-sm text-gray-400">${translate('no_public_personalities_placeholder', 'No public personalities available.')}</p>`;
        return;
    }
    publicPersonalitiesCache.sort((a,b) => (a.category || '').localeCompare(b.category || '') || a.name.localeCompare(b.name)).forEach(p => {
        // Only show public personalities that the user doesn't "own" (i.e., doesn't have a private copy with the same ID)
        // System personalities have owner_user_id = null. If a user "clones" one, it gets their owner_user_id.
        // The check `!userPersonalitiesCache.some(up => up.id === p.id)` is good if IDs are truly unique.
        // For display, we just list all from publicPersonalitiesCache.
        const item = createPersonalityListItem(p, false); // false for public
        publicPersonalitiesList.appendChild(item);
    });
    updateUIText();
}

// Ensure createPersonalityListItem is robust for public personalities
function createPersonalityListItem(p, isOwned) {
    const div = document.createElement('div');
    div.className = 'flex justify-between items-center py-1.5 px-2 hover:bg-gray-750 rounded text-sm transition-colors duration-150';
    
    const infoDiv = document.createElement('div');
    infoDiv.className = 'flex items-center space-x-2 flex-grow min-w-0'; // min-w-0 for truncate

    if (p.icon_base64) {
        const iconImg = document.createElement('img');
        iconImg.src = p.icon_base64;
        iconImg.alt = ''; // Decorative
        iconImg.className = 'w-6 h-6 rounded-sm flex-shrink-0 object-cover';
        infoDiv.appendChild(iconImg);
    } else {
        // Placeholder icon if none provided
        const placeholderIcon = document.createElement('div');
        placeholderIcon.className = 'w-6 h-6 rounded-sm flex-shrink-0 bg-gray-600 flex items-center justify-center text-xs';
        placeholderIcon.textContent = p.name.charAt(0).toUpperCase();
        infoDiv.appendChild(placeholderIcon);
    }

    const textDiv = document.createElement('div');
    textDiv.className = 'flex flex-col min-w-0'; // min-w-0 for truncate

    const nameSpan = document.createElement('span');
    nameSpan.textContent = p.name;
    nameSpan.className = 'font-medium truncate';
    nameSpan.title = p.name;
    textDiv.appendChild(nameSpan);

    if (p.category) {
        const categorySpan = document.createElement('span');
        categorySpan.textContent = p.category;
        categorySpan.className = 'text-xs text-gray-400 truncate';
        categorySpan.title = p.category;
        textDiv.appendChild(categorySpan);
    }
    infoDiv.appendChild(textDiv);

    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'space-x-1 flex-shrink-0 ml-2';

    if (isOwned) {
        const editBtn = createActionButton('edit', translate('edit_personality_tooltip'), () => openPersonalityEditor(p.id));
        actionsDiv.appendChild(editBtn);
        
        const sendBtn = createActionButton('send', translate('send_personality_tooltip', 'Send to Friend'), () => openSendPersonalityModal(p.id, p.name));
        actionsDiv.appendChild(sendBtn);

        const deleteBtn = createActionButton('delete', translate('delete_personality_tooltip'), () => deletePersonality(p.id, p.name), 'destructive');
        actionsDiv.appendChild(deleteBtn);
    } else { // Public personality
        const useBtn = document.createElement('button');
        useBtn.textContent = translate('use_personality_btn', 'Use');
        useBtn.className = 'btn btn-xs btn-secondary'; // Use secondary style
        useBtn.title = translate('use_public_personality_tooltip', `Set "${p.name}" as active personality`);
        useBtn.onclick = (e) => { 
            e.stopPropagation();
            settingsActivePersonality.value = p.id;
            if(saveActivePersonalityBtn) saveActivePersonalityBtn.disabled = (settingsActivePersonality.value === (currentUser.active_personality_id || ""));
            showStatus(translate('status_personality_selected_save_prompt', `Selected "${p.name}". Click "Save Active Personality" to apply.`), 'info', settingsStatus_personalities);
        };
        actionsDiv.appendChild(useBtn);
        // Optional: "Clone to My Personalities" button
        const cloneBtn = document.createElement('button');
        cloneBtn.textContent = translate('clone_personality_btn', 'Clone');
        cloneBtn.className = 'btn btn-xs btn-outline'; // Define btn-outline
        cloneBtn.onclick = () => clonePublicPersonality(p);
        actionsDiv.appendChild(cloneBtn);
    }
    div.appendChild(infoDiv);
    div.appendChild(actionsDiv);
    return div;
}

async function clonePublicPersonality(p) {
    const id = personalityEditorId.value;
    const payload = {
        ...p, // Spread all properties from p into payload
        is_public: false // Ensure is_public is set to false
    };

    if (!payload.name || !payload.prompt_text) {
        showStatus(translate('error_personality_name_prompt_required', 'Name and System Prompt are required.'), 'error', personalityEditorStatus);
        return;
    }

    const method = id ? 'PUT' : 'POST';
    const url = id ? `/api/personalities/${id}` : '/api/personalities';

    showStatus(translate(id ? 'status_saving_personality' : 'status_creating_personality', id ? 'Saving personality...' : 'Creating personality...'), 'info', personalityEditorStatus);
    savePersonalityBtn.disabled = true;

    try {
        await apiRequest(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            statusElement: personalityEditorStatus
        });
        showStatus(translate(id ? 'status_personality_saved_success' : 'status_personality_created_success', id ? 'Personality saved.' : 'Personality created.'), 'success', personalityEditorStatus);
        await loadAndPopulatePersonalitiesTab(); // Refresh lists
        setTimeout(() => closeModal('personalityEditorModal'), 1000);
    } catch (error) { /* apiRequest handles status */
    } finally {
        savePersonalityBtn.disabled = false;
    }
}

function openPersonalityEditor(personalityId) {
    // Reset form
    personalityEditorId.value = personalityId || '';
    personalityName.value = '';
    personalityCategory.value = '';
    personalityAuthor.value = '';
    personalityDescription.value = '';
    personalityPromptText.value = '';
    personalityDisclaimer.value = '';
    personalityScriptCode.value = '';
    personalityIconUpload.value = '';
    personalityIconPreview.src = '#';
    personalityIconPreview.classList.add('hidden');
    personalityIconBase64.value = '';
    showStatus('', 'info', personalityEditorStatus);

    if (personalityId) {
        personalityEditorTitle.textContent = translate('edit_personality_modal_title', 'Edit Personality');
        const personality = userPersonalitiesCache.find(p => p.id === personalityId);
        if (personality) {
            personalityName.value = personality.name;
            personalityCategory.value = personality.category || '';
            personalityAuthor.value = personality.author || '';
            personalityDescription.value = personality.description || '';
            personalityPromptText.value = personality.prompt_text;
            personalityDisclaimer.value = personality.disclaimer || '';
            personalityScriptCode.value = personality.script_code || '';
            if (personality.icon_base64) {
                personalityIconPreview.src = personality.icon_base64;
                personalityIconPreview.classList.remove('hidden');
                personalityIconBase64.value = personality.icon_base64;
            }
        } else {
            showStatus(translate('error_personality_not_found_for_edit', 'Error: Personality not found for editing.'), 'error', personalityEditorStatus);
            return; // Don't open modal if data not found
        }
    } else {
        personalityEditorTitle.textContent = translate('create_personality_modal_title', 'Create New Personality');
    }
    openModal('personalityEditorModal', false);
}

function handlePersonalityIconChange(event) {
    const file = event.target.files[0];
    if (file) {
        if (file.size > 256 * 1024) { // Max 256KB for icon
            showStatus(translate('error_icon_too_large', 'Icon image too large (max 256KB).'), 'error', personalityEditorStatus);
            personalityIconUpload.value = ''; return;
        }
        const reader = new FileReader();
        reader.onload = (e) => {
            personalityIconPreview.src = e.target.result;
            personalityIconPreview.classList.remove('hidden');
            personalityIconBase64.value = e.target.result; // This is data URL
        };
        reader.readAsDataURL(file);
    }
}

async function handleSavePersonality() {
    const id = personalityEditorId.value;
    const payload = {
        name: personalityName.value.trim(),
        category: personalityCategory.value.trim() || null,
        author: personalityAuthor.value.trim() || currentUser.username, // Default to current user
        description: personalityDescription.value.trim() || null,
        prompt_text: personalityPromptText.value.trim(),
        disclaimer: personalityDisclaimer.value.trim() || null,
        script_code: personalityScriptCode.value.trim() || null,
        icon_base64: personalityIconBase64.value || null,
        is_public: false // User created personalities are private by default
    };

    if (!payload.name || !payload.prompt_text) {
        showStatus(translate('error_personality_name_prompt_required', 'Name and System Prompt are required.'), 'error', personalityEditorStatus);
        return;
    }

    const method = id ? 'PUT' : 'POST';
    const url = id ? `/api/personalities/${id}` : '/api/personalities';

    showStatus(translate(id ? 'status_saving_personality' : 'status_creating_personality', id ? 'Saving personality...' : 'Creating personality...'), 'info', personalityEditorStatus);
    savePersonalityBtn.disabled = true;

    try {
        await apiRequest(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            statusElement: personalityEditorStatus
        });
        showStatus(translate(id ? 'status_personality_saved_success' : 'status_personality_created_success', id ? 'Personality saved.' : 'Personality created.'), 'success', personalityEditorStatus);
        await loadAndPopulatePersonalitiesTab(); // Refresh lists
        setTimeout(() => closeModal('personalityEditorModal'), 1000);
    } catch (error) { /* apiRequest handles status */
    } finally {
        savePersonalityBtn.disabled = false;
    }
}

async function deletePersonality(id, name) {
    if (!confirm(translate('confirm_delete_personality', `Are you sure you want to delete personality "${name}"?`, { name: name }))) return;
    
    showStatus(translate('status_deleting_personality', `Deleting personality "${name}"...`, { name: name }), 'info', settingsStatus_personalities);
    try {
        await apiRequest(`/api/personalities/${id}`, { method: 'DELETE', statusElement: settingsStatus_personalities });
        showStatus(translate('status_personality_deleted_success', 'Personality deleted.'), 'success', settingsStatus_personalities);
        if (currentUser.active_personality_id === id) { // If deleted personality was active
            currentUser.active_personality_id = null;
            // Optionally, call backend to update user's active_personality_id to null
            await apiRequest('/api/users/me', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ active_personality_id: null })
            });
        }
        await loadAndPopulatePersonalitiesTab(); // Refresh lists
    } catch (error) { /* apiRequest handles status */ }
}


function openFriendsMessagesModal() {
    if (!currentUser) return;
    userMenuDropdown.style.display = 'none'; // Close user menu
    userMenuArrow.classList.remove('rotate-180');
    
    // Reset status messages
    showStatus('', 'info', addFriendStatus);
    
    // Load initial data for the default tab (e.g., Friends List)
    handleFriendsMessagesTabSwitch('friendsListTab'); // Switch to default tab
    loadFriendsList();
    loadPendingFriendRequests(); // Load requests to update badge even if not default tab

    openModal('friendsMessagesModal');
}

function handleFriendsMessagesTabSwitch(tabId) {
    document.querySelectorAll('#friendsMessagesModal .friends-messages-tab-content').forEach(content => {
        content.style.display = 'none';
    });
    document.querySelectorAll('#friendsMessagesModal .friends-messages-tab-btn').forEach(button => {
        button.classList.remove('active-tab');
    });

    const tabContent = document.getElementById(tabId);
    const tabButton = document.querySelector(`#friendsMessagesModal .friends-messages-tab-btn[data-tab="${tabId}"]`);
    
    if(tabContent) tabContent.style.display = 'block';
    if(tabButton) tabButton.classList.add('active-tab');

    // Load data for the selected tab if not already loaded or needs refresh
    if (tabId === 'friendsListTab') {
        loadFriendsList();
    } else if (tabId === 'friendRequestsTab') {
        loadPendingFriendRequests();
    } else if (tabId === 'directMessagesTab') {
        dmChatArea.classList.add('hidden'); // Hide chat area initially
        dmNoConversationSelected.classList.remove('hidden'); // Show placeholder
        dmNoConversationSelected.style.display = 'flex'; // Ensure it's flex for centering
        loadDmConversations();
        if(dmSearchUsersInput) dmSearchUsersInput.value = '';
        if(dmSearchResults) dmSearchResults.innerHTML = ''; dmSearchResults.classList.add('hidden');
    }
}



//---- Friendship ----
async function handleSendFriendRequest() {
    const targetUsername = addFriendInput.value.trim();
    if (!targetUsername) {
        showStatus(translate('error_friend_username_required', 'Username is required.'), 'error', addFriendStatus);
        return;
    }
    showStatus(translate('status_sending_friend_request', `Sending request to ${targetUsername}...`, {username: targetUsername}), 'info', addFriendStatus);
    sendFriendRequestBtn.disabled = true;
    try {
        await apiRequest('/api/friends/request', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_username: targetUsername }),
            statusElement: addFriendStatus
        });
        showStatus(translate('status_friend_request_sent_success', `Friend request sent to ${targetUsername}.`, {username: targetUsername}), 'success', addFriendStatus);
        addFriendInput.value = '';
        // Optionally, refresh pending sent requests if you display them
    } catch (error) {
        // apiRequest will show the error in addFriendStatus
    } finally {
        sendFriendRequestBtn.disabled = false;
    }
}

async function loadFriendsList() {
    if (!friendsListContainerFM) return;
    friendsListContainerFM.innerHTML = `<p class="italic text-sm text-gray-400" data-translate-key="loading_friends_list">Loading friends...</p>`;
    try {
        const response = await apiRequest('/api/friends');
        const friends = await response.json(); // Expects List[FriendPublic]
        renderFriendsList(friends);
    } catch (error) {
        friendsListContainerFM.innerHTML = `<p class="italic text-sm text-red-400">${translate('error_loading_friends_list', 'Failed to load friends list.')}</p>`;
    }
}

function renderFriendsList(friends) {
    friendsListContainerFM.innerHTML = '';
    if (friends.length === 0) {
        friendsListContainerFM.innerHTML = `<p class="italic text-sm text-gray-400" data-translate-key="no_friends_yet_placeholder">You haven't added any friends yet.</p>`;
        return;
    }
    friends.forEach(friend => {
        const friendDiv = document.createElement('div');
        friendDiv.className = 'flex items-center justify-between p-2 bg-gray-750 rounded-md hover:bg-gray-700 transition-colors';
        
        const friendInfo = document.createElement('div');
        friendInfo.className = 'flex items-center space-x-2';
        // Placeholder for avatar - you can generate one like in messages
        const avatarPlaceholder = document.createElement('div');
        avatarPlaceholder.className = 'w-8 h-8 bg-gray-600 rounded-full flex items-center justify-center text-sm font-semibold';
        avatarPlaceholder.textContent = friend.username.charAt(0).toUpperCase();
        friendInfo.appendChild(avatarPlaceholder);
        const nameSpan = document.createElement('span');
        nameSpan.textContent = friend.username;
        nameSpan.className = 'font-medium';
        friendInfo.appendChild(nameSpan);
        
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'space-x-2';

        const messageBtn = createActionButton('chat_bubble', translate('message_friend_tooltip', `Message ${friend.username}`), () => openDirectMessage(friend.id, friend.username));
        actionsDiv.appendChild(messageBtn);
        
        const unfriendBtn = createActionButton('person_remove', translate('unfriend_tooltip', `Unfriend ${friend.username}`), () => unfriendUser(friend.id, friend.username), 'destructive');
        actionsDiv.appendChild(unfriendBtn);

        // Optional: Block button directly in friend list
        const blockBtn = createActionButton('block', `Block ${friend.username}`, () => blockUser(friend.id, friend.username), 'destructive');
        actionsDiv.appendChild(blockBtn);

        friendDiv.appendChild(friendInfo);
        friendDiv.appendChild(actionsDiv);
        friendsListContainerFM.appendChild(friendDiv);
    });
    updateUIText(); // Translate any new elements
}

// Modify createActionButton to include more icons if needed
// e.g., 'chat_bubble', 'person_remove', 'block'

async function loadPendingFriendRequests() {
    if (!pendingRequestsContainer || !friendRequestsBadge) return;
    pendingRequestsContainer.innerHTML = `<p class="italic text-sm text-gray-400" data-translate-key="loading_pending_requests">Loading requests...</p>`;
    try {
        const response = await apiRequest('/api/friends/requests/pending');
        const requests = await response.json(); // Expects List[FriendshipRequestPublic]
        
        if (requests.length > 0) {
            friendRequestsBadge.textContent = requests.length > 9 ? '9+' : requests.length.toString();
            friendRequestsBadge.classList.remove('hidden');
        } else {
            friendRequestsBadge.classList.add('hidden');
        }
        renderPendingRequests(requests);
    } catch (error) {
        pendingRequestsContainer.innerHTML = `<p class="italic text-sm text-red-400">${translate('error_loading_pending_requests', 'Failed to load friend requests.')}</p>`;
        friendRequestsBadge.classList.add('hidden');
    }
}

function renderPendingRequests(requests) {
    pendingRequestsContainer.innerHTML = '';
    if (requests.length === 0) {
        pendingRequestsContainer.innerHTML = `<p class="italic text-sm text-gray-400" data-translate-key="no_pending_friend_requests">No pending friend requests.</p>`;
        return;
    }
    requests.forEach(req => {
        const reqDiv = document.createElement('div');
        reqDiv.className = 'flex items-center justify-between p-2 bg-gray-750 rounded-md';
        
        const reqInfo = document.createElement('span');
        reqInfo.innerHTML = translate('friend_request_from_user', `Request from <strong class="font-semibold">${req.requesting_username}</strong>`, {username: req.requesting_username});
        
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'space-x-2';
        
        const acceptBtn = document.createElement('button');
        acceptBtn.className = 'btn btn-xs btn-success'; // Define btn-xs, btn-success
        acceptBtn.textContent = translate('accept_btn', 'Accept');
        acceptBtn.onclick = () => respondToFriendRequest(req.friendship_id, 'accept');
        
        const rejectBtn = document.createElement('button');
        rejectBtn.className = 'btn btn-xs btn-danger'; // Define btn-xs, btn-danger
        rejectBtn.textContent = translate('reject_btn', 'Reject');
        rejectBtn.onclick = () => respondToFriendRequest(req.friendship_id, 'reject');
        
        actionsDiv.appendChild(acceptBtn);
        actionsDiv.appendChild(rejectBtn);
        
        reqDiv.appendChild(reqInfo);
        reqDiv.appendChild(actionsDiv);
        pendingRequestsContainer.appendChild(reqDiv);
    });
    updateUIText(); // Translate any new elements
}

async function respondToFriendRequest(friendshipId, action) {
    showStatus(translate(`status_responding_to_request_${action}`, `Responding to request (${action})...`), 'info', addFriendStatus); // Use a relevant status element
    try {
        await apiRequest(`/api/friends/requests/${friendshipId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: action })
        });
        showStatus(translate(`status_friend_request_${action}_success`, `Friend request ${action}ed.`), 'success', addFriendStatus);
        loadPendingFriendRequests(); // Refresh pending list
        if (action === 'accept') {
            loadFriendsList(); // Refresh friends list if accepted
        }
    } catch (error) {
        // apiRequest shows error
    }
}

async function unfriendUser(friendUserId, friendUsername) {
    if (!confirm(translate('confirm_unfriend_user', `Are you sure you want to unfriend ${friendUsername}?`, {username: friendUsername}))) return;
    showStatus(translate('status_unfriending_user', `Unfriending ${friendUsername}...`, {username: friendUsername}), 'info', addFriendStatus); // Or a status within friends list
    try {
        await apiRequest(`/api/friends/${friendUserId}`, { method: 'DELETE' }); // Use friendUserId
        showStatus(translate('status_user_unfriended_success', `${friendUsername} has been unfriended.`, {username: friendUsername}), 'success', addFriendStatus);
        loadFriendsList();
    } catch (error) {
        // apiRequest shows error
    }
}

function openDirectMessage(friendUserId, friendUsername) {
    // This is a placeholder for opening a DM chat interface
    // For now, just switch to the messages tab and log
    handleFriendsMessagesTabSwitch('directMessagesTab');
    const dmContent = document.getElementById('directMessagesTab');
    if (dmContent) {
        dmContent.innerHTML = `
            <h4 class="text-md font-semibold mb-2">${translate('chatting_with_user_header', `Chat with ${friendUsername}`, {username: friendUsername})}</h4>
            <div class="border border-gray-700 rounded-md p-4 h-64 overflow-y-auto mb-2 bg-gray-850">
                <!-- Messages will go here -->
                <p class="italic text-sm text-gray-500">${translate('dm_loading_messages_placeholder', 'Loading messages...')}</p>
            </div>
            <div class="flex space-x-2">
                <input type="text" id="directMessageInput" class="input-field flex-grow" placeholder="${translate('dm_type_message_placeholder', 'Type a message...')}" />
                <button id="sendDirectMessageBtn" class="btn btn-primary">${translate('send_btn', 'Send')}</button>
            </div>
        `;
        // Add event listener for sendDirectMessageBtn here
        const sendDmBtn = document.getElementById('sendDirectMessageBtn');
        if (sendDmBtn) {
            sendDmBtn.onclick = () => {
                const dmInput = document.getElementById('directMessageInput');
                if (dmInput && dmInput.value.trim()) {
                    sendDirectMessageToServer(friendUserId, dmInput.value.trim()); // Implement this
                    dmInput.value = '';
                }
            };
        }
        // TODO: Implement 
        loadDirectMessagesForUser(friendUserId);
    }
    console.log(`Open DM with user ID: ${friendUserId}, Username: ${friendUsername}`);
    openDmChatWithUser(friendUserId, friendUsername)
}
async function loadDirectMessagesForUser(friendUserId) {
    if (!friendUserId || !currentUser.id) return; // Check for valid user ID

    try {
        const response = await apiRequest(`/api/dm/conversations/${friendUserId}`);
        const data = await response.json();
        // Check for pagination links (if present)
        if (data.links) {
            // Handle pagination links (e.g., load more messages)
            // ...
        }

        renderDirectMessages(data.messages);
    } catch (error) {
        console.error("Error loading direct messages:", error);
        showStatus(translate('dm_error_loading_messages', 'Failed to load messages.'), 'error');
    } finally {
        if (loadingIndicator) {
            loadingIndicator.style.display = 'none';
        }
    }
}

// Helper function to render direct messages
function renderDirectMessages(messages) {
    const dmChatMessages = document.getElementById('directMessageChatArea');

    // Clear any existing messages
    dmChatMessages.innerHTML = '';

    // Render each message
    messages.forEach((message, index) => {
        const msgDiv = createMessageDiv(message);
        dmChatMessages.appendChild(msgDiv);

        // Scroll to the last message if necessary
        if (index === 0) {
            dmChatMessages.scrollTop = dmChatMessages.scrollHeight;
        }
    });
}

// Helper function to create a single message div
function createMessageDiv(message) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'dm-message-bubble';

    // Create content and timestamp elements
    const contentP = document.createElement('p');
    const timeSpan = document.createElement('span');

    // Set content and timestamp values
    contentP.textContent = message.content;
    timeSpan.textContent = formatTimestamp(new Date(message.sent_at));

    // Append to the message div
    msgDiv.appendChild(contentP);
    msgDiv.appendChild(timeSpan);

    return msgDiv;
}

async function sendDirectMessageToServer(receiverUserId, content) {
    if (!currentDmPartner || currentDmPartner.userId !== receiverUserId || !content.trim()) {
        console.error("DM send conditions not met:", currentDmPartner, receiverUserId, content);
        return;
    }

    // Disable input while sending
    if(directMessageInput) directMessageInput.disabled = true;
    if(sendDirectMessageBtn) sendDirectMessageBtn.disabled = true;
    showStatus(translate('dm_sending_message_status', 'Sending...'), 'info', dmSendStatus);

    try {
        const payload = {
            receiver_user_id: receiverUserId,
            content: content.trim()
            // Add image_references_json here if you implement image DMs
        };

        const response = await apiRequest('/api/dm/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            statusElement: dmSendStatus // Show status in the DM input area
        });
        const newSentDm = await response.json(); // Expects DirectMessagePublic

        // 1. Add the new message to the currently displayed chat
        if (dmChatMessages && currentDmPartner && currentDmPartner.userId === newSentDm.receiver_id || currentDmPartner.userId === newSentDm.sender_id) {
            // Construct a message object similar to what renderDirectMessages expects
            // Note: newSentDm already has sender_username and receiver_username from the backend
            appendSingleDirectMessage(newSentDm); // New helper function
        }

        // 2. Clear the input field
        if(directMessageInput) directMessageInput.value = '';

        // 3. Clear sending status
        showStatus('', 'info', dmSendStatus);

        // 4. Refresh the main conversations list to update previews
        //    and potentially move this conversation to the top.
        await loadDmConversations();

    } catch (error) {
        // apiRequest should have already shown an error in dmSendStatus
        console.error("Failed to send DM:", error);
        // Optionally, provide a more specific error message here if needed
        showStatus(translate('dm_send_failed_error', 'Failed to send message. Please try again.'), 'error', dmSendStatus);
    } finally {
        // Re-enable input
        if(directMessageInput) directMessageInput.disabled = false;
        if(sendDirectMessageBtn) sendDirectMessageBtn.disabled = false;
        if(directMessageInput) directMessageInput.focus(); // Focus back on input
    }
}

// New helper function to append a single DM to the chat area
function appendSingleDirectMessage(msg) {
    if (!dmChatMessages || !currentUser) return;

    // If it's the first message in an empty chat, clear the placeholder
    const placeholder = dmChatMessages.querySelector('p.italic');
    if (placeholder) {
        placeholder.remove();
    }

    const msgDiv = document.createElement('div');
    const isSender = msg.sender_id === currentUser.id; // currentUser.id should be the user's integer ID
    msgDiv.className = `dm-message-bubble ${isSender ? 'sent' : 'received'}`;
    
    const contentP = document.createElement('p');
    // For DMs, let's assume plain text for now. If you want Markdown:
    // contentP.innerHTML = marked.parse(msg.content);
    contentP.textContent = msg.content; 
    
    const timeSpan = document.createElement('span');
    timeSpan.className = 'dm-message-timestamp';
    timeSpan.textContent = formatTimestamp(new Date(msg.sent_at));
    
    msgDiv.appendChild(contentP);
    msgDiv.appendChild(timeSpan);
    dmChatMessages.appendChild(msgDiv);

    // Scroll to the new message
    dmChatMessages.scrollTop = dmChatMessages.scrollHeight;
}


function openSendPersonalityModal(personalityId, personalityName) {
    if (!personalityId || !personalityName) return;
    sendPersonalityIdInput.value = personalityId;
    sendPersonalityModalTitle.textContent = translate('send_personality_modal_title_prefix', `Send Personality: "${personalityName}"`, {name: personalityName});
    sendPersonalityTargetUsername.value = '';
    showStatus('', 'info', sendPersonalityStatus);
    openModal('sendPersonalityModal');
}

async function handleConfirmSendPersonality() {
    const personalityId = sendPersonalityIdInput.value;
    const targetUsername = sendPersonalityTargetUsername.value.trim();
    if (!personalityId || !targetUsername) {
        showStatus(translate('error_target_username_required', 'Target username is required.'), 'error', sendPersonalityStatus);
        return;
    }
    showStatus(translate('status_sending_personality_to_user', `Sending personality to ${targetUsername}...`, {username: targetUsername}), 'info', sendPersonalityStatus);
    confirmSendPersonalityBtn.disabled = true;
    try {
        await apiRequest(`/api/personalities/${personalityId}/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_username: targetUsername }),
            statusElement: sendPersonalityStatus
        });
        showStatus(translate('status_personality_sent_success', 'Personality sent successfully!'), 'success', sendPersonalityStatus);
        setTimeout(() => closeModal('sendPersonalityModal'), 1500);
    } catch (error) {
        // API request shows error
    } finally {
        confirmSendPersonalityBtn.disabled = false;
    }
}



async function loadDmConversations() {
    if (!dmConversationsList) {
        console.error("DM Conversations List element not found.");
        return;
    }
    dmConversationsList.innerHTML = `<p class="italic text-sm text-gray-400" data-translate-key="dm_loading_conversations">${translate('dm_loading_conversations', 'Loading conversations...')}</p>`;
    updateUIText(); // Translate the loading message

    try {
        const response = await apiRequest('/api/dm/conversations');
        if (!response.ok) { // apiRequest should throw, but as a safeguard
            throw new Error(`Failed to fetch conversations: ${response.status}`);
        }
        dmConversationsCache = await response.json(); // Expects List of conversation summaries
        renderDmConversationsList();
    } catch (error) {
        console.error("Error loading DM conversations:", error);
        dmConversationsList.innerHTML = `<p class="italic text-sm text-red-400">${translate('dm_error_loading_conversations', 'Failed to load conversations.')}</p>`;
        updateUIText(); // Translate the error message
    }
}

function renderDmConversationsList() {
    if (!dmConversationsList) return;
    dmConversationsList.innerHTML = '';

    if (dmConversationsCache.length === 0) {
        dmConversationsList.innerHTML = `<p class="italic text-sm text-gray-400" data-translate-key="dm_no_conversations_placeholder">${translate('dm_no_conversations_placeholder', 'No active conversations. Search for a user to start one.')}</p>`;
        updateUIText();
        return;
    }

    // Sort conversations by last message time, most recent first
    dmConversationsCache.sort((a, b) => {
        const dateA = a.last_message_sent_at ? new Date(a.last_message_sent_at) : new Date(0);
        const dateB = b.last_message_sent_at ? new Date(b.last_message_sent_at) : new Date(0);
        return dateB - dateA;
    });

    dmConversationsCache.forEach(convo => {
        const convoDiv = document.createElement('div');
        // Highlight if this conversation is currently active in the chat view
        const isActiveConvo = currentDmPartner && currentDmPartner.userId === convo.partner_user_id;
        convoDiv.className = `p-2.5 rounded-lg cursor-pointer hover:bg-gray-700 transition-colors duration-150 flex items-center space-x-3 ${isActiveConvo ? 'bg-gray-700 shadow-md' : 'bg-gray-750'}`;
        convoDiv.onclick = () => openDmChatWithUser(convo.partner_user_id, convo.partner_username);

        // Simple Avatar Placeholder
        const avatarPlaceholder = document.createElement('div');
        avatarPlaceholder.className = 'w-10 h-10 bg-gray-600 rounded-full flex items-center justify-center text-sm font-semibold flex-shrink-0';
        avatarPlaceholder.textContent = convo.partner_username.charAt(0).toUpperCase();
        
        const textContentDiv = document.createElement('div');
        textContentDiv.className = 'flex-grow min-w-0'; // For truncation

        const header = document.createElement('div');
        header.className = 'flex justify-between items-baseline mb-0.5';
        
        const partnerName = document.createElement('span');
        partnerName.className = 'font-semibold text-sm text-gray-100 truncate';
        partnerName.textContent = convo.partner_username;
        partnerName.title = convo.partner_username;

        if (convo.unread_count > 0) {
            const unreadBadge = document.createElement('span');
            unreadBadge.className = 'ml-1.5 bg-red-500 text-white text-xs font-bold rounded-full px-1.5 py-0.5 leading-none';
            unreadBadge.textContent = convo.unread_count > 9 ? '9+' : convo.unread_count;
            partnerName.appendChild(unreadBadge);
        }
        
        const lastMsgTime = document.createElement('span');
        lastMsgTime.className = 'text-xs text-gray-400 flex-shrink-0';
        lastMsgTime.textContent = convo.last_message_sent_at ? formatTimestamp(new Date(convo.last_message_sent_at)) : '';
        
        header.appendChild(partnerName);
        header.appendChild(lastMsgTime);

        const preview = document.createElement('p');
        preview.className = 'text-xs text-gray-300 truncate';
        let previewText = convo.last_message_content || translate('dm_no_messages_yet_preview', 'No messages yet.');
        if (convo.last_message_sender_id === currentUser.id && previewText !== translate('dm_no_messages_yet_preview', 'No messages yet.')) {
            previewText = `${translate('dm_you_prefix', 'You:')} ${previewText}`;
        }
        preview.textContent = previewText;
        preview.title = previewText;
        
        textContentDiv.appendChild(header);
        textContentDiv.appendChild(preview);

        convoDiv.appendChild(avatarPlaceholder);
        convoDiv.appendChild(textContentDiv);
        dmConversationsList.appendChild(convoDiv);
    });
    updateUIText(); // Translate any new elements if they use data-translate-key
}
async function handleDmUserSearch() {
    const query = dmSearchUsersInput.value.trim().toLowerCase();
    if (query.length < 2) { // Minimum characters to search
        dmSearchResults.innerHTML = '';
        dmSearchResults.classList.add('hidden');
        return;
    }

    // For now, search within existing friends list.
    // A proper backend search endpoint /api/users/search?q=... would be better.
    const matchingFriends = availableDataStoresForRag // Re-using this for now, should be actual friends list
        .filter(user => user.username.toLowerCase().includes(query) && user.username !== currentUser.username)
        .slice(0, 5); // Limit results

    dmSearchResults.innerHTML = '';
    if (matchingFriends.length > 0) {
        matchingFriends.forEach(user => {
            const item = document.createElement('div');
            item.className = 'p-2 hover:bg-gray-600 cursor-pointer text-sm';
            item.textContent = user.username;
            item.onclick = () => {
                openDmChatWithUser(user.id, user.username); // Pass ID and username
                dmSearchUsersInput.value = '';
                dmSearchResults.classList.add('hidden');
            };
            dmSearchResults.appendChild(item);
        });
        dmSearchResults.classList.remove('hidden');
    } else {
        dmSearchResults.innerHTML = `<div class="p-2 text-xs text-gray-400">${translate('dm_no_users_found_search', 'No users found.')}</div>`;
        dmSearchResults.classList.remove('hidden'); // Show "no users found"
    }
}


async function loadDmConversations() {
    if (!dmConversationsList) return;
    dmConversationsList.innerHTML = `<p class="italic text-sm text-gray-400" data-translate-key="dm_loading_conversations">Loading conversations...</p>`;
    try {
        const response = await apiRequest('/api/dm/conversations');
        dmConversationsCache = await response.json(); // Expects List of conversation summaries
        renderDmConversationsList();
    } catch (error) {
        dmConversationsList.innerHTML = `<p class="italic text-sm text-red-400">${translate('dm_error_loading_conversations', 'Failed to load conversations.')}</p>`;
    }
}

function renderDmConversationsList() {
    dmConversationsList.innerHTML = '';
    if (dmConversationsCache.length === 0) {
        dmConversationsList.innerHTML = `<p class="italic text-sm text-gray-400" data-translate-key="dm_no_conversations_placeholder">No active conversations. Search for a user to start one.</p>`;
        return;
    }
    dmConversationsCache.forEach(convo => {
        const convoDiv = document.createElement('div');
        convoDiv.className = `p-2 rounded-md cursor-pointer hover:bg-gray-700 transition-colors ${currentDmPartner && currentDmPartner.userId === convo.partner_user_id ? 'bg-gray-700' : 'bg-gray-750'}`;
        convoDiv.onclick = () => openDmChatWithUser(convo.partner_user_id, convo.partner_username);

        const header = document.createElement('div');
        header.className = 'flex justify-between items-center mb-1';
        const partnerName = document.createElement('span');
        partnerName.className = 'font-semibold text-sm';
        partnerName.textContent = convo.partner_username;
        const lastMsgTime = document.createElement('span');
        lastMsgTime.className = 'text-xs text-gray-400';
        lastMsgTime.textContent = convo.last_message_sent_at ? formatTimestamp(new Date(convo.last_message_sent_at)) : '';
        header.appendChild(partnerName);
        header.appendChild(lastMsgTime);

        const preview = document.createElement('p');
        preview.className = 'text-xs text-gray-300 truncate';
        preview.textContent = convo.last_message_content || translate('dm_no_messages_yet_preview', 'No messages yet.');
        
        if (convo.unread_count > 0) {
            const unreadBadge = document.createElement('span');
            unreadBadge.className = 'ml-2 bg-red-500 text-white text-xs font-bold rounded-full px-1.5 py-0.5';
            unreadBadge.textContent = convo.unread_count > 9 ? '9+' : convo.unread_count;
            partnerName.appendChild(unreadBadge); // Append to name for visibility
        }

        convoDiv.appendChild(header);
        convoDiv.appendChild(preview);
        dmConversationsList.appendChild(convoDiv);
    });
    updateUIText();
}

async function openDmChatWithUser(partnerUserId, partnerUsername) {
    console.log("Opening dm chat")
    currentDmPartner = { userId: partnerUserId, username: partnerUsername };
    
    dmChatArea.classList.remove('hidden');
    dmNoConversationSelected.classList.add('hidden');
    dmNoConversationSelected.style.display = 'none';


    if(dmChatHeader) dmChatHeader.textContent = translate('dm_chatting_with_header', `Chat with ${partnerUsername}`, {username: partnerUsername});
    if(dmChatMessages) dmChatMessages.innerHTML = `<p class="italic text-sm text-gray-500 text-center py-10" data-translate-key="dm_loading_messages_placeholder">Loading messages...</p>`;
    if(directMessageInput) directMessageInput.value = '';
    showStatus('', 'info', dmSendStatus);

    // Highlight selected conversation in the list
    renderDmConversationsList(); // Re-render to highlight

    try {
        // Mark conversation as read on the backend when opening
        await apiRequest(`/api/dm/conversation/${partnerUserId}/mark_read`, { method: 'POST' });
        // Update unread count in cache and re-render list
        const convoInCache = dmConversationsCache.find(c => c.partner_user_id === partnerUserId);
        if (convoInCache) {
            convoInCache.unread_count = 0;
            renderDmConversationsList(); // Re-render to remove badge
        }


        const response = await apiRequest(`/api/dm/conversation/${partnerUserId}`);
        const messages = await response.json(); // Expects List[DirectMessagePublic]
        renderDirectMessages(messages);
    } catch (error) {
        if(dmChatMessages) dmChatMessages.innerHTML = `<p class="italic text-sm text-red-400 text-center py-10">${translate('dm_error_loading_messages', 'Failed to load messages.')}</p>`;
    }
}

function renderDirectMessages(messages) {
    dmChatMessages.innerHTML = '';
    if (messages.length === 0) {
        dmChatMessages.innerHTML = `<p class="italic text-sm text-gray-400 text-center py-10" data-translate-key="dm_no_messages_in_conversation">No messages in this conversation yet. Say hello!</p>`;
        updateUIText();
        return;
    }
    messages.forEach(msg => {
        const msgDiv = document.createElement('div');
        const isSender = msg.sender_id === currentUser.id;
        msgDiv.className = `dm-message-bubble ${isSender ? 'sent' : 'received'}`;
        
        const contentP = document.createElement('p');
        contentP.textContent = msg.content; // Add Markdown parsing later if needed
        
        const timeSpan = document.createElement('span');
        timeSpan.className = 'dm-message-timestamp';
        timeSpan.textContent = formatTimestamp(new Date(msg.sent_at));
        
        msgDiv.appendChild(contentP);
        msgDiv.appendChild(timeSpan);
        dmChatMessages.appendChild(msgDiv);
    });
    dmChatMessages.scrollTop = dmChatMessages.scrollHeight; // Scroll to bottom
}

async function handleSendDirectMessage() {
    if (!currentDmPartner || !directMessageInput || !sendDirectMessageBtn) return;
    const content = directMessageInput.value.trim();
    if (!content) return;

    sendDirectMessageBtn.disabled = true;
    directMessageInput.disabled = true;
    showStatus(translate('dm_sending_message_status', 'Sending...'), 'info', dmSendStatus);

    try {
        const payload = {
            receiver_user_id: currentDmPartner.userId,
            content: content
        };
        const response = await apiRequest('/api/dm/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            statusElement: dmSendStatus
        });
        const newDm = await response.json(); // DirectMessagePublic

        // Add to local messages and re-render
        const currentChatMessages = Array.from(dmChatMessages.querySelectorAll('.dm-message-bubble')).map(el => ({
            // This is a simplification; ideally, you'd have a proper local cache of DMs
            // For now, just append and re-render this message
        }));
         // A bit hacky, ideally fetch full conversation or have a proper local store
        const tempMessagesForRender = [];
        dmChatMessages.querySelectorAll('.dm-message-bubble').forEach(bubble => {
            // This is not ideal, we don't have the full message objects here.
            // For a quick append, we'll just add the new one.
            // A robust solution would fetch the conversation again or manage a local array.
        });
        renderDirectMessages([...tempMessagesForRender, newDm]); // This will clear and re-render, not ideal for just one new message
        
        // Better: Append directly
        // const msgForRender = { // Construct object similar to what renderDirectMessages expects
        //    id: newDm.id, sender_id: newDm.sender_id, content: newDm.content, sent_at: newDm.sent_at
        // };
        // appendSingleDirectMessage(msgForRender); // You'd need this helper

        directMessageInput.value = '';
        showStatus('', 'info', dmSendStatus);

        // Refresh conversation list to update last message preview
        await loadDmConversations();

    } catch (error) {
        // apiRequest shows error in dmSendStatus
    } finally {
        sendDirectMessageBtn.disabled = false;
        directMessageInput.disabled = false;
    }
}

adminLink.addEventListener('click', async function(event) {
    event.preventDefault(); // Prevent the default GET behavior
    const response = await apiRequest("/admin")
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }

    const html = await response.text();

    // Replace the whole page
    document.open();
    document.write(html);
    document.close();    
});


document.addEventListener('DOMContentLoaded', () => {

    const sortMenuBtn = document.getElementById('sortMenuBtn');
    const sortMenuDropdown = document.getElementById('sortMenuDropdown');
    const discussionSearchInput = document.getElementById('discussionSearchInput'); // Ensure this is defined here or globally

    // Add event listener for discussion search input
    if(discussionSearchInput) {
        discussionSearchInput.addEventListener('input', () => renderDiscussionList());
    }

    if (sortMenuBtn && sortMenuDropdown) {
        // Toggle the dropdown visibility
        sortMenuBtn.addEventListener('click', (event) => {
            event.stopPropagation(); // Prevents the window click listener from closing it immediately
            sortMenuDropdown.classList.toggle('hidden');
        });

        // Handle selection of a sort option
        sortMenuDropdown.addEventListener('click', (event) => {
            const target = event.target.closest('.sort-option');
            if (target) {
                event.preventDefault();
                const newSortMethod = target.dataset.sort;
                if (newSortMethod) {
                    currentSortMethod = newSortMethod;
                    renderDiscussionList(); // Re-render the list with the new sort order
                    sortMenuDropdown.classList.add('hidden'); // Hide the menu after selection
                }
            }
        });

        // Hide the dropdown if clicking anywhere else on the page
        window.addEventListener('click', (event) => {
            if (!sortMenuDropdown.classList.contains('hidden') && !sortMenuBtn.contains(event.target)) {
                sortMenuDropdown.classList.add('hidden');
            }
        });
    }

});
