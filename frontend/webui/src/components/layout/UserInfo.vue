<script setup>
import { ref, computed, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import UserAvatar from '../ui/UserAvatar.vue';

const authStore = useAuthStore();
const uiStore = useUiStore();
const dataStore = useDataStore();

const isMenuOpen = ref(false);
const activeSubMenu = ref(null);

const user = computed(() => authStore.user);
const isAdmin = computed(() => authStore.isAdmin);
const apps = computed(() => [...dataStore.userApps, ...dataStore.systemApps].filter(app => app.active));

onMounted(() => {
    if (authStore.isAuthenticated) {
        dataStore.fetchApps();
    }
});

function toggleMenu() {
  isMenuOpen.value = !isMenuOpen.value;
  if (!isMenuOpen.value) {
    activeSubMenu.value = null;
  }
}

function closeMenu() {
  isMenuOpen.value = false;
  activeSubMenu.value = null;
}

function handleLogout() {
  authStore.logout();
  closeMenu();
}

function openDataStores() {
  uiStore.openModal('dataStores');
  closeMenu();
}

const vOnClickOutside = {
  beforeMount: (el, binding) => {
    el.clickOutsideEvent = event => {
      if (!(el === event.target || el.contains(event.target))) {
        binding.value();
      }
    };
    document.addEventListener('click', el.clickOutsideEvent);
  },
  unmounted: el => {
    document.removeEventListener('click', el.clickOutsideEvent);
  },
};
</script>

<template>
  <div class="relative" v-if="user" v-on-click-outside="closeMenu">
    <div 
      v-if="isMenuOpen"
      class="absolute bottom-full left-0 right-0 mb-2 w-full border dark:border-gray-600 rounded-lg shadow-xl bg-white dark:bg-gray-800 z-20"
    >
      <div class="relative overflow-hidden h-[280px]">
        <transition
          enter-active-class="transition ease-out duration-200"
          enter-from-class="opacity-0 -translate-x-full"
          enter-to-class="opacity-100 translate-x-0"
          leave-active-class="transition ease-in duration-200 absolute"
          leave-from-class="opacity-100 translate-x-0"
          leave-to-class="opacity-0 -translate-x-full"
        >
          <div v-if="!activeSubMenu" class="py-1 w-full">
            <router-link to="/profile/me" @click="closeMenu" class="menu-item">
              <UserAvatar :icon="user.icon" :username="user.username" size-class="h-5 w-5 mr-3" />
              <span>My Profile</span>
            </router-link>
            <router-link to="/settings" @click="closeMenu" class="menu-item">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5 mr-3 text-gray-500"><path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 0 1 0 1.255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.063-.374-.313-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 0 1 0-1.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /></svg>
              <span>Settings</span>
            </router-link>
            <router-link v-if="isAdmin" to="/admin" @click="closeMenu" class="menu-item">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-3 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M15 21v-1.5a6.375 6.375 0 00-3.262-5.171M9 10a3 3 0 11-6 0 3 3 0 016 0zm3 2a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                <span>Admin Panel</span>
            </router-link>
            <div class="my-1 border-t dark:border-gray-600"></div>
            <button @click="openDataStores" class="menu-item">
               <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5 mr-3 text-gray-500"><path stroke-linecap="round" stroke-linejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" /></svg>
              <span>Data Stores</span>
            </button>
            <button v-if="apps.length > 0" @click="activeSubMenu = 'apps'" class="menu-item justify-between">
              <div class="flex items-center">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5 mr-3 text-gray-500"><path d="M3.5 2.75a.75.75 0 0 0-1.5 0v14.5a.75.75 0 0 0 1.5 0v-1.313a3.504 3.504 0 0 1 2.37-3.187 2.002 2.002 0 0 1 1.732 0 3.504 3.504 0 0 1 2.37 3.187V17.25a.75.75 0 0 0 1.5 0v-1.313a3.504 3.504 0 0 1 2.37-3.187 2.002 2.002 0 0 1 1.732 0 3.504 3.504 0 0 1 2.37 3.187V17.25a.75.75 0 0 0 1.5 0V2.75a.75.75 0 0 0-1.5 0v1.313a3.504 3.504 0 0 1-2.37 3.187 2.002 2.002 0 0 1-1.732 0 3.504 3.504 0 0 1-2.37-3.187V2.75a.75.75 0 0 0-1.5 0v1.313a3.504 3.504 0 0 1-2.37 3.187 2.002 2.002 0 0 1-1.732 0 3.504 3.504 0 0 1-2.37-3.187V2.75Z" /></svg>
                <span>Apps</span>
              </div>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5"><path fill-rule="evenodd" d="M8.22 5.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.75.75 0 0 1-1.06-1.06L11.94 10 8.22 6.28a.75.75 0 0 1 0-1.06Z" clip-rule="evenodd" /></svg>
            </button>
            <div class="my-1 border-t dark:border-gray-600"></div>
            <button @click="handleLogout" class="w-full text-left flex items-center px-4 py-2 text-sm text-red-500 dark:text-red-400 rounded-md hover:bg-red-50 dark:hover:bg-red-900/50">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5 mr-3"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" /></svg>
              <span>Sign Out</span>
            </button>
          </div>
        </transition>
        
        <transition
          enter-active-class="transition ease-out duration-200"
          enter-from-class="opacity-0 translate-x-full"
          enter-to-class="opacity-100 translate-x-0"
          leave-active-class="transition ease-in duration-200 absolute"
          leave-from-class="opacity-100 translate-x-0"
          leave-to-class="opacity-0 translate-x-full"
        >
          <div v-if="activeSubMenu === 'apps'" class="py-1 absolute inset-0 bg-white dark:bg-gray-800 w-full">
            <button @click="activeSubMenu = null" class="menu-item">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5 mr-3"><path fill-rule="evenodd" d="M11.78 5.22a.75.75 0 0 1 0 1.06L8.56 10l3.22 3.22a.75.75 0 1 1-1.06 1.06l-3.75-3.75a.75.75 0 0 1 0-1.06l3.75-3.75a.75.75 0 0 1 1.06 0Z" clip-rule="evenodd" /></svg>
              <span>Back</span>
            </button>
            <div class="my-1 border-t dark:border-gray-600"></div>
            <a v-for="app in apps" :key="app.id" :href="app.url" target="_blank" rel="noopener noreferrer" class="menu-item">
                <UserAvatar :icon="app.icon" :username="app.name" size-class="h-5 w-5 mr-3" />
                <span class="truncate">{{ app.name }}</span>
            </a>
          </div>
        </transition>
      </div>
    </div>

    <button 
      @click="toggleMenu"
      class="w-full flex items-center justify-between text-sm p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors focus:outline-none text-gray-800 dark:text-gray-100"
    >
      <div class="flex items-center">
        <UserAvatar :icon="user.icon" :username="user.username" size-class="w-8 h-8" class="mr-3 flex-shrink-0" />
        
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

<style scoped>
.menu-item {
    @apply w-full text-left flex items-center px-4 py-2 text-sm text-gray-700 dark:text-gray-200 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700;
}
</style>