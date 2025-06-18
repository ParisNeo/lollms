import { defineStore } from 'pinia';
import apiClient from '../services/api';

export const useUiStore = defineStore('ui', {
  // State is a function that returns the initial state object
  state: () => ({
    currentTheme: 'dark',
    openModals: [],
    modalDataStore: {},
    notifications: [],
    nextNotificationId: 0,
    confirmationOptions: {},
    confirmationPromise: null,
    imageViewerSrc: null,
    availableLanguages: {},
    currentLanguage: localStorage.getItem('lollms_language') || 'en',
    translations: {},
  }),

  // Getters are like computed properties for the store
  getters: {
    isModalOpen: (state) => (modalName) => state.openModals.includes(modalName),
    modalData: (state) => (modalName) => state.modalDataStore[modalName],
    isImageViewerOpen: (state) => !!state.imageViewerSrc,
    
    // The translate getter
    translate: (state) => (key, fallback = null, vars = {}) => {
      let translation = state.translations[key] || fallback || key;
      for (const varKey in vars) {
        translation = translation.replace(new RegExp(`{{${varKey}}}`, 'g'), vars[varKey]);
      }
      return translation;
    },
  },

  // Actions are methods that can mutate the state
  actions: {
    initializeTheme() {
      const savedTheme = localStorage.getItem('theme') || 'dark';
      this.setTheme(savedTheme);
    },
    setTheme(theme) {
      this.currentTheme = theme;
      if (theme === 'dark') {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
      localStorage.setItem('theme', theme);
    },
    toggleTheme() {
      this.setTheme(this.currentTheme === 'dark' ? 'light' : 'dark');
    },
    openModal(modalName, data = null) {
      if (!this.openModals.includes(modalName)) {
        this.openModals.push(modalName);
      }
      if (data) {
        this.modalDataStore[modalName] = data;
      }
    },
    closeModal(modalName) {
      this.openModals = this.openModals.filter(m => m !== modalName);
      delete this.modalDataStore[modalName];
    },
    addNotification(message, type = 'info', duration = 5000) {
      const id = this.nextNotificationId++;
      this.notifications.push({ id, message, type });
      setTimeout(() => this.removeNotification(id), duration);
    },
    removeNotification(id) {
      this.notifications = this.notifications.filter(n => n.id !== id);
    },
    showConfirmation(options = { title: 'Are you sure?', message: 'This action cannot be undone.' }) {
      this.confirmationOptions = options;
      this.openModal('confirmation'); // Use the standard modal flow
      return new Promise((resolve) => {
        this.confirmationPromise = { resolve };
      });
    },
    confirmAction() {
      if (this.confirmationPromise) this.confirmationPromise.resolve(true);
      this.closeModal('confirmation');
    },
    cancelAction() {
      if (this.confirmationPromise) this.confirmationPromise.resolve(false);
      this.closeModal('confirmation');
    },
    openImageViewer(src) {
      this.imageViewerSrc = src;
    },
    closeImageViewer() {
      this.imageViewerSrc = null;
    },
    async fetchAvailableLanguages() {
      try {
        const response = await apiClient.get('/api/languages/');
        this.availableLanguages = response.data;
      } catch (error) {
        console.error("Failed to fetch available languages:", error);
        this.availableLanguages = { 'en': 'English' };
      }
    },
    async loadTranslations(langCode) {
      try {
        const response = await apiClient.get(`/locals/${langCode}.json`);
        this.translations = response.data;
        document.documentElement.lang = langCode.split('-')[0];
      } catch (error) {
        console.error(`Failed to load translations for ${langCode}:`, error);
        if (langCode !== 'en') await this.loadTranslations('en');
      }
    },
    async setLanguage(langCode) {
      this.currentLanguage = langCode;
      localStorage.setItem('lollms_language', langCode);
      await this.loadTranslations(langCode);
    },
    async initializeLocalization() {
      await this.fetchAvailableLanguages();
      let langToLoad = localStorage.getItem('lollms_language');
      if (!langToLoad || !this.availableLanguages[langToLoad]) {
        const browserLang = navigator.language.split('-')[0];
        langToLoad = this.availableLanguages[browserLang] ? browserLang : 'en';
      }
      await this.setLanguage(langToLoad);
    },
  },
});