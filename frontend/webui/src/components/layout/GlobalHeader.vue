<script setup>
import { computed, ref, provide, watch, nextTick, markRaw } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useFloating, offset, flip, shift, autoUpdate } from '@floating-ui/vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import { useSocialStore } from '../../stores/social';

import DropdownSubmenu from '../ui/DropdownMenu/DropdownSubmenu.vue';
import TasksManagerButton from './TasksManagerButton.vue';
import NotificationBell from '../ui/NotificationBell.vue';
import ThemeToggle from '../ui/ThemeToggle.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';
import IconUserCircle from '../../assets/icons/IconUserCircle.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconMicrophone from '../../assets/icons/IconMicrophone.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconMenu from '../../assets/icons/IconMenu.vue';
import IconDataZone from '../../assets/icons/IconDataZone.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconServer from '../../assets/icons/IconServer.vue';
import IconMessage from '../../assets/icons/IconMessage.vue'; 

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
const mainView = computed(() => uiStore.mainView);
const unreadDmCount = computed(() => socialStore.totalUnreadDms);

const showDataZoneButton = computed(() => {
    return route.name === 'Home' && mainView.value === 'chat';
});

const isMenuOpen = ref(false);
const menuTriggerRef = ref(null);
const menuFloatingRef = ref(null);
const isSubmenuActive = ref(false);
let closeTimer = null;

const { floatingStyles } = useFloating(menuTriggerRef, menuFloatingRef, {
  placement: 'bottom',
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
const modelSearchTerm = ref('');
const personalitySearchTerm = ref('');
const ttiModelSearchTerm = ref('');
const ttsModelSearchTerm = ref('');
const sttModelSearchTerm = ref('');

// Active Selections
const activePersonalityId = computed({ get: () => user.value?.active_personality_id, set: (id) => authStore.updateUserPreferences({ active_personality_id: id }) });
const activeModelName = computed({ get: () => user.value?.lollms_model_name, set: (name) => authStore.updateUserPreferences({ lollms_model_name: name }) });
const activeTtiModelName = computed({ get: () => user.value?.tti_binding_model_name, set: (name) => authStore.updateUserPreferences({ tti_binding_model_name: name }) });
const activeItiModelName = computed({ get: () => user.value?.iti_binding_model_name, set: (name) => authStore.updateUserPreferences({ iti_binding_model_name: name }) });
const activeTtsModelName = computed({ get: () => user.value?.tts_binding_model_name, set: (name) => authStore.updateUserPreferences({ tts_binding_model_name: name }) });
const activeSttModelName = computed({ get: () => user.value?.stt_binding_model_name, set: (name) => authStore.updateUserPreferences({ stt_binding_model_name: name }) });

// Available Data
const availablePersonalities = computed(() => [{ isGroup: true, label: 'Personal', items: dataStore.userPersonalities }, { isGroup: true, label: 'Public', items: dataStore.publicPersonalities }]);
const formattedAvailableModels = computed(() => dataStore.availableLLMModelsGrouped);
const formattedAvailableTtiModels = computed(() => dataStore.availableTtiModelsGrouped);
const formattedAvailableTtsModels = computed(() => dataStore.availableTtsModelsGrouped);
const formattedAvailableSttModels = computed(() => dataStore.availableSttModelsGrouped);

// Selected Items
const selectedModel = computed(() => formattedAvailableModels.value.flatMap(g => g.items).find(m => m.id === activeModelName.value));
const selectedPersonality = computed(() => availablePersonalities.value.flatMap(g => g.items).find(p => p.id === activePersonalityId.value));
const selectedTtiModel = computed(() => formattedAvailableTtiModels.value.flatMap(g => g.items).find(m => m.id === activeTtiModelName.value));
const selectedItiModel = computed(() => formattedAvailableTtiModels.value.flatMap(g => g.items).find(m => m.id === activeItiModelName.value));
const selectedTtsModel = computed(() => formattedAvailableTtsModels.value.flatMap(g => g.items).find(m => m.id === activeTtsModelName.value));
const selectedSttModel = computed(() => formattedAvailableSttModels.value.flatMap(g => g.items).find(m => m.id === activeSttModelName.value));

// Filtering Logic
const filteredAvailableModels = computed(() => modelSearchTerm.value ? formattedAvailableModels.value.map(g => ({...g, items: g.items.filter(i => i.name.toLowerCase().includes(modelSearchTerm.value.toLowerCase()))})).filter(g => g.items.length > 0) : formattedAvailableModels.value);
const filteredAvailableTtiModels = computed(() => ttiModelSearchTerm.value ? formattedAvailableTtiModels.value.map(g => ({...g, items: g.items.filter(i => i.name.toLowerCase().includes(ttiModelSearchTerm.value.toLowerCase()))})).filter(g => g.items.length > 0) : formattedAvailableTtiModels.value);
const filteredAvailableTtsModels = computed(() => ttsModelSearchTerm.value ? formattedAvailableTtsModels.value.map(g => ({...g, items: g.items.filter(i => i.name.toLowerCase().includes(ttsModelSearchTerm.value.toLowerCase()))})).filter(g => g.items.length > 0) : formattedAvailableTtsModels.value);
const filteredAvailableSttModels = computed(() => sttModelSearchTerm.value ? formattedAvailableSttModels.value.map(g => ({...g, items: g.items.filter(i => i.name.toLowerCase().includes(sttModelSearchTerm.value.toLowerCase()))})).filter(g => g.items.length > 0) : formattedAvailableSttModels.value);
const filteredAvailablePersonalities = computed(() => personalitySearchTerm.value ? availablePersonalities.value.map(g => ({...g, items: g.items.filter(i => i.name.toLowerCase().includes(personalitySearchTerm.value.toLowerCase()))})).filter(g => g.items.length > 0) : availablePersonalities.value);


function openModelCard(model) { uiStore.openModal('modelCard', { model }); }
function selectModel(id) { activeModelName.value = id; }
function selectPersonality(id) { activePersonalityId.value = id; }
function selectTtiModel(id) { activeTtiModelName.value = id; }
function selectItiModel(id) { activeItiModelName.value = id; }
function selectTtsModel(id) { activeTtsModelName.value = id; }
function selectSttModel(id) { activeSttModelName.value = id; }
function handleEditPersonality(personality, event) {
    event.stopPropagation();
    isMenuOpen.value = false;
    router.push({ path: '/settings', query: { tab: 'personalities' } });
    nextTick(() => { uiStore.openModal('personalityEditor', { personality: personality, isSystemPersonality: false }); });
}

</script>

<template>
  <header class="flex-shrink-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-2 sm:p-3 flex items-center justify-between shadow-sm z-10">
    <!-- Left Section: Logo/Title/Model Selector -->
    <div v-if="route.name === 'Home' && user && user.user_ui_level >= 2" class="hidden md:flex items-center gap-2 flex-1 min-w-0 justify-center px-4">
         <div class="relative">
            <button ref="menuTriggerRef" @click="isMenuOpen = !isMenuOpen" class="toolbox-select flex items-center gap-2 max-w-sm !p-1">
                 <div class="flex items-center flex-shrink-0">
                      <!-- LLM Icon -->
                      <div class="w-7 h-7 flex-shrink-0 text-gray-500 dark:text-gray-400 flex items-center justify-center bg-gray-200 dark:bg-gray-700 rounded-md">
                          <img v-if="selectedModel?.alias?.icon" :src="selectedModel.alias.icon" class="h-full w-full rounded-md object-cover"/>
                          <IconCpuChip v-else class="w-4 h-4" />
                      </div>
                      <!-- TTI Icon -->
                      <div v-if="!user.tti_model_forced" class="w-7 h-7 flex-shrink-0 text-gray-500 dark:text-gray-400 flex items-center justify-center bg-gray-200 dark:bg-gray-700 rounded-md -ml-3 z-10 border-2 border-white dark:border-gray-800">
                           <img v-if="selectedTtiModel?.alias?.icon" :src="selectedTtiModel.alias.icon" class="h-full w-full rounded-md object-cover"/>
                           <IconPhoto v-else class="w-4 h-4" />
                      </div>
                      <!-- ITI Icon -->
                      <div v-if="!user.iti_model_forced" class="w-7 h-7 flex-shrink-0 text-gray-500 dark:text-gray-400 flex items-center justify-center bg-gray-200 dark:bg-gray-700 rounded-md -ml-3 z-10 border-2 border-white dark:border-gray-800">
                           <img v-if="selectedItiModel?.alias?.icon" :src="selectedItiModel.alias.icon" class="h-full w-full rounded-md object-cover"/>
                           <IconPencil v-else class="w-4 h-4" />
                      </div>
                       <!-- TTS Icon -->
                      <div class="w-7 h-7 flex-shrink-0 text-gray-500 dark:text-gray-400 flex items-center justify-center bg-gray-200 dark:bg-gray-700 rounded-md -ml-3 z-10 border-2 border-white dark:border-gray-800">
                           <img v-if="selectedTtsModel?.alias?.icon" :src="selectedTtsModel.alias.icon" class="h-full w-full rounded-md object-cover"/>
                           <IconMicrophone v-else class="w-4 h-4" />
                      </div>
                      <!-- STT Icon -->
                      <div class="w-7 h-7 flex-shrink-0 text-gray-500 dark:text-gray-400 flex items-center justify-center bg-gray-200 dark:bg-gray-700 rounded-md -ml-3 z-10 border-2 border-white dark:border-gray-800">
                           <img v-if="selectedSttModel?.alias?.icon" :src="selectedSttModel.alias.icon" class="h-full w-full rounded-md object-cover"/>
                           <IconMicrophone v-else class="w-4 h-4" />
                      </div>
                       <!-- Personality Icon -->
                        <div class="w-7 h-7 flex-shrink-0 text-gray-500 dark:text-gray-400 flex items-center justify-center bg-gray-200 dark:bg-gray-700 rounded-md -ml-3 z-20 border-2 border-white dark:border-gray-800">
                            <img v-if="selectedPersonality?.icon_base64" :src="selectedPersonality.icon_base64" class="h-full w-full rounded-md object-cover"/>
                            <IconUserCircle v-else class="w-4 h-4" />
                        </div>
                 </div>
                 <div class="min-w-0 text-left flex-grow">
                      <span class="block font-semibold truncate text-xs" :title="selectedModel?.name || 'Select Model'">{{ selectedModel?.name || 'Select Model' }}</span>
                      <span class="block text-xs text-gray-500/80 truncate" :title="selectedPersonality?.name || 'Select Personality'">{{ selectedPersonality?.name || 'Select Personality' }}</span>
                 </div>
                 <svg class="w-4 h-4 text-gray-400 flex-shrink-0 ml-auto" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
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
                        class="z-50 w-64 origin-top-left rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 dark:ring-gray-700 focus:outline-none py-1 flex flex-col max-h-[80vh]"
                    >
                         <DropdownSubmenu title="LLM Model" icon="cpu-chip" :icon-src="selectedModel?.alias?.icon">
                             <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10 border-b dark:border-gray-700">
                                <input type="text" v-model="modelSearchTerm" @click.stop placeholder="Search models..." class="input-field-sm w-full">
                            </div>
                            <div class="p-1 flex-grow overflow-y-auto max-h-96">
                                 <button @click="selectModel(null)" class="menu-item-button" :class="{'selected': !activeModelName}">
                                    <div class="flex items-center space-x-3 truncate">
                                        <IconCpuChip class="w-6 h-6 p-0.5 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                                        <div class="truncate text-left"><p class="font-medium truncate text-sm">None</p></div>
                                    </div>
                                </button>
                                <div v-if="filteredAvailableModels.length > 0" class="my-1 border-t dark:border-gray-600"></div>
                                <div v-for="group in filteredAvailableModels" :key="group.label">
                                    <h4 class="px-2 py-1.5 text-xs font-bold text-gray-600 dark:text-gray-300">{{ group.label }}</h4>
                                    <button v-for="item in group.items" :key="item.id" @click="selectModel(item.id)" class="menu-item-button group/item" :class="{'selected': activeModelName === item.id}">
                                         <div class="flex items-center space-x-3 truncate flex-1 min-w-0">
                                            <img v-if="item.alias?.icon" :src="item.alias.icon" class="h-6 w-6 rounded-md object-cover flex-shrink-0" />
                                            <IconCpuChip v-else class="w-6 h-6 p-0.5 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                                            <div class="truncate text-left flex-1 min-w-0">
                                                <p class="font-medium truncate text-sm">{{ item.name }}</p>
                                            </div>
                                        </div>
                                        <div class="flex items-center gap-1 pl-2 flex-shrink-0">
                                            <IconEye v-if="item.alias?.has_vision" class="w-4 h-4 text-blue-500" title="Vision Supported" />
                                            <div class="opacity-0 group-hover/item:opacity-100 focus-within:opacity-100 transition-opacity w-6 h-6 flex items-center justify-center">
                                                <div @click.stop="openModelCard(item)" class="p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-full cursor-pointer" title="Model Information">
                                                    <IconInfo class="w-4 h-4 text-gray-500 dark:text-gray-400" />
                                                </div>
                                            </div>
                                        </div>
                                    </button>
                                </div>
                            </div>
                         </DropdownSubmenu>
                         <DropdownSubmenu v-if="!user.tti_model_forced" title="Text-to-Image" icon="photo" :icon-src="selectedTtiModel?.alias?.icon">
                             <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10 border-b dark:border-gray-700">
                                <input type="text" v-model="ttiModelSearchTerm" @click.stop placeholder="Search TTI models..." class="input-field-sm w-full">
                            </div>
                            <div class="p-1 flex-grow overflow-y-auto max-h-96">
                                <button @click="selectTtiModel(null)" class="menu-item-button" :class="{'selected': !activeTtiModelName}">
                                    <div class="flex items-center space-x-3 truncate">
                                        <IconPhoto class="w-6 h-6 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                                        <div class="truncate text-left"><p class="font-medium truncate text-sm">None</p></div>
                                    </div>
                                </button>
                                <div v-if="filteredAvailableTtiModels.length > 0" class="my-1 border-t dark:border-gray-600"></div>
                                <div v-for="group in filteredAvailableTtiModels" :key="group.label">
                                     <h4 class="px-2 py-1.5 text-xs font-bold text-gray-600 dark:text-gray-300">{{ group.label }}</h4>
                                     <button v-for="item in group.items" :key="item.id" @click="selectTtiModel(item.id)" class="menu-item-button" :class="{'selected': activeTtiModelName === item.id}">
                                         <div class="flex items-center space-x-3 truncate">
                                            <img v-if="item.alias?.icon" :src="item.alias.icon" class="h-6 w-6 rounded-md object-cover flex-shrink-0" />
                                            <IconPhoto v-else class="w-6 h-6 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                                            <div class="truncate text-left"><p class="font-medium truncate text-sm">{{ item.name }}</p></div>
                                        </div>
                                    </button>
                                </div>
                            </div>
                         </DropdownSubmenu>
                         <DropdownSubmenu v-if="!user.iti_model_forced" title="Image Editing" icon="pencil" :icon-src="selectedItiModel?.alias?.icon">
                             <div class="p-1 flex-grow overflow-y-auto max-h-96">
                                <button @click="selectItiModel(null)" class="menu-item-button" :class="{'selected': !activeItiModelName}">
                                    <div class="flex items-center space-x-3 truncate">
                                        <IconPencil class="w-6 h-6 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                                        <div class="truncate text-left"><p class="font-medium truncate text-sm">None</p></div>
                                    </div>
                                </button>
                                <div v-if="filteredAvailableTtiModels.length > 0" class="my-1 border-t dark:border-gray-600"></div>
                                <div v-for="group in filteredAvailableTtiModels" :key="group.label">
                                    <h4 class="px-2 py-1.5 text-xs font-bold text-gray-600 dark:text-gray-300">{{ group.label }}</h4>
                                    <button v-for="item in group.items" :key="item.id" @click="selectItiModel(item.id)" class="menu-item-button" :class="{'selected': activeItiModelName === item.id}">
                                        <div class="flex items-center space-x-3 truncate">
                                            <img v-if="item.alias?.icon" :src="item.alias.icon" class="h-6 w-6 rounded-md object-cover flex-shrink-0" />
                                            <IconPencil v-else class="w-6 h-6 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                                            <div class="truncate text-left"><p class="font-medium truncate text-sm">{{ item.name }}</p></div>
                                        </div>
                                    </button>
                                </div>
                             </div>
                         </DropdownSubmenu>

                         <DropdownSubmenu title="Text-to-Speech" icon="microphone" :icon-src="selectedTtsModel?.alias?.icon">
                            <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10 border-b dark:border-gray-700">
                                <input type="text" v-model="ttsModelSearchTerm" @click.stop placeholder="Search TTS models..." class="input-field-sm w-full">
                            </div>
                            <div class="p-1 flex-grow overflow-y-auto max-h-96">
                                <button @click="selectTtsModel(null)" class="menu-item-button" :class="{'selected': !activeTtsModelName}">
                                    <div class="flex items-center space-x-3 truncate">
                                        <IconMicrophone class="w-6 h-6 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                                        <div class="truncate text-left"><p class="font-medium truncate text-sm">None</p></div>
                                    </div>
                                </button>
                                <div v-if="filteredAvailableTtsModels.length > 0" class="my-1 border-t dark:border-gray-600"></div>
                                <div v-for="group in filteredAvailableTtsModels" :key="group.label">
                                    <h4 class="px-2 py-1.5 text-xs font-bold text-gray-600 dark:text-gray-300">{{ group.label }}</h4>
                                    <button v-for="item in group.items" :key="item.id" @click="selectTtsModel(item.id)" class="menu-item-button" :class="{'selected': activeTtsModelName === item.id}">
                                        <div class="flex items-center space-x-3 truncate">
                                            <img v-if="item.alias?.icon" :src="item.alias.icon" class="h-6 w-6 rounded-md object-cover flex-shrink-0" />
                                            <IconMicrophone v-else class="w-6 h-6 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                                            <div class="truncate text-left"><p class="font-medium truncate text-sm">{{ item.name }}</p></div>
                                        </div>
                                    </button>
                                </div>
                            </div>
                        </DropdownSubmenu>

                        <DropdownSubmenu title="Speech-to-Text" icon="microphone" :icon-src="selectedSttModel?.alias?.icon">
                            <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10 border-b dark:border-gray-700">
                                <input type="text" v-model="sttModelSearchTerm" @click.stop placeholder="Search STT models..." class="input-field-sm w-full">
                            </div>
                            <div class="p-1 flex-grow overflow-y-auto max-h-96">
                                <button @click="selectSttModel(null)" class="menu-item-button" :class="{'selected': !activeSttModelName}">
                                    <div class="flex items-center space-x-3 truncate">
                                        <IconMicrophone class="w-6 h-6 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                                        <div class="truncate text-left"><p class="font-medium truncate text-sm">None</p></div>
                                    </div>
                                </button>
                                <div v-if="filteredAvailableSttModels.length > 0" class="my-1 border-t dark:border-gray-600"></div>
                                <div v-for="group in filteredAvailableSttModels" :key="group.label">
                                    <h4 class="px-2 py-1.5 text-xs font-bold text-gray-600 dark:text-gray-300">{{ group.label }}</h4>
                                    <button v-for="item in group.items" :key="item.id" @click="selectSttModel(item.id)" class="menu-item-button" :class="{'selected': activeSttModelName === item.id}">
                                        <div class="flex items-center space-x-3 truncate">
                                            <img v-if="item.alias?.icon" :src="item.alias.icon" class="h-6 w-6 rounded-md object-cover flex-shrink-0" />
                                            <IconMicrophone v-else class="w-6 h-6 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                                            <div class="truncate text-left"><p class="font-medium truncate text-sm">{{ item.name }}</p></div>
                                        </div>
                                    </button>
                                </div>
                            </div>
                        </DropdownSubmenu>

                         <DropdownSubmenu title="Personality" icon="user-circle" :icon-src="selectedPersonality?.icon_base64">
                              <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10 border-b dark:border-gray-700">
                                <input type="text" v-model="personalitySearchTerm" @click.stop placeholder="Search personalities..." class="input-field-sm w-full">
                            </div>
                            <div class="p-1 flex-grow overflow-y-auto max-h-96">
                                <button @click="selectPersonality(null)" class="menu-item-button" :class="{'selected': !activePersonalityId}">
                                    <div class="flex items-center space-x-3 truncate">
                                        <IconUserCircle class="w-6 h-6 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                                        <div class="truncate text-left"><p class="font-medium truncate text-sm">None</p></div>
                                    </div>
                                </button>
                                <div v-if="filteredAvailablePersonalities.length > 0" class="my-1 border-t dark:border-gray-600"></div>
                                <div v-for="group in filteredAvailablePersonalities" :key="group.label">
                                     <h4 class="px-2 py-1.5 text-xs font-bold text-gray-600 dark:text-gray-300">{{ group.label }}</h4>
                                     <div v-for="item in group.items" :key="item.id" class="relative group/personality">
                                        <button @click="selectPersonality(item.id)" class="menu-item-button w-full" :class="{'selected': activePersonalityId === item.id}">
                                            <div class="flex items-center space-x-3 truncate">
                                                <img v-if="item.icon_base64" :src="item.icon_base64" class="h-6 w-6 rounded-md object-cover flex-shrink-0" />
                                                <IconUserCircle v-else class="w-6 h-6 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                                                <div class="truncate text-left"><p class="font-medium truncate text-sm">{{ item.name }}</p></div>
                                            </div>
                                        </button>
                                        <button v-if="group.label === 'Personal'" @click="handleEditPersonality(item, $event)" class="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md bg-gray-200 dark:bg-gray-600 hover:bg-gray-300 dark:hover:bg-gray-50 opacity-0 group-hover/personality:opacity-100 transition-opacity" title="Edit Personality">
                                            <IconPencil class="w-4 h-4"/>
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
    <div v-else class="flex-1 flex items-center justify-center min-w-0 px-4">
        <div class="flex items-center gap-3">
            <component v-if="pageTitleIcon" :is="pageTitleIcon" class="w-6 h-6 text-gray-500 dark:text-gray-400 flex-shrink-0" />
            <h2 class="text-xl font-semibold text-gray-900 dark:text-gray-100 truncate">{{ pageTitle }}</h2>
        </div>
    </div>

    <!-- Right Side: Action Buttons -->
    <div class="flex items-center space-x-1 sm:space-x-2">
      <div 
        class="w-3 h-3 rounded-full transition-colors flex-shrink-0"
        :class="wsConnected ? 'bg-green-50 animate-pulse' : 'bg-red-500'"
        :title="wsConnected ? 'WebSocket Connected' : 'WebSocket Disconnected. Attempting to reconnect...'"
      ></div>
      <ThemeToggle />
      <NotificationBell v-if="user && user.user_ui_level >= 2" />
      <!-- NEW: Chat Sidebar Toggle Button -->
      <button v-if="user && user.chat_active" @click="uiStore.toggleChatSidebar()" class="btn-icon relative" title="Toggle Messages">
          <IconMessage class="w-5 h-5" />
          <span v-if="unreadDmCount > 0" class="absolute -top-1 -right-1 flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-red-600 rounded-full border-2 border-white dark:border-gray-800">
              {{ unreadDmCount }}
          </span>
      </button>

      <TasksManagerButton />      
      <!-- Slot for view-specific actions -->
      <div id="global-header-actions-target" class="flex items-center gap-2"></div>
      <button v-if="showDataZoneButton" @click="uiStore.toggleDataZone()" class="btn-icon" :class="{'bg-gray-200 dark:bg-gray-700': isDataZoneVisible}" title="Toggle Data Zone">
          <IconDataZone class="w-5 h-5" />
      </button>
    </div>
  </header>
</template>
<style scoped>
.toolbox-select { @apply w-full text-left text-sm bg-gray-50 dark:bg-gray-700/50 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500; }
.menu-item-button { @apply w-full text-left p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center justify-between gap-2; }
.menu-item-button.selected { @apply bg-blue-100 dark:bg-blue-900/50 font-semibold; }
</style>
