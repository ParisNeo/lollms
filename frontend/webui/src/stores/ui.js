import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useUiStore = defineStore('ui', () => {
    const mainView = ref('feed'); 
    const activeModal = ref(null);
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
    // State to hold available languages fetched from the backend
    const availableLanguages = ref({});


    function setMainView(viewName) {
        if (['feed', 'chat'].includes(viewName)) {
            mainView.value = viewName;
        }
    }

    function openModal(name, props = {}) {
        activeModal.value = name;
        modalProps.value = props;
    }

    function closeModal(name) {
        if (activeModal.value === name) {
            activeModal.value = null;
            modalProps.value = {};
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
        // Here you would typically also load the language file with a library like i18n
        // For this simplified example, we'll just store the code.
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

    // --- NEW: Action to fetch languages ---
    async function fetchLanguages() {
        try {
            // Lazy import to prevent circular dependencies if needed
            const apiClient = (await import('../services/api')).default;
            const response = await apiClient.get('/api/languages/');
            availableLanguages.value = response.data;
        } catch (error) {
            console.error("Failed to fetch available languages:", error);
            // Fallback to a default set
            availableLanguages.value = { en: 'English' };
        }
    }
    
    function modalData(name) {
        return activeModal.value === name ? modalProps.value : null;
    }

    function isModalOpen(name) {
        return activeModal.value === name;
    }

    return {
        mainView, activeModal, modalProps, notifications, currentTheme,
        currentLanguage, availableLanguages,
        isImageViewerOpen, imageViewerSrc, confirmationOptions,
        setMainView, openModal, closeModal, addNotification, removeNotification,
        setTheme, toggleTheme, initializeTheme, setLanguage, fetchLanguages,
        openImageViewer, closeImageViewer, showConfirmation, confirmAction, cancelAction,
        isModalOpen, modalData
    };
});