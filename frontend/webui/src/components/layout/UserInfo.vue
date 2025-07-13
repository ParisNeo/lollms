<script setup>
import { ref, computed, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import UserAvatar from '../ui/UserAvatar.vue';

// --- Import new icons ---
import IconUserCircle from '../../assets/icons/IconUserCircle.vue';
import IconSettings from '../../assets/icons/IconSettings.vue';
import IconUserGroup from '../../assets/icons/IconUserGroup.vue';
import IconDatabase from '../../assets/icons/IconDatabase.vue';
import IconTicket from '../../assets/icons/IconTicket.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';
import IconSignOut from '../../assets/icons/IconSignOut.vue';
import IconChevronUp from '../../assets/icons/IconChevronUp.vue';
// --- End new icons ---

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
              <IconSettings class="w-5 h-5 mr-3 text-gray-500" />
              <span>Settings</span>
            </router-link>
            <router-link v-if="isAdmin" to="/admin" @click="closeMenu" class="menu-item">
                <IconUserGroup class="h-5 w-5 mr-3 text-gray-500" />
                <span>Admin Panel</span>
            </router-link>
            <div class="my-1 border-t dark:border-gray-600"></div>
            <button @click="openDataStores" class="menu-item">
               <IconDatabase class="w-5 h-5 mr-3 text-gray-500" />
              <span>Data Stores</span>
            </button>
            <button v-if="apps.length > 0" @click="activeSubMenu = 'apps'" class="menu-item justify-between">
              <div class="flex items-center">
                <IconTicket class="w-5 h-5 mr-3 text-gray-500" />
                <span>Apps</span>
              </div>
              <IconChevronRight class="w-5 h-5" />
            </button>
            <div class="my-1 border-t dark:border-gray-600"></div>
            <button @click="handleLogout" class="w-full text-left flex items-center px-4 py-2 text-sm text-red-500 dark:text-red-400 rounded-md hover:bg-red-50 dark:hover:bg-red-900/50">
              <IconSignOut class="w-5 h-5 mr-3" />
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
              <IconArrowLeft class="w-5 h-5 mr-3" />
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
      <IconChevronUp class="w-4 h-4 transition-transform transform" :class="{'rotate-180': isMenuOpen}" />
    </button>
  </div>
</template>

<style scoped>
.menu-item {
    @apply w-full text-left flex items-center px-4 py-2 text-sm text-gray-700 dark:text-gray-200 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700;
}
</style>