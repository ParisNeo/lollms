<script setup>
import { computed, ref, provide, watch, nextTick, markRaw } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useFloating, offset, flip, shift, autoUpdate } from '@floating-ui/vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import { useSocialStore } from '../../stores/social';

import DropdownSubmenu from '../ui/DropDownMenu/DropdownSubmenu.vue';
import TasksManagerButton from './TasksManagerButton.vue';
import NotificationBell from '../ui/NotificationBell.vue';
import ThemeSelector from '../ui/ThemeSelector.vue';
import UserInfo from './UserInfo.vue';
import logoDefault from '../../assets/logo.png';

// Icons
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';
import IconUserCircle from '../../assets/icons/IconUserCircle.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconMicrophone from '../../assets/icons/IconMicrophone.vue';
import IconSpeakerWave from '../../assets/icons/IconSpeakerWave.vue';
import IconVideoCamera from '../../assets/icons/IconVideoCamera.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconMenu from '../../assets/icons/IconMenu.vue';
import IconDataZone from '../../assets/icons/IconDataZone.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconServer from '../../assets/icons/IconServer.vue';
import IconMessage from '../../assets/icons/IconMessage.vue'; 
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconChevronDown from '../../assets/icons/IconChevronDown.vue';

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const dataStore = useDataStore();
const socialStore = useSocialStore();
const route = useRoute();
const router = useRouter();

const user = computed(() => authStore.user);
const wsConnected = computed(() => authStore.wsConnected);
const isDataZoneVisible = computed(() => uiStore.isDataZoneVisible);
const pageTitle = computed(() => uiStore.pageTitle);
const pageTitleIcon = computed(() => uiStore.pageTitleIcon);
const unreadDmCount = computed(() => socialStore.totalUnreadDms);

const logoSrc = computed(() => authStore.welcome_logo_url || logoDefault);

const showMainSidebarToggle = computed(() => {
    if (!authStore.isAuthenticated) return false;
    const noSidebarPaths = ['/settings', '/admin', '/datastores', '/personality-studio', '/friends', '/help', '/profile', '/messages', '/voices-studio', '/image-studio', '/image-studio/edit'];
    return !noSidebarPaths.some(path => route.path.startsWith(path));
});

const showDataZoneButton = computed(() => {
    return !!discussionsStore.currentDiscussionId;
});

const isRefreshingModels = ref(false);
const menuTriggerRef = ref(null);
const menuFloatingRef = ref(null);
const isSubmenuActive = ref(false);
let closeTimer = null;

const { floatingStyles } = useFloating(menuTriggerRef, menuFloatingRef, {
  placement: 'bottom-start',
  whileElementsMounted: autoUpdate,
  middleware: [offset(5), flip(), shift({ padding: 5 })],
});

function setSubmenuActive(status) {
    isSubmenuActive.value = status;
}
function cancelClose() {
    clearTimeout(closeTimer);
}
provide('dropdown-context', {
  setSubmenuActive,
  cancelClose
});

const vOnClickOutside = {
  mounted: (el, binding) => {
    el.clickOutsideEvent = event => {
      const triggerEl = menuTriggerRef.value;
      const targetIsSubmenuPanel = event.target.closest('.is-submenu-panel');
      if (!(el === event.target || el.contains(event.target) || triggerEl?.contains(event.target) || targetIsSubmenuPanel)) {
        binding.value();
      }
    };
    document.addEventListener('mousedown', el.clickOutsideEvent);
  },
  unmounted: el => {
    document.removeEventListener('mousedown', el.clickOutsideEvent);
  },
};

// Model selection state
// Model selection state
const modelSearchTerm = ref('');
const personalitySearchTerm = ref('');
const ttiModelSearchTerm = ref('');
const ttsModelSearchTerm = ref('');
const sttModelSearchTerm = ref('');
const ttvModelSearchTerm = ref('');
const ttmModelSearchTerm = ref('');

const isMenuOpen = ref(false);

// Active Selections
const activePersonalityId = computed({ get: () => user.value?.active_personality_id, set: (id) => authStore.updateUserPreferences({ active_personality_id: id }) });
const activeModelName = computed({ get: () => user.value?.lollms_model_name, set: (name) => authStore.updateUserPreferences({ lollms_model_name: name }) });
const activeTtiModelName = computed({ get: () => user.value?.tti_binding_model_name, set: (name) => authStore.updateUserPreferences({ tti_binding_model_name: name }) });
const activeTtsModelName = computed({ get: () => user.value?.tts_binding_model_name, set: (name) => authStore.updateUserPreferences({ tts_binding_model_name: name }) });
const activeSttModelName = computed({ get: () => user.value?.stt_binding_model_name, set: (name) => authStore.updateUserPreferences({ stt_binding_model_name: name }) });
const activeTtvModelName = computed({ get: () => user.value?.ttv_binding_model_name, set: (name) => authStore.updateUserPreferences({ ttv_binding_model_name: name }) });
const activeTtmModelName = computed({ get: () => user.value?.ttm_binding_model_name, set: (name) => authStore.updateUserPreferences({ ttm_binding_model_name: name }) });

// Available Data
const availablePersonalities = computed(() => [{ isGroup: true, label: 'Personal', items: dataStore.userPersonalities }, { isGroup: true, label: 'Public', items: dataStore.publicPersonalities }]);
const formattedAvailableModels = computed(() => dataStore.availableLLMModelsGrouped);
const formattedAvailableTtiModels = computed(() => dataStore.availableTtiModelsGrouped);
const formattedAvailableTtsModels = computed(() => dataStore.availableTtsModelsGrouped);
const formattedAvailableSttModels = computed(() => dataStore.availableSttModelsGrouped);
const formattedAvailableTtvModels = computed(() => dataStore.availableTtvModelsGrouped || []);
const formattedAvailableTtmModels = computed(() => dataStore.availableTtmModelsGrouped || []);

// Selected Items
const selectedModel = computed(() => formattedAvailableModels.value.flatMap(g => g.items).find(m => m.id === activeModelName.value));
const selectedPersonality = computed(() => availablePersonalities.value.flatMap(g => g.items).find(p => p.id === activePersonalityId.value));

// Filtering Logic
const filteredAvailableModels = computed(() => modelSearchTerm.value ? formattedAvailableModels.value.map(g => ({...g, items: g.items.filter(i => i.name.toLowerCase().includes(modelSearchTerm.value.toLowerCase()))})).filter(g => g.items.length > 0) : formattedAvailableModels.value);
const filteredAvailableTtiModels = computed(() => ttiModelSearchTerm.value ? formattedAvailableTtiModels.value.map(g => ({...g, items: g.items.filter(i => i.name.toLowerCase().includes(ttiModelSearchTerm.value.toLowerCase()))})).filter(g => g.items.length > 0) : formattedAvailableTtiModels.value);
const filteredAvailableTtsModels = computed(() => ttsModelSearchTerm.value ? formattedAvailableTtsModels.value.map(g => ({...g, items: g.items.filter(i => i.name.toLowerCase().includes(ttsModelSearchTerm.value.toLowerCase()))})).filter(g => g.items.length > 0) : formattedAvailableTtsModels.value);
const filteredAvailableSttModels = computed(() => sttModelSearchTerm.value ? formattedAvailableSttModels.value.map(g => ({...g, items: g.items.filter(i => i.name.toLowerCase().includes(sttModelSearchTerm.value.toLowerCase()))})).filter(g => g.items.length > 0) : formattedAvailableSttModels.value);
const filteredAvailableTtvModels = computed(() => ttvModelSearchTerm.value ? formattedAvailableTtvModels.value.map(g => ({...g, items: g.items.filter(i => i.name.toLowerCase().includes(ttvModelSearchTerm.value.toLowerCase()))})).filter(g => g.items.length > 0) : formattedAvailableTtvModels.value);
const filteredAvailableTtmModels = computed(() => ttmModelSearchTerm.value ? formattedAvailableTtmModels.value.map(g => ({...g, items: g.items.filter(i => i.name.toLowerCase().includes(ttmModelSearchTerm.value.toLowerCase()))})).filter(g => g.items.length > 0) : formattedAvailableTtmModels.value);
const filteredAvailablePersonalities = computed(() => personalitySearchTerm.value ? availablePersonalities.value.map(g => ({...g, items: g.items.filter(i => i.name.toLowerCase().includes(personalitySearchTerm.value.toLowerCase()))})).filter(g => g.items.length > 0) : availablePersonalities.value);

function selectModel(id) { activeModelName.value = id; }
function selectPersonality(id) { activePersonalityId.value = id; }
function selectTtiModel(id) { activeTtiModelName.value = id; }
function selectTtsModel(id) { activeTtsModelName.value = id; }
function selectSttModel(id) { activeSttModelName.value = id; }
function selectTtvModel(id) { activeTtvModelName.value = id; }
function selectTtmModel(id) { activeTtmModelName.value = id; }

async function handleRefreshModels() {
    isRefreshingModels.value = true;
    try {
        await dataStore.refreshAllModels();
        uiStore.addNotification('Model lists refreshed.', 'success');
    } finally {
        isRefreshingModels.value = false;
    }
}
</script>

<template>
  <header class="shrink-0 bg-bg-card border-b border-border-main h-14 flex items-center justify-between px-3 sm:px-4 z-[50] relative shadow-sm transition-colors duration-500">
    
    <!-- Left: Logo & Sidebar Toggle & Model Selector -->
    <div class="flex items-center gap-2 sm:gap-4 min-w-0">
        <!-- Logo / Home Link -->
        <router-link to="/" class="flex items-center gap-2 shrink-0 group">
             <img :src="logoSrc" alt="LoLLMs Logo" class="h-8 w-8 shrink-0 object-contain rounded-md transition-transform group-hover:scale-110" @error="($event.target.src=logoDefault)">
             <span class="hidden md:inline font-black text-lg tracking-tighter text-primary">LoLLMs</span>
        </router-link>

        <!-- Sidebar Toggle -->
        <button v-if="showMainSidebarToggle" @click="uiStore.toggleSidebar" 
                class="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                title="Toggle Sidebar">
            <IconMenu class="w-5 h-5" />
        </button>

        <div class="h-6 w-px bg-gray-200 dark:border-gray-700 hidden sm:block"></div>

        <!-- Compact Model Selector -->
        <div class="relative" v-if="user && user.user_ui_level >= 2">
            <button ref="menuTriggerRef" @click="isMenuOpen = !isMenuOpen" 
                class="flex items-center gap-2 px-1.5 py-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors group border border-transparent hover:border-gray-200 dark:hover:border-gray-600">
                <!-- Personality Avatar -->
                <div class="w-8 h-8 rounded-full overflow-hidden bg-gray-200 dark:bg-gray-700 shrink-0 border border-gray-300 dark:border-gray-600 shadow-sm relative">
                     <img v-if="selectedPersonality?.icon_base64" :src="selectedPersonality.icon_base64" class="w-full h-full object-cover" />
                     <IconUserCircle v-else class="w-full h-full p-1 text-gray-500" />
                     <div class="absolute bottom-0 right-0 bg-white dark:bg-gray-800 rounded-full p-0.5 border border-gray-300 dark:border-gray-600">
                         <IconCpuChip class="w-2.5 h-2.5 text-primary" />
                     </div>
                </div>
                
                <div class="hidden lg:flex flex-col items-start text-xs leading-tight">
                    <span class="font-bold text-gray-800 dark:text-gray-100 max-w-[140px] truncate" :title="selectedModel?.name || 'No Model'">{{ selectedModel?.name || 'Select Model' }}</span>
                    <span class="text-gray-500 dark:text-gray-400 max-w-[140px] truncate text-[10px]" :title="selectedPersonality?.name">{{ selectedPersonality?.name || 'Default' }}</span>
                </div>
                
                <IconChevronDown class="w-3 h-3 text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300 ml-1" />
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
                        ref="menuFloatingRef" 
                        :style="floatingStyles" 
                        v-on-click-outside="() => { isMenuOpen = false; isSubmenuActive = false; }"
                        class="z-[60] w-72 origin-top-left rounded-lg bg-white dark:bg-gray-800 shadow-xl ring-1 ring-black ring-opacity-5 dark:ring-gray-700 focus:outline-none py-1 flex flex-col max-h-[85vh] border dark:border-gray-700"
                    >
                         <button @click="handleRefreshModels" class="menu-item flex items-center gap-3 border-b dark:border-gray-700 mb-1 py-3 px-4 hover:bg-gray-50 dark:hover:bg-gray-700" :disabled="isRefreshingModels">
                            <IconRefresh class="h-4 w-4 text-primary" :class="{'animate-spin': isRefreshingModels}" />
                            <span class="font-bold text-xs uppercase tracking-wider text-gray-600 dark:text-gray-300">Refresh Models</span>
                         </button>

                         <DropdownSubmenu title="LLM Model" icon="cpu-chip">
                            <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10 border-b dark:border-gray-700"><input type="text" v-model="modelSearchTerm" @click.stop placeholder="Search models..." class="input-field-sm w-full"></div>
                            <div class="p-1 grow overflow-y-auto max-h-96">
                                <button @click="selectModel(null)" class="menu-item-button" :class="{'selected': !activeModelName}"><span class="truncate">None</span></button>
                                <div v-for="group in filteredAvailableModels" :key="group.label">
                                    <h4 class="px-2 py-1.5 text-xs font-bold text-gray-500">{{ group.label }}</h4>
                                    <div v-for="item in group.items" :key="item.id" class="flex items-center group/model">
                                        <button @click="selectModel(item.id)" class="menu-item-button grow !justify-between" :class="{'selected': activeModelName === item.id}">
                                            <span class="truncate pr-2">{{ item.name }}</span>
                                            <div class="flex items-center gap-1.5 shrink-0">
                                                <IconEye v-if="item.alias?.has_vision" class="w-3.5 h-3.5 text-green-500" title="Vision Support" />
                                            </div>
                                        </button>
                                    </div>
                                </div>
                            </div>
                         </DropdownSubmenu>

                         <DropdownSubmenu v-if="formattedAvailableTtiModels.length > 0" title="TTI Model" icon="photo">
                            <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10 border-b dark:border-gray-700"><input type="text" v-model="ttiModelSearchTerm" @click.stop placeholder="Search TTI models..." class="input-field-sm w-full"></div>
                            <div class="p-1 grow overflow-y-auto max-h-96">
                                <button @click="selectTtiModel(null)" class="menu-item-button" :class="{'selected': !activeTtiModelName}"><span class="truncate">None</span></button>
                                <div v-for="group in filteredAvailableTtiModels" :key="group.label">
                                    <h4 class="px-2 py-1.5 text-xs font-bold text-gray-500">{{ group.label }}</h4>
                                    <div v-for="item in group.items" :key="item.id" class="flex items-center group/model">
                                        <button @click="selectTtiModel(item.id)" class="menu-item-button grow !justify-between" :class="{'selected': activeTtiModelName === item.id}">
                                            <span class="truncate pr-2">{{ item.name }}</span>
                                        </button>
                                    </div>
                                </div>
                            </div>
                         </DropdownSubmenu>

                         <DropdownSubmenu v-if="formattedAvailableTtsModels.length > 0" title="TTS Model" icon="speaker-wave">
                            <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10 border-b dark:border-gray-700"><input type="text" v-model="ttsModelSearchTerm" @click.stop placeholder="Search TTS models..." class="input-field-sm w-full"></div>
                            <div class="p-1 grow overflow-y-auto max-h-96">
                                <button @click="selectTtsModel(null)" class="menu-item-button" :class="{'selected': !activeTtsModelName}"><span class="truncate">None</span></button>
                                <div v-for="group in filteredAvailableTtsModels" :key="group.label">
                                    <h4 class="px-2 py-1.5 text-xs font-bold text-gray-500">{{ group.label }}</h4>
                                    <div v-for="item in group.items" :key="item.id" class="flex items-center group/model">
                                        <button @click="selectTtsModel(item.id)" class="menu-item-button grow !justify-between" :class="{'selected': activeTtsModelName === item.id}">
                                            <span class="truncate pr-2">{{ item.name }}</span>
                                        </button>
                                    </div>
                                </div>
                            </div>
                         </DropdownSubmenu>

                         <DropdownSubmenu v-if="formattedAvailableSttModels.length > 0" title="STT Model" icon="microphone">
                            <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10 border-b dark:border-gray-700"><input type="text" v-model="sttModelSearchTerm" @click.stop placeholder="Search STT models..." class="input-field-sm w-full"></div>
                            <div class="p-1 grow overflow-y-auto max-h-96">
                                <button @click="selectSttModel(null)" class="menu-item-button" :class="{'selected': !activeSttModelName}"><span class="truncate">None</span></button>
                                <div v-for="group in filteredAvailableSttModels" :key="group.label">
                                    <h4 class="px-2 py-1.5 text-xs font-bold text-gray-500">{{ group.label }}</h4>
                                    <div v-for="item in group.items" :key="item.id" class="flex items-center group/model">
                                        <button @click="selectSttModel(item.id)" class="menu-item-button grow !justify-between" :class="{'selected': activeSttModelName === item.id}">
                                            <span class="truncate pr-2">{{ item.name }}</span>
                                        </button>
                                    </div>
                                </div>
                            </div>
                         </DropdownSubmenu>

                         <DropdownSubmenu v-if="formattedAvailableTtmModels.length > 0" title="TTM Model" icon="speaker-wave">
                            <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10 border-b dark:border-gray-700"><input type="text" v-model="ttmModelSearchTerm" @click.stop placeholder="Search TTM models..." class="input-field-sm w-full"></div>
                            <div class="p-1 grow overflow-y-auto max-h-96">
                                <button @click="selectTtmModel(null)" class="menu-item-button" :class="{'selected': !activeTtmModelName}"><span class="truncate">None</span></button>
                                <div v-for="group in filteredAvailableTtmModels" :key="group.label">
                                    <h4 class="px-2 py-1.5 text-xs font-bold text-gray-500">{{ group.label }}</h4>
                                    <div v-for="item in group.items" :key="item.id" class="flex items-center group/model">
                                        <button @click="selectTtmModel(item.id)" class="menu-item-button grow !justify-between" :class="{'selected': activeTtmModelName === item.id}">
                                            <span class="truncate pr-2">{{ item.name }}</span>
                                        </button>
                                    </div>
                                </div>
                            </div>
                         </DropdownSubmenu>

                         <DropdownSubmenu v-if="formattedAvailableTtvModels.length > 0" title="TTV Model" icon="video-camera">
                            <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10 border-b dark:border-gray-700"><input type="text" v-model="ttvModelSearchTerm" @click.stop placeholder="Search TTV models..." class="input-field-sm w-full"></div>
                            <div class="p-1 grow overflow-y-auto max-h-96">
                                <button @click="selectTtvModel(null)" class="menu-item-button" :class="{'selected': !activeTtvModelName}"><span class="truncate">None</span></button>
                                <div v-for="group in filteredAvailableTtvModels" :key="group.label">
                                    <h4 class="px-2 py-1.5 text-xs font-bold text-gray-500">{{ group.label }}</h4>
                                    <div v-for="item in group.items" :key="item.id" class="flex items-center group/model">
                                        <button @click="selectTtvModel(item.id)" class="menu-item-button grow !justify-between" :class="{'selected': activeTtvModelName === item.id}">
                                            <span class="truncate pr-2">{{ item.name }}</span>
                                        </button>
                                    </div>
                                </div>
                            </div>
                         </DropdownSubmenu>

                         <DropdownSubmenu title="Personality" icon="user-circle">
                            <div class="flex flex-col sticky top-0 bg-white dark:bg-gray-800 z-10 border-b dark:border-gray-700">
                                <router-link to="/personality-studio" @click="closeMenu" class="flex items-center gap-3 py-2.5 px-4 hover:bg-orange-50 dark:hover:bg-orange-900/20 text-orange-600 transition-colors border-b dark:border-gray-700">
                                    <IconPencil class="w-4 h-4" />
                                    <span class="text-xs font-bold uppercase tracking-wider">Personality Studio</span>
                                </router-link>
                                <div class="p-2">
                                    <input type="text" v-model="personalitySearchTerm" @click.stop placeholder="Search..." class="input-field-sm w-full">
                                </div>
                            </div>
                            <div class="p-1 grow overflow-y-auto max-h-96">
                                <div v-for="group in filteredAvailablePersonalities" :key="group.label">
                                     <h4 class="px-2 py-1.5 text-xs font-bold text-gray-500">{{ group.label }}</h4>
                                     <div v-for="item in group.items" :key="item.id" class="relative group/p">
                                        <button @click="selectPersonality(item.id)" class="menu-item-button w-full" :class="{'selected': activePersonalityId === item.id}">
                                            <div class="flex items-center gap-2 truncate">
                                                <img v-if="item.icon_base64" :src="item.icon_base64" class="h-5 w-5 rounded object-cover" />
                                                <IconUserCircle v-else class="h-5 w-5 text-gray-400" />
                                                <span class="truncate">{{ item.name }}</span>
                                            </div>
                                        </button>
                                    </div>
                                </div>
                            </div>
                         </DropdownSubmenu>
                     </div>
                </Transition>
             </Teleport>
        </div>
    </div>

    <!-- Center: Dynamic Portal -->
    <div class="flex-1 flex justify-center min-w-0 px-2 lg:px-6 h-full relative">
        <div id="global-header-title-target" class="w-full flex justify-center items-center h-full pointer-events-auto z-20"></div>
        <div v-if="pageTitle" class="absolute pointer-events-none flex items-center gap-2 text-gray-600 dark:text-gray-300 font-semibold truncate">
            <component v-if="pageTitleIcon" :is="pageTitleIcon" class="w-5 h-5 opacity-70" />
            <span>{{ pageTitle }}</span>
        </div>
    </div>

    <!-- Right: Vibe Selector & Tools -->
    <div class="flex items-center gap-1 sm:gap-2 shrink-0">
        <div id="global-header-actions-target" class="flex items-center gap-1 mr-1 sm:mr-3"></div>
        
        <div class="h-6 w-px bg-gray-200 dark:border-gray-700 mx-1 hidden sm:block"></div>

        <TasksManagerButton />
        
        <NotificationBell v-if="user && user.user_ui_level >= 2" />
        
        <!-- NEW THEME AND VIBE SELECTOR -->
        <ThemeSelector />
        
        <button v-if="showDataZoneButton" @click="uiStore.toggleDataZone()" 
            class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors relative" 
            :class="{'text-primary bg-blue-50 dark:bg-blue-900/20': isDataZoneVisible, 'text-gray-500': !isDataZoneVisible}"
            title="Context Explorer"
        >
            <IconDataZone class="w-5 h-5" />
        </button>
        
        <button v-if="user && user.chat_active" @click="uiStore.toggleChatSidebar()" class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 relative transition-colors">
            <IconMessage class="w-5 h-5" />
            <span v-if="unreadDmCount > 0" class="absolute top-1.5 right-1.5 w-2.5 h-2.5 bg-red-500 rounded-full ring-2 ring-white dark:ring-gray-800"></span>
        </button>

        <UserInfo />
    </div>
  </header>
</template>

<style scoped>
@reference "tailwindcss";
@reference "../../assets/css/main.css";
.menu-item { @apply w-full text-left px-4 py-2.5 text-sm transition-colors hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer flex items-center; }
.menu-item-button { @apply w-full text-left p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center justify-between gap-2 text-sm text-gray-700 dark:text-gray-200; }
.menu-item-button.selected { @apply bg-blue-50 dark:bg-blue-900/30 text-primary font-medium; }
</style>
