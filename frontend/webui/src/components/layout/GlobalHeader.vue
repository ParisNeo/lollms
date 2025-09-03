<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import TasksManagerButton from './TasksManagerButton.vue';
import ThemeToggle from '../ui/ThemeToggle.vue';
import IconPlusCircle from '../../assets/icons/IconPlusCircle.vue';
import IconDataZone from '../../assets/icons/IconDataZone.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';
import IconUserCircle from '../../assets/icons/IconUserCircle.vue';
import IconSelectMenu from '../ui/IconSelectMenu.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import logoDefault from '../../assets/logo.png';

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const dataStore = useDataStore();
const route = useRoute();

const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const user = computed(() => authStore.user);
const logoSrc = computed(() => authStore.welcome_logo_url || logoDefault);

const pageLayoutRoutes = ['Settings', 'Admin', 'DataStores', 'Friends', 'Help', 'Profile', 'Messages'];
const isHomePageLayout = computed(() => !pageLayoutRoutes.includes(route.name));
const pageTitle = computed(() => uiStore.pageTitle);
const pageTitleIcon = computed(() => uiStore.pageTitleIcon);

const activePersonalityId = computed({
    get: () => user.value?.active_personality_id,
    set: (id) => authStore.updateUserPreferences({ active_personality_id: id })
});
const activeModelName = computed({
    get: () => user.value?.lollms_model_name,
    set: (name) => authStore.updateUserPreferences({ lollms_model_name: name })
});

const availablePersonalities = computed(() => {
    return [
        { isGroup: true, label: 'Personal', items: dataStore.userPersonalities.sort((a, b) => a.name.localeCompare(b.name)) },
        { isGroup: true, label: 'Public', items: dataStore.publicPersonalities.sort((a, b) => a.name.localeCompare(b.name)) }
    ].filter(group => group.items.length > 0);
});

const formattedAvailableModels = computed(() => dataStore.availableLLMModelsGrouped);

function openModelCard(model) {
    uiStore.openModal('modelCard', { model });
}

function newDiscussion() {
  discussionsStore.createNewDiscussion();
}
</script>

<template>
  <header class="flex-shrink-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-3 flex items-center justify-between shadow-sm z-10">
    <!-- Left Side: App Logo and Title -->
    <div class="flex items-center space-x-3">
        <img :src="logoSrc" alt="LoLLMs Logo" class="h-8 w-8 object-contain" @error="($event.target.src=logoDefault)">
        <h1 class="text-lg font-bold text-gray-800 dark:text-gray-100 hidden sm:block">LoLLMs</h1>
    </div>

    <!-- Center: Model Selectors (Home) or Page Title (Other Views) -->
    <div v-if="isHomePageLayout && user && user.user_ui_level >= 2" class="hidden md:flex items-center gap-2 flex-1 min-w-0 justify-center px-4">
        <div class="min-w-0 max-w-xs w-full">
            <IconSelectMenu 
                v-model="activeModelName" 
                :items="formattedAvailableModels"
                :is-loading="dataStore.isLoadingLollmsModels"
                placeholder="Select Model"
            >
                <template #button="{ toggle, selectedItem }">
                    <button @click="toggle" class="toolbox-select truncate w-full flex items-center justify-between">
                        <div class="flex items-center space-x-3 truncate">
                            <img v-if="selectedItem?.icon_base64" :src="selectedItem.icon_base64" class="h-8 w-8 rounded-md object-cover"/>
                            <span v-else class="w-8 h-8 flex-shrink-0 text-gray-500 dark:text-gray-400 flex items-center justify-center bg-gray-200 dark:bg-gray-700 rounded-md"><IconCpuChip class="w-5 h-5" /></span>
                            <div class="min-w-0 text-left">
                                <span class="block font-semibold truncate">{{ selectedItem?.name || 'Select Model' }}</span>
                                <span class="block text-xs text-gray-500 truncate">{{ selectedItem?.description || 'Click to choose a model' }}</span>
                            </div>
                        </div>
                        <svg class="w-4 h-4 text-gray-400 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
                    </button>
                </template>
                <template #placeholder-icon><IconCpuChip class="w-5 h-5" /></template>
                <template #item-icon-default><IconCpuChip class="w-5 h-5" /></template>
                 <template #item-extra="{ item }">
                    <div class="flex items-center gap-2">
                        <IconEye v-if="item.alias?.has_vision" class="w-5 h-5 text-green-500" title="Vision active" />
                        <button v-if="item.alias" @click.stop="openModelCard(item)" class="p-1 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600" title="View model details">
                            <IconInfo class="w-4 h-4 text-blue-500" />
                        </button>
                    </div>
                </template>
            </IconSelectMenu>
        </div>

        <div class="min-w-0 max-w-xs w-full">
            <IconSelectMenu 
                v-model="activePersonalityId" 
                :items="availablePersonalities" 
                :is-loading="dataStore.isLoadingPersonalities"
                placeholder="Select Personality"
            >
                <template #button="{ toggle, selectedItem }">
                    <button @click="toggle" class="toolbox-select truncate w-full flex items-center justify-between">
                         <div class="flex items-center space-x-3 truncate">
                            <img v-if="selectedItem?.icon_base64" :src="selectedItem.icon_base64" class="h-8 w-8 rounded-md object-cover"/>
                            <span v-else class="w-8 h-8 flex-shrink-0 text-gray-500 dark:text-gray-400 flex items-center justify-center bg-gray-200 dark:bg-gray-700 rounded-md"><IconUserCircle class="w-5 h-5" /></span>
                            <div class="min-w-0 text-left">
                                <span class="block font-semibold truncate">{{ selectedItem?.name || 'Select Personality' }}</span>
                                <span class="block text-xs text-gray-500 truncate">{{ selectedItem?.description || 'Click to choose a personality' }}</span>
                            </div>
                        </div>
                        <svg class="w-4 h-4 text-gray-400 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
                    </button>
                </template>
                <template #placeholder-icon><IconUserCircle class="w-5 h-5" /></template>
                <template #item-icon-default><IconUserCircle class="w-5 h-5" /></template>
            </IconSelectMenu>
        </div>
    </div>
    <div v-else class="flex-1 flex items-center justify-center min-w-0 px-4">
        <div class="flex items-center gap-3">
            <component v-if="pageTitleIcon" :is="pageTitleIcon" class="w-6 h-6 text-gray-500 dark:text-gray-400 flex-shrink-0" />
            <h2 class="text-xl font-semibold text-gray-900 dark:text-gray-100 truncate">{{ pageTitle }}</h2>
        </div>
    </div>

    <!-- Right Side: Action Buttons -->
    <div class="flex items-center space-x-2">
      <ThemeToggle />
      <TasksManagerButton />

      <button v-if="activeDiscussion && isHomePageLayout" @click="uiStore.toggleDataZone()" class="btn-icon" title="Toggle Data Zone">
        <IconDataZone class="w-5 h-5" />
      </button>

      <button v-if="isHomePageLayout" @click="newDiscussion" class="btn btn-secondary" title="New Discussion">
        <IconPlusCircle class="w-5 h-5" />
        <span class="hidden sm:inline ml-2">New</span>
      </button>
      
      <!-- Slot for view-specific actions -->
      <slot name="actions"></slot>
    </div>
  </header>
</template>
<style scoped>
.toolbox-select { @apply w-full text-left text-sm px-2.5 py-1.5 bg-gray-50 dark:bg-gray-700/50 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500; }
</style>