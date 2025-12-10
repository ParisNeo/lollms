<!-- [UPDATE] frontend/webui/src/components/layout/UserInfo.vue -->
<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import UserAvatar from '../ui/Cards/UserAvatar.vue';

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
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconMicrophone from '../../assets/icons/IconMicrophone.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue'; // Placeholder for timelapse if needed, using generic

const authStore = useAuthStore();
const uiStore = useUiStore();
const dataStore = useDataStore();

const isMenuOpen = ref(false);
const activeSubMenu = ref(null);
const menuStyle = ref({});
const triggerRef = ref(null);
const menuDivRef = ref(null);

const user = computed(() => authStore.user);
const isAdmin = computed(() => authStore.isAdmin);
const isSidebarOpen = computed(() => uiStore.isSidebarOpen);
const isTtsConfigured = computed(() => !!user.value?.tts_binding_model_name);
const isTtiConfigured = computed(() => !!user.value?.tti_binding_model_name);

const runningApps = computed(() => {
    const allServices = [...dataStore.userApps, ...dataStore.systemApps];
    return allServices.filter(app => app.active && app.url && (!app.is_installed || app.status === 'running'));
});


function calculateMenuPosition() {
    if (!triggerRef.value || !menuDivRef.value) return;

    const rect = triggerRef.value.getBoundingClientRect();
    const margin = 8;
    const viewportHeight = window.innerHeight;
    const viewportWidth = window.innerWidth;

    const naturalMenuHeight = menuDivRef.value.offsetHeight;
    const naturalMenuWidth = menuDivRef.value.offsetWidth;

    let newTop = 'auto';
    let newBottom = 'auto';
    let newLeft = 'auto';
    let newRight = 'auto';
    let newWidth = `${naturalMenuWidth}px`;

    if (isSidebarOpen.value) {
        newLeft = `${rect.left}px`;
        newWidth = `${rect.width}px`;
        const spaceBelow = viewportHeight - rect.bottom;
        const spaceAbove = rect.top;

        if (spaceBelow >= naturalMenuHeight + margin || spaceBelow > spaceAbove) {
            newTop = `${rect.bottom + margin}px`;
        } else {
            newBottom = `${viewportHeight - rect.top + margin}px`;
        }
    } else {
        newLeft = `${rect.right + margin}px`;
        const desiredTop = rect.top + (rect.height / 2) - (naturalMenuHeight / 2);
        newTop = `${Math.max(margin, Math.min(desiredTop, viewportHeight - naturalMenuHeight - margin))}px`;
        
        if (newLeft !== 'auto' && parseFloat(newLeft) + naturalMenuWidth > viewportWidth - margin) {
            newLeft = `${rect.left - naturalMenuWidth - margin}px`;
        }
    }
    
    if (newLeft !== 'auto' && parseFloat(newLeft) < margin) {
        newLeft = `${margin}px`;
    }

    menuStyle.value = {
        top: newTop,
        bottom: newBottom,
        left: newLeft,
        right: newRight,
        width: newWidth,
        maxHeight: `${viewportHeight - 2 * margin}px`,
        overflowY: 'auto'
    };
}

watch(isMenuOpen, (isOpen) => {
    if (isOpen) {
        dataStore.fetchApps();
        nextTick(() => {
            setTimeout(() => {
                calculateMenuPosition();
                window.addEventListener('resize', calculateMenuPosition, { passive: true });
                window.addEventListener('scroll', calculateMenuPosition, { passive: true });
            }, 50);
        });
    } else {
        window.removeEventListener('resize', calculateMenuPosition);
        window.removeEventListener('scroll', calculateMenuPosition);
    }
});

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
                ref="menuDivRef"
            >
                <div class="relative min-h-[280px]">
                    <transition
                        enter-active-class="transition ease-out duration-200"
                        enter-from-class="opacity-0 -translate-x-full"
                        enter-to-class="opacity-100 translate-x-0"
                        leave-active-class="transition ease-in duration-200 absolute top-0 left-0 right-0"
                        leave-from-class="opacity-100 translate-x-0"
                        leave-to-class="opacity-0 -translate-x-full"
                    >
                        <div v-if="!activeSubMenu" class="w-full py-1 h-full overflow-y-auto">
                            <!-- Me Section -->
                            <router-link to="/profile/me" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <UserAvatar :icon="user.icon" :username="user.username" size-class="h-5 w-5" />
                                <span>My Profile</span>
                            </router-link>
                            <router-link to="/friends" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <IconUserGroup class="h-5 w-5 text-gray-500" />
                                <span>Friends</span>
                            </router-link>
                            
                            <!-- Studios Section -->
                            <div class="my-1 border-t dark:border-gray-600"></div>
                            <router-link v-if="isTtsConfigured" to="/voices-studio" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <IconMicrophone class="h-5 w-5 text-gray-500" />
                                <span>Voices Studio</span>
                            </router-link>
                            <router-link v-if="isTtiConfigured" to="/image-studio" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <IconPhoto class="h-5 w-5 text-gray-500" />
                                <span>Image Studio</span>
                            </router-link>
                            <router-link v-if="isTtiConfigured" to="/image-studio/timelapse" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <svg class="h-5 w-5 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="2" y1="7" x2="7" y2="7"></line><line x1="2" y1="17" x2="7" y2="17"></line><line x1="17" y1="17" x2="22" y2="17"></line><line x1="17" y1="7" x2="22" y2="7"></line></svg>
                                <span>Timelapse</span>
                            </router-link>
                            <router-link to="/datastores" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <IconDatabase class="h-5 w-5 text-gray-500" />
                                <span>Data Studio</span>
                            </router-link>

                            <!-- System Section -->
                            <div class="my-1 border-t dark:border-gray-600"></div>
                            <router-link to="/settings" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <IconSettings class="h-5 w-5 text-gray-500" />
                                <span>Settings</span>
                            </router-link>
                            <router-link v-if="isAdmin" to="/admin" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <IconUserGroup class="h-5 w-5 text-gray-500" />
                                <span>Admin Panel</span>
                            </router-link>
                             <router-link to="/help" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <IconBookOpen class="h-5 w-5 text-gray-500" />
                                <span>Help</span>
                            </router-link>
                            <button v-if="runningApps.length > 0" @click="activeSubMenu = 'apps'" class="menu-item flex items-center justify-between">
                                <div class="flex items-center gap-3">
                                    <IconTicket class="h-5 w-5 text-gray-500" />
                                    <span>Running Apps</span>
                                </div>
                                <IconChevronRight class="h-5 w-5" />
                            </button>
                                                       
                            <div class="my-1 border-t dark:border-gray-600"></div>
                            <button @click="handleLogout" class="w-full rounded-md px-4 py-2 text-left text-sm text-red-500 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/50 flex items-center gap-3">
                            <IconSignOut class="h-5 w-5" />
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
                        <div v-if="activeSubMenu === 'apps'" class="absolute inset-0 w-full bg-white py-1 dark:bg-gray-800 h-full overflow-y-auto">
                            <button @click="activeSubMenu = null" class="menu-item flex items-center gap-3">
                            <IconArrowLeft class="h-5 w-5" />
                            <span>Back</span>
                            </button>
                            <div class="my-1 border-t dark:border-gray-600"></div>
                            <a v-for="app in runningApps" :key="app.id" :href="app.url" target="_blank" rel="noopener noreferrer" class="menu-item flex items-center gap-3">
                                <UserAvatar :icon="app.icon" :username="app.name" size-class="h-5 w-5" />
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
