<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import UserAvatar from '../ui/UserAvatar.vue';

// --- Import icons ---
import IconUserCircle from '../../assets/icons/IconUserCircle.vue';
import IconSettings from '../../assets/icons/IconSettings.vue';
import IconUserGroup from '../../assets/icons/IconUserGroup.vue';
import IconDatabase from '../../assets/icons/IconDatabase.vue';
import IconTicket from '../../assets/icons/IconTicket.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';
import IconSignOut from '../../assets/icons/IconSignOut.vue';
import IconChevronUp from '../../assets/icons/IconChevronUp.vue';

const authStore = useAuthStore();
const uiStore = useUiStore();
const dataStore = useDataStore();

const isMenuOpen = ref(false);
const activeSubMenu = ref(null);
const menuStyle = ref({});
const triggerRef = ref(null); // Ref for the trigger button

const user = computed(() => authStore.user);
const isAdmin = computed(() => authStore.isAdmin);
const isSidebarOpen = computed(() => uiStore.isSidebarOpen);
const apps = computed(() => [...dataStore.userApps, ...dataStore.systemApps].filter(app => app.active));


function calculateMenuPosition() {
    if (!triggerRef.value) return;

    const rect = triggerRef.value.getBoundingClientRect();
    const menuHeight = 280; // The fixed height of the menu panel
    const menuWidth = 224; // w-56
    const margin = 8;

    let styles = {};

    if (isSidebarOpen.value) {
        // When sidebar is open, default to positioning menu above the button
        styles = {
            width: `${rect.width}px`,
            left: `${rect.left}px`,
            bottom: `${window.innerHeight - rect.top + margin}px`,
            top: 'auto',
            transform: 'none',
        };
        // If there's not enough space above, flip to below
        if (rect.top < menuHeight + margin) {
            styles.bottom = 'auto';
            styles.top = `${rect.bottom + margin}px`;
        }
    } else {
        // When sidebar is collapsed, position menu to the right
        const topPosition = rect.top + rect.height / 2 - menuHeight / 2;
        styles = {
            width: `${menuWidth}px`,
            left: `${rect.right + margin}px`,
            top: `${Math.max(margin, topPosition)}px`, // Ensure it doesn't go off the top
            bottom: 'auto',
            transform: 'none',
        };
        // Check if it goes off the bottom
        if (parseFloat(styles.top) + menuHeight + margin > window.innerHeight) {
            styles.top = 'auto';
            styles.bottom = `${margin}px`;
        }
    }
    
    menuStyle.value = styles;
}

// Watch for the menu opening/closing
watch(isMenuOpen, (isOpen) => {
    if (isOpen) {
        nextTick(() => {
            calculateMenuPosition();
            window.addEventListener('resize', calculateMenuPosition, { passive: true });
            window.addEventListener('scroll', calculateMenuPosition, { passive: true });
        });
    } else {
        window.removeEventListener('resize', calculateMenuPosition);
        window.removeEventListener('scroll', calculateMenuPosition);
    }
});

// If the sidebar state changes while the menu is open, recalculate the position.
watch(isSidebarOpen, () => {
    if (isMenuOpen.value) {
        calculateMenuPosition();
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
      const triggerEl = triggerRef.value;
      if (!(el === event.target || el.contains(event.target) || triggerEl?.contains(event.target))) {
        binding.value();
      }
    };
    document.addEventListener('mousedown', el.clickOutsideEvent);
  },
  unmounted: el => {
    document.removeEventListener('mousedown', el.clickOutsideEvent);
  },
};
</script>

<template>
  <div class="relative w-full" v-if="user">
    <!-- The user button that triggers the menu -->
    <button 
      ref="triggerRef"
      @click="toggleMenu"
      class="w-full flex items-center justify-center rounded-lg p-2 text-gray-800 transition-colors hover:bg-gray-200 focus:outline-none dark:text-gray-100 dark:hover:bg-gray-700"
    >
      <div class="flex items-center" :class="{ 'w-full justify-between': isSidebarOpen }">
        <div class="flex min-w-0 items-center">
          <UserAvatar :icon="user.icon" :username="user.username" size-class="w-8 h-8" class="mr-3 flex-shrink-0" />
          
          <div v-if="isSidebarOpen" class="flex min-w-0 flex-col items-start">
            <span class="truncate text-sm font-medium">{{ user.username }}</span>
            <span v-if="isAdmin" class="text-xs font-medium text-red-500 dark:text-red-400">Administrator</span>
          </div>
        </div>
        <IconChevronUp v-if="isSidebarOpen" class="ml-2 h-4 w-4 transform transition-transform" :class="{'rotate-180': isMenuOpen}" />
      </div>
    </button>

    <!-- Teleport the menu to the body tag to escape clipping containers -->
    <Teleport to="body">
        <Transition
            enter-active-class="transition-opacity ease-out duration-200"
            enter-from-class="opacity-0"
            enter-to-class="opacity-100"
            leave-active-class="transition-opacity ease-in duration-150"
            leave-from-class="opacity-100"
            leave-to-class="opacity-0"
        >
            <div 
                v-if="isMenuOpen"
                :style="menuStyle"
                v-on-click-outside="closeMenu"
                class="fixed z-30 w-56 rounded-lg border bg-white shadow-xl dark:border-gray-600 dark:bg-gray-800"
            >
                <div class="relative h-[280px] overflow-hidden">
                    <transition
                        enter-active-class="transition ease-out duration-200"
                        enter-from-class="opacity-0 -translate-x-full"
                        enter-to-class="opacity-100 translate-x-0"
                        leave-active-class="transition ease-in duration-200 absolute top-0 left-0 right-0"
                        leave-from-class="opacity-100 translate-x-0"
                        leave-to-class="opacity-0 -translate-x-full"
                    >
                        <div v-if="!activeSubMenu" class="w-full py-1">
                            <router-link to="/profile/me" @click="closeMenu" class="menu-item">
                            <UserAvatar :icon="user.icon" :username="user.username" size-class="h-5 w-5 mr-3" />
                            <span>My Profile</span>
                            </router-link>
                            <router-link to="/settings" @click="closeMenu" class="menu-item">
                            <IconSettings class="mr-3 h-5 w-5 text-gray-500" />
                            <span>Settings</span>
                            </router-link>
                            <router-link v-if="isAdmin" to="/admin" @click="closeMenu" class="menu-item">
                                <IconUserGroup class="mr-3 h-5 w-5 text-gray-500" />
                                <span>Admin Panel</span>
                            </router-link>
                            <div class="my-1 border-t dark:border-gray-600"></div>
                            <button @click="openDataStores" class="menu-item">
                            <IconDatabase class="mr-3 h-5 w-5 text-gray-500" />
                            <span>Data Stores</span>
                            </button>
                            <button v-if="apps.length > 0" @click="activeSubMenu = 'apps'" class="menu-item justify-between">
                            <div class="flex items-center">
                                <IconTicket class="mr-3 h-5 w-5 text-gray-500" />
                                <span>Apps</span>
                            </div>
                            <IconChevronRight class="h-5 w-5" />
                            </button>
                            <div class="my-1 border-t dark:border-gray-600"></div>
                            <button @click="handleLogout" class="w-full rounded-md px-4 py-2 text-left text-sm text-red-500 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/50 flex items-center">
                            <IconSignOut class="mr-3 h-5 w-5" />
                            <span>Sign Out</span>
                            </button>
                        </div>
                    </transition>
                    
                    <transition
                        enter-active-class="transition ease-out duration-200"
                        enter-from-class="opacity-0 translate-x-full"
                        enter-to-class="opacity-100 translate-x-0"
                        leave-active-class="transition ease-in duration-200 absolute top-0 left-0 right-0"
                        leave-from-class="opacity-100 translate-x-0"
                        leave-to-class="opacity-0 translate-x-full"
                    >
                        <div v-if="activeSubMenu === 'apps'" class="absolute inset-0 w-full bg-white py-1 dark:bg-gray-800">
                            <button @click="activeSubMenu = null" class="menu-item">
                            <IconArrowLeft class="mr-3 h-5 w-5" />
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
        </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.menu-item {
    @apply flex w-full items-center rounded-md px-4 py-2 text-left text-sm text-gray-700 transition-colors hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-700;
}
</style>