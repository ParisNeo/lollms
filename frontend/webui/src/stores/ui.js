import { defineStore } from 'pinia';
import { markRaw } from 'vue';
import router from '../router';
import apiClient from '../services/api';

export const useUiStore = defineStore('ui', {
  state: () => ({
    mainView: 'chat',
    modalStack: [],
    modalProps: {},
    notifications: [],
    currentTheme: localStorage.getItem('lollms-theme') || 'light',
    currentVibe: localStorage.getItem('lollms-vibe') || 'default',
    currentLanguage: localStorage.getItem('lollms-language') || 'en',
    message_font_size: 14,
    imageViewer: {
      isOpen: false,
      imageList: [],
      startIndex: 0,
    },
    // Slideshow State
    slideshow: {
        isOpen: false,
        slides: [], // Items with { src, prompt, duration? }
        startIndex: 0,
        title: '',
        messageId: null
    },
    confirmationOptions: {
        title: 'Are you sure?',
        message: 'This action cannot be undone.',
        confirmText: 'Confirm',
        cancelText: 'Cancel',
        onConfirm: () => {},
        onCancel: () => {},
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
    isChatSidebarOpen: false,
    keywords: [],
    isDataZoneVisible: false,
    isDataZoneExpanded: false,
    dataZoneTab: 'context', // 'context', 'files', 'workspace', 'memory', 'personality'
    activeSplitArtefactTitle: null, // Title of the artefact open in the workspace split view
    showNewMessagesButton: false,
    generatePersonalityModalProps: {
        prompt: '',
        customEnhancePrompt: ''
    },
    pageTitle: '',
    pageTitleIcon: null,

    // Maintenance & System State
    isMaintenanceMode: false,
    maintenanceMessage: '',
    isConnectionLost: false,
    appVersion: '',
  }),

  getters: {
    activeModal: (state) => state.modalStack.length > 0 ? state.modalStack[state.modalStack.length - 1] : null,
    modalData: (state) => (name) => state.modalProps[name] || null,
    isImageViewerOpen: (state) => state.imageViewer.isOpen,
    imageViewerData: (state) => state.imageViewer,
    isSlideshowOpen: (state) => state.slideshow.isOpen,
    slideshowData: (state) => state.slideshow,
    /**
     * Resolves the current source URL/Data for the image viewer.
     */
    imageViewerSrc: (state) => {
        const item = state.imageViewer.imageList[state.imageViewer.startIndex];
        return item ? (item.src || item) : null;
    }
  },

  actions: {
    toggleChatSidebar() {
        this.isChatSidebarOpen = !this.isChatSidebarOpen;
    },
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
        if (['feed', 'chat', 'messages'].includes(viewName)) {
            this.mainView = viewName;
            if (viewName !== 'messages' && router.currentRoute.value?.path !== '/') {
                router.push('/');
            }
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
    
    // Version Check & Changelog Logic
    async checkVersionUpdates() {
        try {
            const res = await apiClient.get('/api/public/version');
            const currentVer = res.data.version;
            this.appVersion = currentVer;

            const lastSeenVer = localStorage.getItem('lollms_last_seen_version');
            
            if (lastSeenVer !== currentVer) {
                try {
                    const changelogRes = await apiClient.get('/api/public/changelog', { params: { version: currentVer } });
                    this.openModal('whatsNext', { 
                        isUpdate: true, 
                        changelog: changelogRes.data 
                    });
                } catch(e) {
                     this.openModal('whatsNext', { 
                        isUpdate: true, 
                        changelog: { title: `Updated to v${currentVer}`, content: "Check the GitHub repository for detailed release notes." } 
                    });
                }
                
                localStorage.setItem('lollms_last_seen_version', currentVer);
            }
        } catch (e) {
            console.error("Version check failed", e);
        }
    },

    addNotification(message, type = 'info', duration = 3000, persistent = false, sender = null, icon = null) {
        const id = Date.now() + Math.random();
        this.notifications.push({ id, message, type, duration, persistent, sender, icon });
        
        if (!persistent && duration > 0) {
            setTimeout(() => {
                this.removeNotification(id);
            }, duration);
        }
    },

    removeNotification(id) {
        this.notifications = this.notifications.filter(n => n.id !== id);
    },
    
    setTheme(theme) {
        this.currentTheme = theme;
        localStorage.setItem('lollms-theme', theme);
        document.documentElement.classList.toggle('dark', theme === 'dark');
    },

    setVibe(vibe) {
        const root = document.documentElement;
        const vibeClasses = Array.from(root.classList).filter(c => c.startsWith('vibe-'));
        vibeClasses.forEach(c => root.classList.remove(c));

        this.currentVibe = vibe;
        localStorage.setItem('lollms-vibe', vibe);

        if (vibe && vibe !== 'default') {
            root.classList.add(`vibe-${vibe}`);
        }

        console.log(`[UI] Vibe applied: ${vibe || 'default'}. Active classes:`, root.className);
    },

    toggleTheme() {
        this.setTheme(this.currentTheme === 'light' ? 'dark' : 'light');
    },

    initializeTheme() {
        this.setTheme(this.currentTheme);
        this.setVibe(this.currentVibe);
    },

    setLanguage(langCode) {
        this.currentLanguage = langCode;
        localStorage.setItem('lollms-language', langCode);
    },

    openImageViewer(payload) {
        let list = [];
        let index = 0;

        if (typeof payload === 'string') {
            list = [{ src: payload, prompt: '' }];
            index = 0;
        } else if (payload && typeof payload === 'object') {
            if (Array.isArray(payload.imageList) && payload.imageList.length > 0) {
                list = payload.imageList;
                index = typeof payload.startIndex === 'number' ? payload.startIndex : 0;
            } else if (payload.src) {
                list = [{ src: payload.src, prompt: payload.prompt || '', thumbnail: payload.thumbnail || payload.src }];
                index = 0;
            }
        }

        if (index < 0 || (list.length > 0 && index >= list.length)) {
            index = 0;
        }

        // Reassign with a fresh object state to ensure all computed/watch dependencies trigger
        this.imageViewer = {
            isOpen: true,
            imageList: list,
            startIndex: index,
        };
    },

    closeImageViewer() {
        this.imageViewer = {
            isOpen: false,
            imageList: [],
            startIndex: 0,
        };
    },
    
    openSlideshow({ slides, startIndex = 0, title = 'Slideshow', messageId = null }) {
        this.slideshow.slides = slides || [];
        this.slideshow.startIndex = startIndex;
        this.slideshow.title = title;
        this.slideshow.messageId = messageId;
        this.slideshow.isOpen = true;
    },
    
    setSlideshowIndex(index) {
        this.slideshow.startIndex = index;
    },

    closeSlideshow() {
        this.slideshow.isOpen = false;
        setTimeout(() => {
            this.slideshow.slides = [];
            this.slideshow.messageId = null;
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
            const response = await apiClient.get('/api/languages/');
            this.availableLanguages = response.data;
        } catch (error) {
            this.availableLanguages = { en: 'English' };
        }
    },
    
    async fetchKeywords() {
        if (this.keywords.length > 0) return;
        try {
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

    openSidebar() {
        this.isSidebarOpen = true;
        localStorage.setItem('lollms-sidebar-open', 'true');
    },

    closeSidebar() {
        this.isSidebarOpen = false;
        localStorage.setItem('lollms-sidebar-open', 'false');
    },

    initializeSidebarState() {
        const storedState = localStorage.getItem('lollms-sidebar-open');
        if (storedState !== null) {
            try {
                this.isSidebarOpen = JSON.parse(storedState);
            } catch (e) {
                this.isSidebarOpen = window.innerWidth > 768;
            }
        } else {
            this.isSidebarOpen = window.innerWidth > 768;
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

    setMaintenanceMode(enabled, message = "") {
        this.isMaintenanceMode = enabled;
        this.maintenanceMessage = message;
        if (!enabled) {
            this.closeModal();
        }
    },

    setConnectionLost(status) {
        this.isConnectionLost = status;
    }
  }
});