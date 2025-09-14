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
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';
import IconFolder from '../../assets/icons/IconFolder.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';

const store = useDiscussionsStore();
const authStore = useAuthStore();
const uiStore = useUiStore();

const user = computed(() => authStore.user);
const isLoading = computed(() => store.isLoadingDiscussions && store.sortedDiscussions.length === 0);
const hasMoreDiscussions = computed(() => store.hasMoreDiscussions);
const activeDiscussion = computed(() => store.activeDiscussion);
const discussionGroups = computed(() => store.discussionGroups);

const logoSrc = computed(() => authStore.welcome_logo_url || logoDefault);
const welcomeText = computed(() => authStore.welcomeText || 'LoLLMs');
const welcomeSlogan = computed(() => authStore.welcomeSlogan || 'One tool to rule them all');

const searchTerm = ref('');
const isSearchVisible = ref(false);
const isStarredVisible = ref(true);
const showToolbox = ref(false);
const openGroupIds = ref([]);
const isUngroupedVisible = ref(true); // State for ungrouped section

const filteredAndSortedDiscussions = computed(() => {
    if (!searchTerm.value) {
        return store.sortedDiscussions;
    }
    const lowerCaseSearch = searchTerm.value.toLowerCase();
    return store.sortedDiscussions.filter(d => 
        d.title.toLowerCase().includes(lowerCaseSearch)
    );
});

const starredDiscussions = computed(() => {
    return filteredAndSortedDiscussions.value.filter(d => d.is_starred);
});

const ungroupedDiscussions = computed(() => {
    return filteredAndSortedDiscussions.value.filter(d => !d.group_id && !d.is_starred);
});

const groupsWithDiscussions = computed(() => {
    const groupsMap = new Map(discussionGroups.value.map(g => [g.id, { ...g, discussions: [] }]));
    
    filteredAndSortedDiscussions.value.forEach(d => {
        if (d.is_starred) return;

        if (d.group_id && groupsMap.has(d.group_id)) {
            groupsMap.get(d.group_id).discussions.push(d);
        }
    });

    return Array.from(groupsMap.values()).sort((a,b) => a.name.localeCompare(b.name));
});

function toggleGroup(groupId) {
    const index = openGroupIds.value.indexOf(groupId);
    if (index > -1) {
        openGroupIds.value.splice(index, 1);
    } else {
        openGroupIds.value.push(groupId);
    }
}

function handleNewGroup() {
    uiStore.openModal('discussionGroup', { group: null });
}

function handleEditGroup(group, event) {
    event.stopPropagation();
    uiStore.openModal('discussionGroup', { group });
}

async function handleDeleteGroup(group, event) {
    event.stopPropagation();
    const confirmed = await uiStore.showConfirmation({
        title: `Delete Group "${group.name}"?`,
        message: 'Discussions in this group will become ungrouped. This action cannot be undone.',
        confirmText: 'Delete'
    });
    if (confirmed) {
        store.deleteGroup(group.id);
    }
}

function handleNewDiscussionInGroup(groupId, event) {
    event.stopPropagation();
    store.createNewDiscussion(groupId);
}

function goToFeed() {
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
</script>

<template>
    <div class="h-full flex flex-col bg-white dark:bg-gray-900 w-full flex-shrink-0">
        
        <div class="p-4 border-b border-slate-200 dark:border-gray-700 flex-shrink-0 space-y-3">
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-3 min-w-0 flex-grow">
                    <button @click="uiStore.toggleSidebar" class="p-1 rounded text-slate-500 dark:text-gray-400 hover:bg-slate-100 dark:hover:bg-gray-700 transition-colors md:hidden" title="Toggle Menu">
                        <IconMenu class="w-5 h-5" />
                    </button>
                    <img :src="logoSrc" alt="LoLLMs Logo" class="h-8 w-8 flex-shrink-0 object-contain rounded-md" @error="($event.target.src=logoDefault)">
                    <div class="min-w-0 flex-grow">
                        <h1 class="text-base font-semibold text-slate-900 dark:text-gray-100 truncate" :title="welcomeText">{{ welcomeText }}</h1>
                        <p class="text-xs text-slate-500 dark:text-gray-400 truncate" :title="welcomeSlogan">{{ welcomeSlogan }}</p>
                    </div>
                </div>
                <button @click="uiStore.toggleSidebar" class="btn-icon-flat hidden md:inline-flex ml-2" title="Collapse sidebar">
                    <IconArrowLeft class="h-5 w-5" />
                </button>
            </div>

            <div class="flex items-center justify-between">
                 <div class="flex items-center space-x-1">
                    <button @click="isSearchVisible = !isSearchVisible" class="btn-icon-flat" title="Search discussions" :class="{'bg-slate-100 dark:bg-gray-700': isSearchVisible}">
                        <IconMagnifyingGlass class="h-4 w-4" />
                    </button>
                    <button v-if="user && user.user_ui_level >= 2" @click="goToFeed" class="btn-icon-flat" title="Go to Feed">
                        <IconHome class="h-4 w-4" />
                    </button>
                    <button @click="handleNewGroup" class="btn-icon-flat" title="New Group">
                        <IconFolder class="w-4 h-4" />
                    </button>
                    <button @click="showToolbox = !showToolbox" v-if="user && user.user_ui_level >= 4" class="btn-icon-flat" :class="{ 'bg-slate-100 dark:bg-gray-700': showToolbox }" title="Toggle Toolbox">
                        <IconAdjustmentsHorizontal class="h-4 w-4" />
                    </button>
                </div>
                <button @click="handleNewDiscussion()" class="btn-primary-flat" title="New Discussion">
                    <IconPlus class="h-4 w-4 mr-1 sm:mr-2" stroke-width="2.5" />
                    <span class="hidden sm:inline">New Chat</span>
                </button>
            </div>
            
            <div v-if="isSearchVisible" class="relative mt-2">
                <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                    <IconMagnifyingGlass class="h-4 w-4 text-slate-400 dark:text-gray-500" />
                </div>
                <input type="text" v-model="searchTerm" placeholder="Search discussions..." class="search-input-flat">
                <button v-if="searchTerm" @click="searchTerm = ''" class="absolute inset-y-0 right-0 flex items-center pr-3" title="Clear search">
                    <IconXMark class="h-4 w-4 text-slate-400 hover:text-slate-600 dark:hover:text-gray-300 transition-colors" />
                </button>
            </div>

            <div v-if="user && user.user_ui_level >= 4 && showToolbox" class="overflow-hidden transition-all duration-300 ease-out">
                <div class="p-3 bg-slate-50 dark:bg-gray-800 rounded-md border border-slate-200 dark:border-gray-700">
                    <div class="grid grid-cols-5 gap-2">
                        <button @click="handleImportClick" class="btn-toolbox-flat" title="Import"><IconArrowDownTray class="h-4 w-4" /><span class="text-xs mt-1 font-medium">Import</span></button>
                        <button @click="handleExportClick" class="btn-toolbox-flat" title="Export"><IconArrowUpTray class="h-4 w-4" /><span class="text-xs mt-1 font-medium">Export</span></button>
                        <button @click="handleClone" class="btn-toolbox-flat" title="Clone Discussion" :disabled="!activeDiscussion"><IconCopy class="h-4 w-4" /><span class="text-xs mt-1 font-medium">Clone</span></button>
                        <button @click="handleShowTree" class="btn-toolbox-flat" title="Show Discussion Tree" :disabled="!activeDiscussion"><IconGitBranch class="h-4 w-4" /><span class="text-xs mt-1 font-medium">Tree</span></button>
                        <button @click="handlePrune" class="btn-toolbox-danger-flat" title="Prune Empty"><IconScissors class="h-4 w-4" /><span class="text-xs mt-1 font-medium">Prune</span></button>
                    </div>
                </div>
            </div>
        </div>
        
        <div ref="scrollComponent" class="flex-grow overflow-y-auto p-2 space-y-1 custom-scrollbar">
            <div v-if="isLoading" class="space-y-2 animate-pulse">
                <div v-for="i in 8" :key="'skel-' + i" class="loading-skeleton-flat"></div>
            </div>
            
            <div v-else class="space-y-3">
                <!-- Starred Section -->
                <div v-if="starredDiscussions.length > 0">
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

                 <!-- Groups Section -->
                <div v-for="group in groupsWithDiscussions" :key="group.id" class="discussion-group">
                    <button @click="toggleGroup(group.id)" class="group-header group">
                        <div class="flex items-center space-x-2 flex-grow min-w-0">
                            <IconFolder class="w-4 h-4 flex-shrink-0 text-slate-500 dark:text-gray-400" />
                            <span class="font-medium text-slate-700 dark:text-gray-300 truncate">{{ group.name }}</span>
                            <div class="px-1.5 py-0.5 bg-slate-100 dark:bg-gray-700 text-slate-600 dark:text-gray-400 rounded text-xs font-medium">
                                {{ group.discussions.length }}
                            </div>
                        </div>
                        <div class="flex items-center opacity-0 group-hover:opacity-100 transition-opacity">
                            <button @click="handleEditGroup(group, $event)" class="btn-icon-flat p-1" title="Edit group"><IconPencil class="w-3 h-3" /></button>
                            <button @click="handleDeleteGroup(group, $event)" class="btn-icon-flat p-1 text-red-500 hover:bg-red-100 dark:hover:bg-red-900/50" title="Delete group"><IconTrash class="w-3 h-3" /></button>
                            <button @click="handleNewDiscussionInGroup(group.id, $event)" class="btn-icon-flat p-1" title="New chat in group"><IconPlus class="w-3 h-3" /></button>
                        </div>
                        <IconChevronRight class="w-4 h-4 transition-transform duration-200 text-slate-400 ml-2 flex-shrink-0" :class="{'rotate-90': openGroupIds.includes(group.id)}" />
                    </button>
                    <div v-if="openGroupIds.includes(group.id)" class="pl-2 space-y-1 mt-1 border-l-2 border-slate-200 dark:border-gray-700">
                        <DiscussionItem v-for="discussion in group.discussions" :key="discussion.id" :discussion="discussion" />
                    </div>
                </div>

                <!-- Ungrouped Section -->
                <div v-if="ungroupedDiscussions.length > 0">
                    <button @click="isUngroupedVisible = !isUngroupedVisible" class="section-header-flat mt-4">
                        <div class="flex items-center space-x-2">
                            <span class="font-medium text-slate-700 dark:text-gray-300">Discussions</span>
                            <div class="px-1.5 py-0.5 bg-slate-100 dark:bg-gray-700 text-slate-600 dark:text-gray-400 rounded text-xs font-medium">
                                {{ ungroupedDiscussions.length }}
                            </div>
                        </div>
                        <IconChevronRight class="w-4 h-4 transition-transform duration-200 text-slate-400" :class="{'rotate-90': isUngroupedVisible}" />
                    </button>
                    <div v-if="isUngroupedVisible" class="space-y-1 mt-2">
                        <DiscussionItem v-for="discussion in ungroupedDiscussions" :key="discussion.id" :discussion="discussion" />
                    </div>
                </div>

                <div v-if="filteredAndSortedDiscussions.length === 0 && !isLoading" class="empty-state-flat">
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