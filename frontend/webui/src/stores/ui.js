import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';

export const useUiStore = defineStore('ui', () => {
    // State
    const currentTheme = ref('dark');
    const openModals = ref([]);
    const modalDataStore = ref({});
    const notifications = ref([]);
    let nextNotificationId = 0;

    const isConfirmationVisible = ref(false);
    const confirmationOptions = ref({});
    let confirmationPromise = null;

    const imageViewerSrc = ref(null);

    // --- NEW: Localization State ---
    const availableLanguages = ref({});
    const currentLanguage = ref(localStorage.getItem('lollms_language') || 'en');
    const translations = ref({});

    // Getters
    const isModalOpen = computed(() => (modalName) => openModals.value.includes(modalName));
    const modalData = computed(() => (modalName) => modalDataStore.value[modalName]);
    const isImageViewerOpen = computed(() => !!imageViewerSrc.value);

    // --- NEW: Translate Getter ---
    const translate = computed(() => (key, fallback = null, vars = {}) => {
        let translation = translations.value[key] || fallback || key;
        for (const varKey in vars) {
            translation = translation.replace(new RegExp(`{{${varKey}}}`, 'g'), vars[varKey]);
        }
        return translation;
    });

    // Actions
    function initializeTheme() {
        const savedTheme = localStorage.getItem('theme') || 'dark';
        setTheme(savedTheme);
    }

    function setTheme(theme) {
        currentTheme.value = theme;
        if (theme === 'dark') {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
        localStorage.setItem('theme', theme);
    }

    function toggleTheme() {
        setTheme(currentTheme.value === 'dark' ? 'light' : 'dark');
    }

    function openModal(modalName, data = null) {
        if (!openModals.value.includes(modalName)) {
            openModals.value.push(modalName);
        }
        if (data) {
            modalDataStore.value[modalName] = data;
        }
    }

    function closeModal(modalName) {
        openModals.value = openModals.value.filter(m => m !== modalName);
        delete modalDataStore.value[modalName];
    }

    function addNotification(message, type = 'info', duration = 5000) {
        const id = nextNotificationId++;
        notifications.value.push({ id, message, type });

        setTimeout(() => {
            removeNotification(id);
        }, duration);
    }

    function removeNotification(id) {
        notifications.value = notifications.value.filter(n => n.id !== id);
    }

    function showConfirmation(options = { title: 'Are you sure?', message: 'This action cannot be undone.' }) {
        confirmationOptions.value = options;
        isConfirmationVisible.value = true;
        
        return new Promise((resolve, reject) => {
            confirmationPromise = { resolve };
        });
    }

    function confirmAction() {
        if (confirmationPromise) {
            confirmationPromise.resolve(true);
        }
        isConfirmationVisible.value = false;
    }

    function cancelAction() {
        if (confirmationPromise) {
            confirmationPromise.resolve(false);
        }
        isConfirmationVisible.value = false;
    }
    
    function openImageViewer(src) {
        imageViewerSrc.value = src;
    }

    function closeImageViewer() {
        imageViewerSrc.value = null;
    }

    // --- NEW: Localization Actions ---
    async function fetchAvailableLanguages() {
        try {
            const response = await apiClient.get('/api/languages/');
            availableLanguages.value = response.data;
        } catch (error) {
            console.error("Failed to fetch available languages:", error);
            availableLanguages.value = { 'en': 'English' }; // Fallback
        }
    }

    async function loadTranslations(langCode) {
        try {
            const response = await apiClient.get(`/locals/${langCode}.json`);
            translations.value = response.data;
            document.documentElement.lang = langCode.split('-')[0];
        } catch (error) {
            console.error(`Failed to load translations for ${langCode}:`, error);
            if (langCode !== 'en') {
                await loadTranslations('en'); // Fallback to English
            }
        }
    }

    async function setLanguage(langCode) {
        currentLanguage.value = langCode;
        localStorage.setItem('lollms_language', langCode);
        await loadTranslations(langCode);
    }

    async function initializeLocalization() {
        await fetchAvailableLanguages();
        let langToLoad = localStorage.getItem('lollms_language');
        
        if (!langToLoad || !availableLanguages.value[langToLoad]) {
            const browserLang = navigator.language.split('-')[0];
            langToLoad = availableLanguages.value[browserLang] ? browserLang : 'en';
        }
        
        await setLanguage(langToLoad);
    }


    return {
        // State
        currentTheme,
        notifications,
        isModalOpen,
        modalData,
        isConfirmationVisible,
        confirmationOptions,
        imageViewerSrc,
        isImageViewerOpen,
        availableLanguages,
        currentLanguage,
        translations,

        // Getters
        translate,

        // Actions
        initializeTheme,
        toggleTheme,
        openModal,
        closeModal,
        addNotification,
        removeNotification,
        showConfirmation,
        confirmAction,
        cancelAction,
        openImageViewer,
        closeImageViewer,
        initializeLocalization,
        setLanguage
    };
});