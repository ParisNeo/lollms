<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
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
import IconChevronDown from '../../assets/icons/IconChevronDown.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconMicrophone from '../../assets/icons/IconMicrophone.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconServer from '../../assets/icons/IconServer.vue';
import IconSquares2x2 from '../../assets/icons/IconSquares2x2.vue';
import IconMessage from '../../assets/icons/IconMessage.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconShare from '../../assets/icons/IconShare.vue';

const authStore = useAuthStore();
const uiStore = useUiStore();
const dataStore = useDataStore();
const route = useRoute();
const router = useRouter();

const isMenuOpen = ref(false);
const activeSubMenu = ref(null); // null, 'apps', 'studios'
const triggerRef = ref(null);

const user = computed(() => authStore.user);
const isAdmin = computed(() => authStore.isAdmin);
const isTtsConfigured = computed(() => !!user.value?.tts_binding_model_name);
const isTtiConfigured = computed(() => !!user.value?.tti_binding_model_name);

// Highlight Logic
const isDiscussionActive = computed(() => route.path === '/' && uiStore.mainView === 'chat');
const isNotebooksActive = computed(() => route.path.startsWith('/notebooks'));
const isImageStudioActive = computed(() => route.path.startsWith('/image-studio'));
const isVoicesStudioActive = computed(() => route.path.startsWith('/voices-studio'));
const isDataStoresActive = computed(() => route.path.startsWith('/datastores'));
const isFlowStudioActive = computed(() => route.path.startsWith('/flow-studio'));

const runningApps = computed(() => {
    const allServices = [...dataStore.userApps, ...dataStore.systemApps];
    return allServices.filter(app => app.active && app.url && (!app.is_installed || app.status === 'running'));
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

function openDiscussionStudio() {
    router.push('/');
    uiStore.setMainView('chat');
    closeMenu();
}

const vOnClickOutside = {
  mounted: (el, binding) => {
    el.clickOutsideEvent = event => {
      if (!(el === event.target || el.contains(event.target) || triggerRef.value?.contains(event.target))) {
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
  <div class="relative" v-if="user">
    <!-- Compact Header Trigger -->
    <button 
      ref="triggerRef"
      @click="toggleMenu"
      class="flex items-center gap-2 p-1 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-all border border-transparent hover:border-gray-200 dark:hover:border-gray-600 shadow-sm"
      :class="{'ring-2 ring-blue-500/20 bg-blue-50 dark:bg-blue-900/20': isMenuOpen}"
    >
      <UserAvatar :icon="user.icon" :username="user.username" size-class="h-8 w-8" />
      <IconChevronDown v-if="!isMenuOpen" class="w-3.5 h-3.5 text-gray-400 mr-1" />
      <IconXMark v-else class="w-3.5 h-3.5 text-gray-500 mr-1" />
    </button>

    <Teleport to="body">
        <Transition
            enter-active-class="transition ease-out duration-100"
            enter-from-class="transform opacity-0 scale-95"
            enter-to-class="transform opacity-100 scale-100"
            leave-active-class="transition ease-in duration-75"
            leave-from-class="transform opacity-100 scale-100"
            leave-to-class="transform opacity-0 scale-95"
        >
            <div 
                v-if="isMenuOpen"
                v-on-click-outside="closeMenu"
                class="fixed z-[60] top-14 right-4 w-64 rounded-xl border border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-800 overflow-hidden"
            >
                <div class="relative overflow-hidden min-h-[350px] flex flex-col">
                    <!-- User Header in Menu -->
                    <div class="p-4 border-b dark:border-gray-700 bg-gray-50/50 dark:bg-gray-900/30 flex items-center gap-3">
                         <UserAvatar :icon="user.icon" :username="user.username" size-class="h-10 w-10" />
                         <div class="min-w-0">
                            <p class="font-black text-sm text-gray-900 dark:text-white truncate">{{ user.username }}</p>
                            <p v-if="isAdmin" class="text-[9px] font-black uppercase text-red-500 tracking-widest">Administrator</p>
                            <p v-else class="text-[9px] font-black uppercase text-blue-500 tracking-widest">Explorer</p>
                         </div>
                    </div>

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
                                <IconUserCircle class="h-5 w-5 text-gray-400" />
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
                            
                            <router-link to="/about" @click="closeMenu" class="menu-item flex items-center gap-3">
                                <IconInfo class="h-5 w-5 text-gray-400" />
                                <span>About</span>
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
                            
                            <!-- Discussion Studio -->
                            <button @click="openDiscussionStudio" class="menu-item flex items-center gap-3" :class="{'bg-blue-50 dark:bg-blue-900/20': isDiscussionActive}">
                                <IconMessage class="h-5 w-5 text-indigo-500" />
                                <div class="flex flex-col text-left">
                                    <span class="font-bold">Discussion Studio</span>
                                    <span class="text-[10px] opacity-60">Chat & Generation</span>
                                </div>
                            </button>

                            <router-link to="/notebooks" @click="closeMenu" class="menu-item flex items-center gap-3" :class="{'bg-blue-50 dark:bg-blue-900/20': isNotebooksActive}">
                                <IconServer class="h-5 w-5 text-blue-500" />
                                <div class="flex flex-col">
                                    <span class="font-bold">Notebook Studio</span>
                                    <span class="text-[10px] opacity-60">Research & Writing</span>
                                </div>
                            </router-link>

                            <router-link v-if="isTtiConfigured" to="/image-studio" @click="closeMenu" class="menu-item flex items-center gap-3" :class="{'bg-blue-50 dark:bg-blue-900/20': isImageStudioActive}">
                                <IconPhoto class="h-5 w-5 text-purple-500" />
                                <div class="flex flex-col">
                                    <span class="font-bold">Image Studio</span>
                                    <span class="text-[10px] opacity-60">Visual Creation</span>
                                </div>
                            </router-link>

                            <router-link v-if="isTtsConfigured" to="/voices-studio" @click="closeMenu" class="menu-item flex items-center gap-3" :class="{'bg-blue-50 dark:bg-blue-900/20': isVoicesStudioActive}">
                                <IconMicrophone class="h-5 w-5 text-pink-500" />
                                <div class="flex flex-col">
                                    <span class="font-bold">Voices Studio</span>
                                    <span class="text-[10px] opacity-60">TTS & Voice Design</span>
                                </div>
                            </router-link>

                            <router-link to="/datastores" @click="closeMenu" class="menu-item flex items-center gap-3" :class="{'bg-blue-50 dark:bg-blue-900/20': isDataStoresActive}">
                                <IconDatabase class="h-5 w-5 text-green-500" />
                                <div class="flex flex-col">
                                    <span class="font-bold">Data Studio</span>
                                    <span class="text-[10px] opacity-60">RAG & Knowledge</span>
                                </div>
                            </router-link>

                            <router-link to="/flow-studio" @click="closeMenu" class="menu-item flex items-center gap-3" :class="{'bg-blue-50 dark:bg-blue-900/20': isFlowStudioActive}">
                                <IconShare class="h-5 w-5 text-cyan-500" />
                                <div class="flex flex-col">
                                    <span class="font-bold">Flow Studio</span>
                                    <span class="text-[10px] opacity-60">Workflows & Logic</span>
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
                            <div class="overflow-y-auto max-h-[300px]">
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
