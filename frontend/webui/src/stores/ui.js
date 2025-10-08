import { defineStore } from 'pinia';
import { markRaw } from 'vue';

export const useUiStore = defineStore('ui', {
  state: () => ({
    mainView: 'chat',
    modalStack: [],
    modalProps: {},
    notifications: [],
    currentTheme: localStorage.getItem('lollms-theme') || 'light',
    currentLanguage: localStorage.getItem('lollms-language') || 'en',
    message_font_size: 14,
    imageViewer: {
      isOpen: false,
      imageList: [],
      startIndex: 0,
    },
    confirmationOptions: {
        title: 'Are you sure?',
        message: 'This action cannot be undone.',
        confirmText: 'Confirm',
        onConfirm: () => {},
        inputType: null,
        inputOptions: [],
        inputValue: null,
    },
    availableLanguages: {},
    emailModalSubject: '',
    emailModalBody: '',
    emailModalBackgroundColor: '#f4f4f8',
    emailModalSendAsText: false,
    isSidebarOpen: true,
    keywords: [],
    isDataZoneVisible: false,
    isDataZoneExpanded: false,
    generatePersonalityModalProps: {
        prompt: '',
        customEnhancePrompt: ''
    },
    pageTitle: '',
    pageTitleIcon: null,
  }),

  getters: {
    activeModal: (state) => state.modalStack.length > 0 ? state.modalStack[state.modalStack.length - 1] : null,
    modalData: (state) => (name) => state.modalProps[name] || null,
  },

  actions: {
    async copyToClipboard(textToCopy, successMessage = 'Copied to clipboard!') {
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
                this.addNotification(successMessage, 'success');
            }
            return true;
        } catch (error) {
            console.error('Copy to clipboard failed:', error);
            this.addNotification('Could not copy text.', 'error');
            return false;
        }
    },
    initEmailModalState() {
        this.emailModalSubject = '';
        this.emailModalBody = '';
        this.emailModalBackgroundColor = '#f4f4f8';
        this.emailModalSendAsText = false;
    },

    setMainView(viewName) {
        if (['feed', 'chat'].includes(viewName)) {
            this.mainView = viewName;
        }
    },

    openModal(name, props = {}) {
        if (!this.modalStack.includes(name)) {
            this.modalStack.push(name);
        }
        this.modalProps[name] = props;
    },

    closeModal(name = null) {
        if (name === null) {
            this.modalStack = [];
            this.modalProps = {};
            return;
        }
        
        if (name && this.activeModal !== name) {
            return;
        }
        if (this.modalStack.length > 0) {
            const closedModalName = this.modalStack.pop();
            delete this.modalProps[closedModalName];
        }
    },

    addNotification(message, type = 'info', duration = 3000, persistent = false, sender = null) {
        const id = Date.now() + Math.random();
        this.notifications.push({ id, message, type, duration, persistent, sender });
    },

    removeNotification(id) {
        this.notifications = this.notifications.filter(n => n.id !== id);
    },
    
    setTheme(theme) {
        this.currentTheme = theme;
        localStorage.setItem('lollms-theme', theme);
        document.documentElement.classList.toggle('dark', theme === 'dark');
    },

    toggleTheme() {
        this.setTheme(this.currentTheme === 'light' ? 'dark' : 'light');
    },
    
    initializeTheme() {
        this.setTheme(this.currentTheme);
    },

    setLanguage(langCode) {
        this.currentLanguage = langCode;
        localStorage.setItem('lollms-language', langCode);
    },

    openImageViewer({ imageList, startIndex = 0 }) {
        this.imageViewer.imageList = imageList;
        this.imageViewer.startIndex = startIndex;
        this.imageViewer.isOpen = true;
    },

    closeImageViewer() {
        this.imageViewer.isOpen = false;
        setTimeout(() => {
            this.imageViewer.imageList = [];
            this.imageViewer.startIndex = 0;
        }, 300);
    },

    showConfirmation(options) {
        return new Promise((resolve) => {
            this.confirmationOptions = {
                title: options.title || 'Are you sure?',
                message: options.message || 'This action cannot be undone.',
                confirmText: options.confirmText || 'Confirm',
                cancelText: options.cancelText || 'Cancel',
                onConfirm: (value) => {
                    resolve({ confirmed: true, value: value });
                    this.closeModal("confirmation");
                },
                onCancel: () => {
                    resolve({ confirmed: false, value: null });
                    this.closeModal("confirmation");
                },
                inputType: options.inputType || null,
                inputOptions: options.inputOptions || [],
                inputValue: options.inputValue !== undefined ? options.inputValue : null,
            };
            this.openModal("confirmation");
        });
    },

    confirmAction(value) {
        if (this.confirmationOptions.onConfirm) {
            this.confirmationOptions.onConfirm(value);
        }
    },

    cancelAction() {
        if (this.confirmationOptions.onCancel) {
            this.confirmationOptions.onCancel();
        }
    },

    async fetchLanguages() {
        try {
            const apiClient = (await import('../services/api')).default;
            const response = await apiClient.get('/api/languages/');
            this.availableLanguages = response.data;
        } catch (error) {
            this.availableLanguages = { en: 'English' };
        }
    },
    
    async fetchKeywords() {
        if (this.keywords.length > 0) return;
        try {
            const apiClient = (await import('../services/api')).default;
            const response = await apiClient.get('/api/help/keywords');
            this.keywords = response.data;
        } catch (error) {
            console.error("Failed to fetch keywords:", error);
        }
    },

    isModalOpen(name) {
        return this.activeModal === name;
    },

    openGeneratePersonalityModal() {
        this.openModal('generatePersonality');
    },

    setEmailModalState(subject, body, backgroundColor='#f4f4f8', sendAsText=false) {
        this.emailModalSubject = subject;
        this.emailModalBody = body;
        this.emailModalBackgroundColor = backgroundColor;
        this.emailModalSendAsText = sendAsText;
    },

    toggleSidebar() {
        this.isSidebarOpen = !this.isSidebarOpen;
        localStorage.setItem('lollms-sidebar-open', this.isSidebarOpen);
    },

    closeSidebar() {
        this.isSidebarOpen = false;
        localStorage.setItem('lollms-sidebar-open', 'false');
    },

    initializeSidebarState() {
        const storedState = localStorage.getItem('lollms-sidebar-open');
        if (storedState !== null) {
            this.isSidebarOpen = JSON.parse(storedState);
        } else {
            this.isSidebarOpen = window.innerWidth <= 768;
        }
    },
    
    toggleDataZone() {
        this.isDataZoneVisible = !this.isDataZoneVisible;
        if (!this.isDataZoneVisible) {
            this.isDataZoneExpanded = false;
        }
    },

    toggleDataZoneExpansion() {
        this.isDataZoneExpanded = !this.isDataZoneExpanded;
    },

    setPageTitle({ title, icon = null }) {
        this.pageTitle = title;
        this.pageTitleIcon = icon ? markRaw(icon) : null;
    },
  }
});