<script>
import { mapState, mapActions } from 'pinia';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';

export default {
  name: 'UserInfo',
  data() {
    return {
      isMenuOpen: false,
    };
  },
  computed: {
    ...mapState(useAuthStore, ['user', 'isAdmin']),
  },
  methods: {
    ...mapActions(useAuthStore, ['logout']),
    ...mapActions(useUiStore, ['openModal']),
    
    toggleMenu() {
      this.isMenuOpen = !this.isMenuOpen;
    },
    closeMenu() {
      this.isMenuOpen = false;
    },
    handleLogout() {
      this.logout();
      this.closeMenu();
    },
    openSettings() {
      this.openModal('settings');
      this.closeMenu();
    },
    openDataStores() {
      this.openModal('dataStores');
      this.closeMenu();
    },
    openExportModal() {
        this.openModal('export');
        this.closeMenu();
    },
    openImportModal() {
        this.openModal('import');
        this.closeMenu();
    },
    openFriends() { console.log('Opening friends modal'); this.closeMenu(); },
  },
  // --- FIX: REMOVED the local directive definition ---
};
</script>

<template>
  <div class="relative" v-if="user" v-on-click-outside="closeMenu">
    <!-- Dropdown Menu -->
    <div 
      v-if="isMenuOpen"
      class="absolute bottom-full left-0 right-0 mb-2 w-full border dark:border-gray-600 rounded-lg shadow-xl py-1 bg-white dark:bg-gray-800 z-20"
    >
      <!-- Main Menu Items -->
      <div class="px-1">
        <button @click="openSettings" class="w-full flex items-center px-3 py-2 text-sm rounded-md hover:bg-gray-100 dark:hover:bg-gray-700">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4 mr-3 text-gray-500"><path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 0 1 0 1.255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.063-.374-.313-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 0 1 0-1.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /></svg>
            <span>Settings</span>
        </button>
        <button @click="openDataStores" class="w-full flex items-center px-3 py-2 text-sm rounded-md hover:bg-gray-100 dark:hover:bg-gray-700">
             <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4 mr-3 text-gray-500"><path stroke-linecap="round" stroke-linejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" /></svg>
            <span>Data Stores</span>
        </button>
      </div>
      <!-- Separator -->
      <div class="my-1 border-t dark:border-gray-600"></div>
      <!-- Data Management -->
      <div class="px-1">
        <div class="px-3 py-1 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">Data Management</div>
        <button @click="openExportModal" class="w-full flex items-center px-3 py-2 text-sm rounded-md hover:bg-gray-100 dark:hover:bg-gray-700">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4 mr-3 text-gray-500"><path stroke-linecap="round" stroke-linejoin="round" d="M9 8.25H7.5a2.25 2.25 0 0 0-2.25 2.25v9a2.25 2.25 0 0 0 2.25 2.25h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25H15m0-3-3-3m0 0-3 3m3-3v11.25" /></svg>
            <span>Export Data</span>
        </button>
        <button @click="openImportModal" class="w-full flex items-center px-3 py-2 text-sm rounded-md hover:bg-gray-100 dark:hover:bg-gray-700">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4 mr-3 text-gray-500"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l3 3m0 0 3-3m-3 3v-9" /></svg>
            <span>Import Data</span>
        </button>
      </div>
      <!-- Separator -->
      <div class="my-1 border-t dark:border-gray-600"></div>
      <!-- Logout -->
      <div class="px-1">
        <button @click="handleLogout" class="w-full flex items-center px-3 py-2 text-sm text-red-500 dark:text-red-400 rounded-md hover:bg-red-50 dark:hover:bg-red-900/50">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4 mr-3"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" /></svg>
          <span>Sign Out</span>
        </button>
      </div>
    </div>

    <!-- User Info Button -->
    <button 
      @click="toggleMenu"
      class="w-full flex items-center justify-between text-sm p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors focus:outline-none text-gray-800 dark:text-gray-100"
    >
      <div class="flex items-center">
        <div class="w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center mr-3">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" /></svg>
        </div>
        <div class="flex flex-col items-start">
          <span class="font-medium text-sm">{{ user.username }}</span>
          <span v-if="isAdmin" class="text-xs text-red-500 dark:text-red-400 font-medium">Administrator</span>
        </div>
      </div>
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 transition-transform transform" :class="{'rotate-180': isMenuOpen}">
        <path stroke-linecap="round" stroke-linejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
      </svg>
    </button>
  </div>
</template>
