<!-- [UPDATE] frontend/webui/src/components/layout/DiscussionList.vue -->
<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import DiscussionItem from './DiscussionItem.vue';

import IconHome from '../../assets/icons/IconHome.vue';
import IconAdjustmentsHorizontal from '../../assets/icons/IconAdjustmentsHorizontal.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import IconScissors from '../../assets/icons/IconScissors.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconGitBranch from '../../assets/icons/IconGitBranch.vue'; 
import IconCopy from '../../assets/icons/IconCopy.vue';

const store = useDiscussionsStore();
const authStore = useAuthStore();
const uiStore = useUiStore();
const dataStore = useDataStore();

const user = computed(() => authStore.user);
const isLoading = computed(() => store.isLoadingDiscussions && store.sortedDiscussions.length === 0);
const hasMoreDiscussions = computed(() => store.hasMoreDiscussions);
const activeDiscussion = computed(() => store.activeDiscussion); // NEW COMPUTED

const searchTerm = ref('');
const isStarredVisible = ref(true);
const isRecentsVisible = ref(true);
const showToolbox = ref(false);
const scrollComponent = ref(null);
const loadMoreTrigger = ref(null);

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

function handleNewDiscussion() { store.createNewDiscussion(); }
function handleImportClick() { uiStore.openModal('import'); }
function handleExportClick() { uiStore.openModal('export', { allDiscussions: store.sortedDiscussions }); }
function handlePrune() { store.pruneDiscussions(); }
function handleShowTree() { 
  if (activeDiscussion.value) {
    uiStore.openModal('discussionTree', { discussionId: activeDiscussion.value.id });
  } else {
    uiStore.addNotification('Please select a discussion first.', 'warning');
  }
}
function handleClone() {
  if (activeDiscussion.value) {
    store.cloneDiscussion(activeDiscussion.value.id);
  } else {
    uiStore.addNotification('Please select a discussion to clone.', 'warning');
  }
}

const observer = new IntersectionObserver((entries) => {
  if (entries[0].isIntersecting && hasMoreDiscussions.value && !isLoading.value) {
    store.loadDiscussions(false);
  }
}, {
  root: scrollComponent.value,
  threshold: 0.1,
});

onMounted(() => {
  if (loadMoreTrigger.value) {
    observer.observe(loadMoreTrigger.value);
  }
});

onUnmounted(() => {
  if (loadMoreTrigger.value) {
    observer.unobserve(loadMoreTrigger.value);
  }
});
</script>

<template>
    <div class="h-full flex flex-col bg-white dark:bg-gray-800 border-r dark:border-gray-700 w-full sm:w-80 flex-shrink-0">
        
        <div class="p-2 border-b dark:border-gray-700 flex-shrink-0 space-y-2">
            <div class="flex items-center justify-between">
                 <button @click="uiStore.setMainView('feed')" v-if="user && user.user_ui_level >= 2" class="btn-icon" title="Go to Feed">
                    <IconHome class="h-5 w-5" />
                </button>
                 <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-100 mx-auto">Discussions</h2>
                <div class="flex items-center">
                    <button @click="showToolbox = !showToolbox" v-if="user && user.user_ui_level >= 4" class="btn-icon" title="Toggle Toolbox">
                        <IconAdjustmentsHorizontal class="h-5 w-5" />
                    </button>
                    <button @click="handleNewDiscussion" class="btn-icon" title="New Discussion">
                        <IconPlus class="h-5 w-5" stroke-width="2" />
                    </button>
                </div>
            </div>
            <div class="relative">
                <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                    <IconMagnifyingGlass class="h-4 w-4 text-gray-400" />
                </div>
                <input type="text" v-model="searchTerm" placeholder="Search discussions..." class="w-full rounded-md border-gray-300 bg-gray-100 dark:border-gray-600 dark:bg-gray-700/50 py-2 pl-10 pr-10 text-sm focus:border-blue-500 focus:ring-blue-500">
                <button v-if="searchTerm" @click="searchTerm = ''" class="absolute inset-y-0 right-0 flex items-center pr-3" title="Clear search">
                    <IconXMark class="h-4 w-4 text-gray-400 hover:text-gray-600" />
                </button>
            </div>
            <div v-if="user && user.user_ui_level >= 4 && showToolbox" class="p-2 bg-gray-50 dark:bg-gray-900/50 rounded-lg space-y-3">
                <div class="flex items-center justify-around border-t dark:border-gray-700/50 pt-2 mt-2">
                    <button @click="handleImportClick" class="btn-footer" title="Import"><IconArrowDownTray class="h-5 w-5" /></button>
                    <button @click="handleExportClick" class="btn-footer" title="Export"><IconArrowUpTray class="h-5 w-5" /></button>
                    <button @click="handleClone" class="btn-footer" title="Clone Discussion Data" :disabled="!activeDiscussion"><IconCopy class="h-5 w-5" /></button>
                    <button @click="handleShowTree" class="btn-footer" title="Show Discussion Tree" :disabled="!activeDiscussion">
                        <IconGitBranch class="h-5 w-5" />
                    </button>
                    <button @click="handlePrune" class="btn-footer-danger" title="Prune Empty"><IconScissors class="h-5 w-5" /></button>
                </div>
            </div>
        </div>
        
        <div ref="scrollComponent" class="flex-grow overflow-y-auto p-2">
            <div v-if="isLoading" class="space-y-2 animate-pulse">
                <div v-for="i in 10" :key="'skel-recent-' + i" class="h-10 bg-gray-200 dark:bg-gray-700/50 rounded-lg"></div>
            </div>
            
            <div v-else>
                <div v-if="starredDiscussions.length > 0 && !searchTerm" class="mb-2">
                    <button @click="isStarredVisible = !isStarredVisible" class="collapsible-header">
                        <span>Starred</span>
                        <IconChevronRight class="w-4 h-4 transition-transform" :class="{'rotate-90': isStarredVisible}" />
                    </button>
                    <div v-if="isStarredVisible" class="mt-1 space-y-1">
                        <DiscussionItem v-for="discussion in starredDiscussions" :key="discussion.id" :discussion="discussion" />
                    </div>
                </div>
                <div class="mb-2">
                    <button v-if="starredDiscussions.length > 0 && !searchTerm" @click="isRecentsVisible = !isRecentsVisible" class="collapsible-header">
                        <span>Recent</span>
                        <IconChevronRight class="w-4 h-4 transition-transform" :class="{'rotate-90': isRecentsVisible}" />
                    </button>
                    <div v-if="isRecentsVisible || searchTerm" class="mt-1 space-y-1">
                        <DiscussionItem v-for="discussion in unstarredDiscussions" :key="discussion.id" :discussion="discussion" />
                    </div>
                </div>

                <div ref="loadMoreTrigger" v-if="hasMoreDiscussions" class="p-4 text-center">
                    <svg class="animate-spin h-6 w-6 text-gray-400 mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                </div>
                
                <div v-if="filteredAndSortedDiscussions.length === 0 && !isLoading" class="text-center py-10 px-4">
                    <p class="text-sm text-gray-500 dark:text-gray-400">{{ searchTerm ? 'No matching discussions.' : 'No discussions yet.' }}</p>
                    <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">{{ searchTerm ? 'Try a different search term.' : 'Start a new conversation to begin.' }}</p>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.btn-icon { @apply p-2 rounded-full text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors; }
.btn-footer { @apply p-2 rounded-full text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed; }
.btn-footer-danger { @apply p-2 rounded-full text-red-500 hover:bg-red-100 dark:hover:bg-red-900/50 transition-colors; }
.toolbox-select { @apply w-full text-left text-xs px-2 py-1.5 bg-gray-50 dark:bg-gray-700/50 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500; }
.collapsible-header { @apply w-full flex items-center justify-between text-left p-1 text-xs font-bold uppercase text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50 rounded; }
</style>