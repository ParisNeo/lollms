// frontend/webui/src/stores/ui.js
import { ref, computed } from 'vue';
import { defineStore } from 'pinia';

export const useUiStore = defineStore('ui', () => {
    const mainView = ref('feed');
    const modalStack = ref([]);
    const modalProps = ref({});
    const notifications = ref([]);
    const currentTheme = ref(localStorage.getItem('lollms-theme') || 'light');
    const currentLanguage = ref(localStorage.getItem('lollms-language') || 'en');
    const isImageViewerOpen = ref(false);
    const imageViewerSrc = ref('');
    const confirmationOptions = ref({
        title: 'Are you sure?',
        message: 'This action cannot be undone.',
        confirmText: 'Confirm',
        onConfirm: () => {},
    });
    const availableLanguages = ref({});
    const emailModalSubject = ref('');
    const emailModalBody = ref('');
    const emailModalBackgroundColor = ref('#f4f4f8');
    const emailModalSendAsText = ref(false);
    const isSidebarOpen = ref(true);
    const keywords = ref([]);
    const isDataZoneVisible = ref(false);
    const isDataZoneExpanded = ref(false);
    const generatePersonalityModalProps = ref({
        prompt: '',
        customEnhancePrompt: ''
    });
    const activeModal = computed(() => modalStack.value.length > 0 ? modalStack.value[modalStack.value.length - 1] : null);

    async function copyToClipboard(textToCopy, successMessage = 'Copied to clipboard!') {
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(textToCopy);
            } else {
                const textArea = document.createElement("textarea");
                textArea.value = textToCopy;
                textArea.style.position = "fixed";
                textArea.style.left = "-9999px";
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                try {
                    document.execCommand('copy');
                } catch (err) {
                    throw new Error('Fallback copy command failed.');
                }
                document.body.removeChild(textArea);
            }
            if (successMessage) {
                addNotification(successMessage, 'success');
            }
            return true;
        } catch (error) {
            console.error('Copy to clipboard failed:', error);
            addNotification('Could not copy text.', 'error');
            return false;
        }
    }

    function initEmailModalState() {
        emailModalSubject.value = '';
        emailModalBody.value = '';
        emailModalBackgroundColor.value = '#f4f4f8';
        emailModalSendAsText.value = false;
    }

    function setMainView(viewName) {
        if (['feed', 'chat'].includes(viewName)) {
            mainView.value = viewName;
        }
    }

    function openModal(name, props = {}) {
        modalStack.value.push(name);
        modalProps.value[name] = props;
    }

    function closeModal(name = null) {
        if (name === null) {
            modalStack.value = [];
            modalProps.value = {};
            return;
        }

        if (name && activeModal.value !== name) {
            return;
        }
        if (modalStack.value.length > 0) {
            const closedModalName = modalStack.value.pop();
            delete modalProps.value[closedModalName];
        }
    }

    function addNotification(message, type = 'info', duration = 3000) {
        const id = Date.now() + Math.random();
        notifications.value.push({ id, message, type, duration });
    }

    function removeNotification(id) {
        notifications.value = notifications.value.filter(n => n.id !== id);
    }
    
    function setTheme(theme) {
        currentTheme.value = theme;
        localStorage.setItem('lollms-theme', theme);
        if (theme === 'dark') {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
    }

    function toggleTheme() {
        const newTheme = currentTheme.value === 'light' ? 'dark' : 'light';
        setTheme(newTheme);
    }
    
    function initializeTheme() {
        setTheme(currentTheme.value);
    }

    function setLanguage(langCode) {
        currentLanguage.value = langCode;
        localStorage.setItem('lollms-language', langCode);
    }

    function openImageViewer(src) {
        imageViewerSrc.value = src;
        isImageViewerOpen.value = true;
    }

    function closeImageViewer() {
        isImageViewerOpen.value = false;
        imageViewerSrc.value = '';
    }

    function showConfirmation(options) {
        return new Promise((resolve) => {
            confirmationOptions.value = {
                title: options.title || 'Are you sure?',
                message: options.message || 'This action cannot be undone.',
                confirmText: options.confirmText || 'Confirm',
                onConfirm: () => {
                    resolve(true);
                    closeModal("confirmation")
                },
                onCancel: () => {
                    resolve(false);
                    closeModal("confirmation")
                }
            };
            openModal("confirmation")
        });
    }

    function confirmAction() {
        if (confirmationOptions.value.onConfirm) {
            confirmationOptions.value.onConfirm();
        }
    }

    function cancelAction() {
        if (confirmationOptions.value.onCancel) {
            confirmationOptions.value.onCancel();
        }
    }

    async function fetchLanguages() {
        try {
            const apiClient = (await import('../services/api')).default;
            const response = await apiClient.get('/api/languages/');
            availableLanguages.value = response.data;
        } catch (error) {
            availableLanguages.value = { en: 'English' };
        }
    }
    
    async function fetchKeywords() {
        if (keywords.value.length > 0) return;
        try {
            const apiClient = (await import('../services/api')).default;
            const response = await apiClient.get('/api/help/keywords');
            keywords.value = response.data;
        } catch (error) {
            console.error("Failed to fetch keywords:", error);
        }
    }

    function modalData(name) {
        return modalProps.value[name] || null;
    }

    function isModalOpen(name) {
        return activeModal.value === name;
    }
    function openGeneratePersonalityModal() {
        openModal('generatePersonality');
    }
    function setEmailModalState(subject, body, backgroundColor='#f4f4f8', sendAsText=false) {
        emailModalSubject.value = subject;
        emailModalBody.value = body;
        emailModalBackgroundColor.value = backgroundColor;
        emailModalSendAsText.value = sendAsText;
    }

    function toggleSidebar() {
        isSidebarOpen.value = !isSidebarOpen.value;
        localStorage.setItem('lollms-sidebar-open', isSidebarOpen.value);
    }

    function initializeSidebarState() {
        const storedState = localStorage.getItem('lollms-sidebar-open');
        if (storedState !== null) {
            isSidebarOpen.value = JSON.parse(storedState);
        }
    }
    
    function toggleDataZone() {
        isDataZoneVisible.value = !isDataZoneVisible.value;
        if (!isDataZoneVisible.value) {
            isDataZoneExpanded.value = false; // Also shrink if hiding
        }
    }

    function toggleDataZoneExpansion() {
        isDataZoneExpanded.value = !isDataZoneExpanded.value;
    }

    return {
        mainView, activeModal, modalProps, notifications, currentTheme,
        currentLanguage, availableLanguages,
        isImageViewerOpen, imageViewerSrc, confirmationOptions,
        emailModalSubject, emailModalBody, emailModalBackgroundColor, emailModalSendAsText,
        isSidebarOpen, keywords, generatePersonalityModalProps,
        isDataZoneVisible, isDataZoneExpanded,
        initEmailModalState,
        setMainView, openModal, closeModal, addNotification, removeNotification,
        setTheme, toggleTheme, initializeTheme, setLanguage, fetchLanguages, fetchKeywords,
        openImageViewer, closeImageViewer, showConfirmation, confirmAction, cancelAction,
        isModalOpen, modalData,
        copyToClipboard,
        toggleSidebar, initializeSidebarState,
        toggleDataZone, toggleDataZoneExpansion,
        openGeneratePersonalityModal
    };
});