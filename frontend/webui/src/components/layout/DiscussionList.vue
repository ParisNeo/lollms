<script setup>
import { computed, ref, onMounted } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import DiscussionItem from './DiscussionItem.vue';
import IconSelectMenu from '../ui/IconSelectMenu.vue';

const store = useDiscussionsStore();
const authStore = useAuthStore();
const uiStore = useUiStore();
const dataStore = useDataStore();

const user = computed(() => authStore.user);

const searchTerm = ref('');
const isStarredVisible = ref(true);
const isRecentsVisible = ref(true);
const showToolbox = ref(false);

const filteredAndSortedDiscussions = computed(() => {
    if (!searchTerm.value) {
        return store.sortedDiscussions;
    }
    const lowerCaseSearch = searchTerm.value.toLowerCase();
    return store.sortedDiscussions.filter(d => 
        d.title.toLowerCase().includes(lowerCaseSearch)
    );
});

const starredDiscussions = computed(() => filteredAndSortedDiscussions.value.filter(d => d.is_starred));
const unstarredDiscussions = computed(() => filteredAndSortedDiscussions.value.filter(d => !d.is_starred));

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

// Use the new grouped models computed property from the data store
const formattedAvailableModels = computed(() => dataStore.availableLollmsModelsGrouped);


function handleNewDiscussion() {
    store.createNewDiscussion();
}
function handleImportClick() {
    uiStore.openModal('import');
}
function handleExportClick() {
    uiStore.openModal('export', { allDiscussions: store.sortedDiscussions });
}
function handlePrune() {
    store.pruneDiscussions();
}

onMounted(() => {
    if (Object.keys(store.discussions).length === 0) {
        store.loadDiscussions();
    }
    if (user.value?.user_ui_level >= 4) {
        if (dataStore.availableLollmsModels.length === 0) dataStore.fetchAvailableLollmsModels();
        if (dataStore.userPersonalities.length === 0 && dataStore.publicPersonalities.length === 0) dataStore.fetchPersonalities();
    }
});
</script>

<template>
    <div class="h-full flex flex-col bg-white dark:bg-gray-800 border-r dark:border-gray-700 w-full sm:w-80 flex-shrink-0">
        
        <!-- Toolbar Header -->
        <div class="p-2 border-b dark:border-gray-700 flex-shrink-0 space-y-2">
            <div class="flex items-center justify-between">
                 <button @click="uiStore.setMainView('feed')" v-if="user && user.user_ui_level >= 2" class="btn-icon" title="Go to Feed">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z" /></svg>
                </button>
                 <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-100 mx-auto">Discussions</h2>
                <div class="flex items-center">
                    <button @click="showToolbox = !showToolbox" v-if="user && user.user_ui_level >= 4" class="btn-icon" title="Toggle Toolbox">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 13.5V3.75m0 9.75a1.5 1.5 0 010 3m0-3a1.5 1.5 0 000 3m0 3.75V16.5m12-3V3.75m0 9.75a1.5 1.5 0 010 3m0-3a1.5 1.5 0 000 3m0 3.75V16.5m-6-9V3.75m0 3.75a1.5 1.5 0 010 3m0-3a1.5 1.5 0 000 3m0 9.75V10.5" /></svg>
                    </button>
                    <button @click="handleNewDiscussion" class="btn-icon" title="New Discussion">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
                        </svg>
                    </button>
                </div>
            </div>
            <!-- Search Bar -->
            <div class="relative">
                <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                    <svg class="h-4 w-4 text-gray-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clip-rule="evenodd" /></svg>
                </div>
                <input type="text" v-model="searchTerm" placeholder="Search discussions..." class="w-full rounded-md border-gray-300 bg-gray-100 dark:border-gray-600 dark:bg-gray-700/50 py-2 pl-10 pr-10 text-sm focus:border-blue-500 focus:ring-blue-500">
                <button v-if="searchTerm" @click="searchTerm = ''" class="absolute inset-y-0 right-0 flex items-center pr-3" title="Clear search">
                    <svg class="h-4 w-4 text-gray-400 hover:text-gray-600" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" /></svg>
                </button>
            </div>
            <!-- Collapsible Toolbox for Experts -->
            <div v-if="user && user.user_ui_level >= 4 && showToolbox" class="p-2 bg-gray-50 dark:bg-gray-900/50 rounded-lg space-y-3">
                <div class="grid grid-cols-2 gap-2">
                    <IconSelectMenu 
                        v-model="activeModelName" 
                        :items="formattedAvailableModels"
                        :is-loading="dataStore.isLoadingLollmsModels"
                        placeholder="Default Model"
                    >
                        <template #button="{ toggle, selectedItem }">
                             <button @click="toggle" class="toolbox-select truncate w-full flex items-center justify-between">
                                <div class="flex items-center space-x-2 truncate">
                                    <span class="w-4 h-4 flex-shrink-0 text-gray-500 dark:text-gray-400">
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 21v-1.5M15.75 3v1.5M19.5 8.25h1.5M19.5 12h1.5m-3.75 3.75h1.5M15.75 21v-1.5m-7.5-6h7.5" /></svg>
                                    </span>
                                    <span class="truncate">{{ selectedItem?.id || 'Default Model' }}</span>
                                </div>
                                <svg class="w-4 h-4 text-gray-400 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
                            </button>
                        </template>
                         <template #placeholder-icon>
                           <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 21v-1.5M15.75 3v1.5M19.5 8.25h1.5M19.5 12h1.5m-3.75 3.75h1.5M15.75 21v-1.5m-7.5-6h7.5" /></svg>
                        </template>
                        <template #item-icon-default>
                           <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 21v-1.5M15.75 3v1.5M19.5 8.25h1.5M19.5 12h1.5m-3.75 3.75h1.5M15.75 21v-1.5m-7.5-6h7.5" /></svg>
                        </template>
                    </IconSelectMenu>
                    <IconSelectMenu v-model="activePersonalityId" :items="availablePersonalities" placeholder="Default Personality">
                        <template #button="{ toggle, selectedItem }">
                            <button @click="toggle" class="toolbox-select truncate w-full flex items-center justify-between">
                                <div class="flex items-center space-x-2 truncate">
                                    <img v-if="selectedItem?.icon_base64" :src="selectedItem.icon_base64" class="h-4 w-4 rounded-full object-cover"/>
                                    <span v-else class="w-4 h-4 flex-shrink-0 text-gray-500 dark:text-gray-400">
                                         <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M17.982 18.725A7.488 7.488 0 0012 15.75a7.488 7.488 0 00-5.982 2.975m11.963 0a9 9 0 10-11.963 0m11.963 0A8.966 8.966 0 0112 21a8.966 8.966 0 01-5.982-2.275M15 9.75a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                                    </span>
                                    <span class="truncate">{{ selectedItem?.name || 'Default Persona' }}</span>
                                </div>
                                <svg class="w-4 h-4 text-gray-400 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
                            </button>
                        </template>
                         <template #placeholder-icon>
                            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M17.982 18.725A7.488 7.488 0 0012 15.75a7.488 7.488 0 00-5.982 2.975m11.963 0a9 9 0 10-11.963 0m11.963 0A8.966 8.966 0 0112 21a8.966 8.966 0 01-5.982-2.275M15 9.75a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                        </template>
                        <template #item-icon-default>
                           <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M17.982 18.725A7.488 7.488 0 0012 15.75a7.488 7.488 0 00-5.982 2.975m11.963 0a9 9 0 10-11.963 0m11.963 0A8.966 8.966 0 0112 21a8.966 8.966 0 01-5.982-2.275M15 9.75a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                        </template>
                    </IconSelectMenu>
                </div>
                <div class="flex items-center justify-around border-t dark:border-gray-700/50 pt-2 mt-2">
                    <button @click="handleImportClick" class="btn-footer" title="Import"><svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg></button>
                    <button @click="handleExportClick" class="btn-footer" title="Export"><svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg></button>
                    <button @click="handlePrune" class="btn-footer-danger" title="Prune Empty"><svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" /></svg></button>
                </div>
            </div>
        </div>
        
        <!-- List of Discussions -->
        <div class="flex-grow overflow-y-auto p-2">
            <div v-if="starredDiscussions.length > 0" class="mb-2">
                <button @click="isStarredVisible = !isStarredVisible" class="collapsible-header">
                    <span>Starred</span>
                    <svg class="w-4 h-4 transition-transform" :class="{'rotate-90': isStarredVisible}" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4-4a1 1 0 01-1.414 0z" clip-rule="evenodd" /></svg>
                </button>
                <div v-if="isStarredVisible" class="mt-1 space-y-1">
                    <DiscussionItem v-for="discussion in starredDiscussions" :key="discussion.id" :discussion="discussion" />
                </div>
            </div>

            <div class="mb-2">
                <button @click="isRecentsVisible = !isRecentsVisible" class="collapsible-header">
                    <span>Recent</span>
                    <svg class="w-4 h-4 transition-transform" :class="{'rotate-90': isRecentsVisible}" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4-4a1 1 0 01-1.414 0z" clip-rule="evenodd" /></svg>
                </button>
                <div v-if="isRecentsVisible" class="mt-1 space-y-1">
                    <DiscussionItem v-for="discussion in unstarredDiscussions" :key="discussion.id" :discussion="discussion" />
                </div>
            </div>

            <div v-if="filteredAndSortedDiscussions.length === 0" class="text-center py-10 px-4">
                <p class="text-sm text-gray-500 dark:text-gray-400">No matching discussions.</p>
                <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">Try a different search term.</p>
            </div>
        </div>
    </div>
</template>

<style scoped>
.btn-icon {
    @apply p-2 rounded-full text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors;
}
.btn-footer {
    @apply p-2 rounded-full text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors;
}
.btn-footer-danger {
    @apply p-2 rounded-full text-red-500 hover:bg-red-100 dark:hover:bg-red-900/50 transition-colors;
}
.toolbox-select {
    @apply w-full text-left text-xs px-2 py-1.5 bg-gray-50 dark:bg-gray-700/50 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500;
}
.collapsible-header {
    @apply w-full flex items-center justify-between text-left p-1 text-xs font-bold uppercase text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50 rounded;
}
</style>