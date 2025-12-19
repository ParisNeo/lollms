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
import IconServer from '../../assets/icons/IconServer.vue';
import IconSquares2x2 from '../../assets/icons/IconSquares2x2.vue';

const authStore = useAuthStore();
const uiStore = useUiStore();
const dataStore = useDataStore();

const isMenuOpen = ref(false);
const activeSubMenu = ref(null); // null, 'apps', 'studios'
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

    if (isSidebarOpen.value) {
        newLeft = `${rect.left}px`;
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
        width: isSidebarOpen.value ? `${rect.width}px` : '240px',
        maxHeight: `${viewportHeight - 2 * margin}px`,
    };
}

watch(isMenuOpen, (isOpen) => {
    if (isOpen) {
        dataStore.fetchApps();
        nextTick(() => {
            setTimeout(calculateMenuPosition, 50);
            window.addEventListener('resize', calculateMenuPosition, { passive: true });
        });
    } else {
        window.removeEventListener('resize', calculateMenuPosition);
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
            <span class="truncate text-sm font-bold">{{ user.username }}</span>
            <span v-if="isAdmin" class="text-[10px] uppercase font-black text-red-500 dark:text-red-400 tracking-tighter">Administrator</span>
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
                class="fixed z-[60] rounded-xl border bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-800 overflow-hidden"
                ref="menuDivRef"
            >
                <div class="relative overflow-hidden min-h-[320px]">
                    <!-- MAIN MENU -->
                    <transition
                        enter-active-class="transition ease-out duration-200"
                        enter-from-class="opacity-0 -translate-x-full"
                        enter-to-class="opacity-100 translate-x-0"
                        leave-active-class="transition ease-in duration-200 absolute inset-0"
                        leave-from-class="opacity-100 translate-x-0"
                        leave-to-class="opacity-0 -translate-x-full"
                    >
                        <div v-if="!activeSubMenu" class="w-full py-2 flex flex-col h-full">
                            <router-link to="/profile/me" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <UserAvatar :icon="user.icon" :username="user.username" size-class="h-5 w-5" />
                                <span>My Profile</span>
                            </router-link>
                            <router-link to="/friends" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <IconUserGroup class="h-5 w-5 text-gray-400" />
                                <span>Friends</span>
                            </router-link>
                            
                            <div class="my-1 border-t dark:border-gray-700"></div>
                            
                            <!-- Studios Submenu Trigger -->
                            <button @click="activeSubMenu = 'studios'" class="menu-item flex items-center justify-between group">
                                <div class="flex items-center gap-3">
                                    <IconSquares2x2 class="h-5 w-5 text-blue-500" />
                                    <span class="font-semibold">Studios</span>
                                </div>
                                <IconChevronRight class="h-4 w-4 text-gray-400 group-hover:translate-x-0.5 transition-transform" />
                            </button>

                            <router-link to="/settings" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <IconSettings class="h-5 w-5 text-gray-400" />
                                <span>Settings</span>
                            </router-link>

                            <router-link v-if="isAdmin" to="/admin" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <IconUserGroup class="h-5 w-5 text-red-400" />
                                <span class="text-red-600 dark:text-red-400 font-medium">Admin Panel</span>
                            </router-link>

                             <router-link to="/help" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <IconBookOpen class="h-5 w-5 text-gray-400" />
                                <span>Help</span>
                            </router-link>

                            <button v-if="runningApps.length > 0" @click="activeSubMenu = 'apps'" class="menu-item flex items-center justify-between group">
                                <div class="flex items-center gap-3">
                                    <IconTicket class="h-5 w-5 text-green-500" />
                                    <span>Running Apps</span>
                                </div>
                                <IconChevronRight class="h-4 w-4 text-gray-400 group-hover:translate-x-0.5 transition-transform" />
                            </button>
                                                       
                            <div class="mt-auto py-1 border-t dark:border-gray-700">
                                <button @click="handleLogout" class="w-full px-4 py-2.5 text-left text-sm text-red-500 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/50 flex items-center gap-3 transition-colors">
                                    <IconSignOut class="h-5 w-5" />
                                    <span>Sign Out</span>
                                </button>
                            </div>
                        </div>
                    </transition>
                    
                    <!-- STUDIOS SUBMENU -->
                    <transition
                        enter-active-class="transition ease-out duration-200"
                        enter-from-class="opacity-0 translate-x-full"
                        enter-to-class="opacity-100 translate-x-0"
                        leave-active-class="transition ease-in duration-200 absolute inset-0"
                        leave-from-class="opacity-100 translate-x-0"
                        leave-to-class="opacity-0 translate-x-full"
                    >
                        <div v-if="activeSubMenu === 'studios'" class="w-full py-2 flex flex-col h-full bg-white dark:bg-gray-800">
                            <button @click="activeSubMenu = null" class="menu-item flex items-center gap-3 text-gray-500 font-bold mb-1">
                                <IconArrowLeft class="h-4 w-4" />
                                <span>Back</span>
                            </button>
                            <div class="px-4 py-2 text-[10px] font-black uppercase text-gray-400 tracking-widest border-b dark:border-gray-700 mb-1">Studios</div>
                            
                            <router-link to="/notebooks" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <IconServer class="h-5 w-5 text-blue-500" />
                                <div class="flex flex-col">
                                    <span class="font-bold">Notebook Studio</span>
                                    <span class="text-[10px] opacity-60">Research & Writing</span>
                                </div>
                            </router-link>

                            <router-link v-if="isTtiConfigured" to="/image-studio" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <IconPhoto class="h-5 w-5 text-purple-500" />
                                <div class="flex flex-col">
                                    <span class="font-bold">Image Studio</span>
                                    <span class="text-[10px] opacity-60">Visual Creation</span>
                                </div>
                            </router-link>

                            <router-link v-if="isTtsConfigured" to="/voices-studio" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <IconMicrophone class="h-5 w-5 text-pink-500" />
                                <div class="flex flex-col">
                                    <span class="font-bold">Voices Studio</span>
                                    <span class="text-[10px] opacity-60">TTS & Voice Design</span>
                                </div>
                            </router-link>

                            <router-link to="/datastores" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <IconDatabase class="h-5 w-5 text-green-500" />
                                <div class="flex flex-col">
                                    <span class="font-bold">Data Studio</span>
                                    <span class="text-[10px] opacity-60">RAG & Knowledge</span>
                                </div>
                            </router-link>
                        </div>
                    </transition>

                    <!-- APPS SUBMENU -->
                    <transition
                        enter-active-class="transition ease-out duration-200"
                        enter-from-class="opacity-0 translate-x-full"
                        enter-to-class="opacity-100 translate-x-0"
                        leave-active-class="transition ease-in duration-200 absolute inset-0"
                        leave-from-class="opacity-100 translate-x-0"
                        leave-to-class="opacity-0 translate-x-full"
                    >
                        <div v-if="activeSubMenu === 'apps'" class="w-full py-2 flex flex-col h-full bg-white dark:bg-gray-800">
                            <button @click="activeSubMenu = null" class="menu-item flex items-center gap-3 text-gray-500 font-bold mb-1">
                                <IconArrowLeft class="h-4 w-4" />
                                <span>Back</span>
                            </button>
                            <div class="px-4 py-2 text-[10px] font-black uppercase text-gray-400 tracking-widest border-b dark:border-gray-700 mb-1">Active Services</div>
                            <div class="overflow-y-auto max-h-[200px]">
                                <a v-for="app in runningApps" :key="app.id" :href="app.url" target="_blank" rel="noopener noreferrer" class="menu-item flex items-center gap-3">
                                    <UserAvatar :icon="app.icon" :username="app.name" size-class="h-5 w-5" />
                                    <span class="truncate">{{ app.name }}</span>
                                </a>
                            </div>
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
    @apply px-4 py-2.5 text-sm transition-colors hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer w-full text-left flex items-center;
}
</style>
