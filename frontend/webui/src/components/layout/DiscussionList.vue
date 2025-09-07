<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import DiscussionItem from './DiscussionItem.vue';

import logoDefault from '../../assets/logo.png';
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
import IconMenu from '../../assets/icons/IconMenu.vue';

const store = useDiscussionsStore();
const authStore = useAuthStore();
const uiStore = useUiStore();

const user = computed(() => authStore.user);
const isLoading = computed(() => store.isLoadingDiscussions && store.sortedDiscussions.length === 0);
const hasMoreDiscussions = computed(() => store.hasMoreDiscussions);
const activeDiscussion = computed(() => store.activeDiscussion);
const logoSrc = computed(() => authStore.welcome_logo_url || logoDefault);

const searchTerm = ref('');
const isStarredVisible = ref(false);
const isSharedVisible = ref(true);
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
const sharedDiscussions = computed(() => {
    if (!searchTerm.value) {
        return store.sharedWithMe;
    }
    const lowerCaseSearch = searchTerm.value.toLowerCase();
    return store.sharedWithMe.filter(d => 
        d.title.toLowerCase().includes(lowerCaseSearch)
    );
});

function goToFeed() {
    console.log("Feed button clicked in DiscussionList.");
    uiStore.setMainView('feed');
}

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
    <div class="h-full flex flex-col bg-white dark:bg-gray-900 w-full flex-shrink-0">
        
        <!-- Integrated Header with Logo -->
        <div class="p-4 border-b border-slate-200 dark:border-gray-700 flex-shrink-0 space-y-3">
            <!-- Logo and Actions Row -->
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-3 min-w-0">
                    <!-- Mobile Menu Toggle (hidden on desktop) -->
                    <button 
                        @click="uiStore.toggleSidebar" 
                        class="p-1 rounded text-slate-500 dark:text-gray-400 hover:bg-slate-100 dark:hover:bg-gray-700 transition-colors md:hidden" 
                        title="Toggle Menu"
                    >
                        <IconMenu class="w-5 h-5" />
                    </button>
                    
                    <img :src="logoSrc" alt="LoLLMs Logo" class="h-6 w-6 flex-shrink-0 object-contain" @error="($event.target.src=logoDefault)">
                    <div class="min-w-0">
                        <h1 class="text-base font-semibold text-slate-900 dark:text-gray-100 truncate">LoLLMs</h1>
                        <p class="text-xs text-slate-500 dark:text-gray-400 truncate hidden sm:block">One tool to rule them all</p>
                    </div>
                </div>
                
                <div class="flex items-center space-x-1">
                    <button 
                        v-if="user && user.user_ui_level >= 2" 
                        @click="goToFeed" 
                        class="btn-icon-flat" 
                        title="Go to Feed"
                    >
                        <IconHome class="h-4 w-4" />
                    </button>
                    
                    <button 
                        @click="showToolbox = !showToolbox" 
                        v-if="user && user.user_ui_level >= 4" 
                        class="btn-icon-flat" 
                        :class="{ 'bg-slate-100 dark:bg-gray-700 text-slate-700 dark:text-gray-200': showToolbox }"
                        title="Toggle Toolbox"
                    >
                        <IconAdjustmentsHorizontal class="h-4 w-4" />
                    </button>
                    
                    <button 
                        @click="handleNewDiscussion" 
                        class="btn-primary-flat" 
                        title="New Discussion"
                    >
                        <IconPlus class="h-4 w-4" stroke-width="2" />
                    </button>
                </div>
            </div>

            <!-- Search Bar -->
            <div class="relative">
                <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                    <IconMagnifyingGlass class="h-4 w-4 text-slate-400 dark:text-gray-500" />
                </div>
                <input 
                    type="text" 
                    v-model="searchTerm" 
                    placeholder="Search..." 
                    class="search-input-flat"
                >
                <button 
                    v-if="searchTerm" 
                    @click="searchTerm = ''" 
                    class="absolute inset-y-0 right-0 flex items-center pr-3" 
                    title="Clear search"
                >
                    <IconXMark class="h-4 w-4 text-slate-400 hover:text-slate-600 dark:hover:text-gray-300 transition-colors" />
                </button>
            </div>

            <!-- Toolbox -->
            <div 
                v-if="user && user.user_ui_level >= 4 && showToolbox" 
                class="overflow-hidden transition-all duration-300 ease-out"
            >
                <div class="p-3 bg-slate-50 dark:bg-gray-800 rounded-md border border-slate-200 dark:border-gray-700">
                    <div class="grid grid-cols-5 gap-2">
                        <button @click="handleImportClick" class="btn-toolbox-flat" title="Import">
                            <IconArrowDownTray class="h-4 w-4" />
                            <span class="text-xs mt-1 font-medium">Import</span>
                        </button>
                        <button @click="handleExportClick" class="btn-toolbox-flat" title="Export">
                            <IconArrowUpTray class="h-4 w-4" />
                            <span class="text-xs mt-1 font-medium">Export</span>
                        </button>
                        <button @click="handleClone" class="btn-toolbox-flat" title="Clone Discussion" :disabled="!activeDiscussion">
                            <IconCopy class="h-4 w-4" />
                            <span class="text-xs mt-1 font-medium">Clone</span>
                        </button>
                        <button @click="handleShowTree" class="btn-toolbox-flat" title="Show Discussion Tree" :disabled="!activeDiscussion">
                            <IconGitBranch class="h-4 w-4" />
                            <span class="text-xs mt-1 font-medium">Tree</span>
                        </button>
                        <button @click="handlePrune" class="btn-toolbox-danger-flat" title="Prune Empty">
                            <IconScissors class="h-4 w-4" />
                            <span class="text-xs mt-1 font-medium">Prune</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Content Area -->
        <div ref="scrollComponent" class="flex-grow overflow-y-auto p-2 space-y-1 custom-scrollbar">
            <div v-if="isLoading" class="space-y-2 animate-pulse">
                <div v-for="i in 8" :key="'skel-recent-' + i" class="loading-skeleton-flat"></div>
            </div>
            
            <div v-else class="space-y-3">
                <!-- Starred Section -->
                <div v-if="starredDiscussions.length > 0 && !searchTerm">
                    <button @click="isStarredVisible = !isStarredVisible" class="section-header-flat">
                        <div class="flex items-center space-x-2">
                            <span class="font-medium text-slate-700 dark:text-gray-300">Starred</span>
                            <div class="px-1.5 py-0.5 bg-slate-100 dark:bg-gray-700 text-slate-600 dark:text-gray-400 rounded text-xs font-medium">
                                {{ starredDiscussions.length }}
                            </div>
                        </div>
                        <IconChevronRight class="w-4 h-4 transition-transform duration-200 text-slate-400" :class="{'rotate-90': isStarredVisible}" />
                    </button>
                    <div v-if="isStarredVisible" class="space-y-1 mt-2">
                        <DiscussionItem v-for="discussion in starredDiscussions" :key="discussion.id" :discussion="discussion" />
                    </div>
                </div>

                <!-- Shared Section -->
                <div v-if="sharedDiscussions.length > 0">
                    <button @click="isSharedVisible = !isSharedVisible" class="section-header-flat">
                        <div class="flex items-center space-x-2">
                            <span class="font-medium text-slate-700 dark:text-gray-300">Shared</span>
                            <div class="px-1.5 py-0.5 bg-slate-100 dark:bg-gray-700 text-slate-600 dark:text-gray-400 rounded text-xs font-medium">
                                {{ sharedDiscussions.length }}
                            </div>
                        </div>
                        <IconChevronRight class="w-4 h-4 transition-transform duration-200 text-slate-400" :class="{'rotate-90': isSharedVisible}" />
                    </button>
                    <div v-if="isSharedVisible" class="space-y-1 mt-2">
                        <DiscussionItem 
                            v-for="discussion in sharedDiscussions" 
                            :key="discussion.share_id" 
                            :discussion="discussion" 
                        />
                    </div>
                </div>

                <!-- Recent Section -->
                <div>
                    <button 
                        v-if="(starredDiscussions.length > 0 || sharedDiscussions.length > 0) && !searchTerm" 
                        @click="isRecentsVisible = !isRecentsVisible" 
                        class="section-header-flat"
                    >
                        <div class="flex items-center space-x-2">
                            <span class="font-medium text-slate-700 dark:text-gray-300">Recent</span>
                            <div class="px-1.5 py-0.5 bg-slate-100 dark:bg-gray-700 text-slate-600 dark:text-gray-400 rounded text-xs font-medium">
                                {{ unstarredDiscussions.length }}
                            </div>
                        </div>
                        <IconChevronRight class="w-4 h-4 transition-transform duration-200 text-slate-400" :class="{'rotate-90': isRecentsVisible}" />
                    </button>
                    <div v-if="isRecentsVisible || searchTerm" class="space-y-1 mt-2">
                        <DiscussionItem v-for="discussion in unstarredDiscussions" :key="discussion.id" :discussion="discussion" />
                    </div>
                </div>

                <!-- Load More -->
                <div ref="loadMoreTrigger" v-if="hasMoreDiscussions" class="flex justify-center py-4">
                    <div class="flex items-center space-x-2 text-slate-500 dark:text-gray-400">
                        <svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <span class="text-sm">Loading...</span>
                    </div>
                </div>
                
                <!-- Empty State -->
                <div v-if="filteredAndSortedDiscussions.length === 0 && sharedDiscussions.length === 0 && !isLoading" class="empty-state-flat">
                    <p class="text-base font-medium text-slate-600 dark:text-gray-300 mb-2">
                        {{ searchTerm ? 'No matches found' : 'No conversations yet' }}
                    </p>
                    <p class="text-sm text-slate-500 dark:text-gray-400">
                        {{ searchTerm ? 'Try different keywords' : 'Start your first conversation' }}
                    </p>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.btn-icon-flat { 
    @apply p-2 rounded text-slate-600 dark:text-gray-300 hover:bg-slate-100 dark:hover:bg-gray-700 transition-colors duration-150; 
}

.btn-primary-flat { 
    @apply px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium transition-colors duration-150; 
}

.search-input-flat {
    @apply w-full rounded border border-slate-200 dark:border-gray-600 bg-white dark:bg-gray-800 py-2 pl-10 pr-10 text-sm placeholder-slate-500 dark:placeholder-gray-400 text-slate-900 dark:text-gray-100 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors duration-150;
}

.btn-toolbox-flat { 
    @apply flex flex-col items-center p-2 rounded text-slate-600 dark:text-gray-300 hover:bg-white dark:hover:bg-gray-700 transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed; 
}

.btn-toolbox-danger-flat { 
    @apply flex flex-col items-center p-2 rounded text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors duration-150; 
}

.section-header-flat { 
    @apply w-full flex items-center justify-between text-left p-2 hover:bg-slate-50 dark:hover:bg-gray-800 rounded transition-colors duration-150; 
}

.loading-skeleton-flat {
    @apply h-10 bg-slate-200 dark:bg-gray-700 rounded animate-pulse;
}

.empty-state-flat {
    @apply text-center py-8 px-4;
}

.custom-scrollbar {
    scrollbar-width: thin;
    scrollbar-color: rgb(203 213 225) transparent;
}

.custom-scrollbar::-webkit-scrollbar {
    width: 4px;
}

.custom-scrollbar::-webkit-scrollbar-track {
    background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
    background-color: rgb(203 213 225);
    border-radius: 2px;
}

.dark .custom-scrollbar::-webkit-scrollbar-thumb {
    background-color: rgb(75 85 99);
}
</style>
