<script setup>
import { computed, ref, onMounted } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useNotesStore } from '../../stores/notes';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import { storeToRefs } from 'pinia';
import DiscussionItem from './DiscussionItem.vue';
import DiscussionGroupItem from './DiscussionGroupItem.vue';
import NoteList from '../notes/NoteList.vue';

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
import IconGitBranch from '../../assets/icons/ui/IconGitBranch.vue'; 
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconMenu from '../../assets/icons/IconMenu.vue';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';
import IconFolder from '../../assets/icons/IconFolder.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconMessage from '../../assets/icons/IconMessage.vue'; 
import IconPencil from '../../assets/icons/IconPencil.vue';

const store = useDiscussionsStore();
const notesStore = useNotesStore();
const authStore = useAuthStore();
const uiStore = useUiStore();

const { user } = storeToRefs(authStore);
const { isLoadingDiscussions, discussionGroupsTree, sharedWithMe, sortedDiscussions } = storeToRefs(store);

const activeDiscussion = computed(() => store.activeDiscussion);
const logoSrc = computed(() => authStore.welcome_logo_url || logoDefault);
const welcomeText = computed(() => authStore.welcomeText || 'LoLLMs');
const welcomeSlogan = computed(() => authStore.welcomeSlogan || 'One tool to rule them all');

const activeTab = ref('chat'); // 'chat' or 'notes'
const searchTerm = ref('');
const isSearchVisible = ref(false);
const isSharedVisible = ref(false);
const showToolbox = ref(false);
const isUngroupedVisible = ref(true);
const isStarredVisible = ref(false);
const isRootDragOver = ref(false);

onMounted(() => {
    // Fetch notes when component mounts, if not already fetched
    if (notesStore.notes.length === 0) {
        notesStore.fetchNotes();
    }
});

// Filter shared discussions based on search term
const filteredSharedDiscussions = computed(() => {
    if (!searchTerm.value) return sharedWithMe.value;
    const lowerCaseSearch = searchTerm.value.toLowerCase();
    return sharedWithMe.value.filter(d => 
        d.title.toLowerCase().includes(lowerCaseSearch)
    );
});

// The tree structure now comes directly from the store, but we need to filter it
const filteredDiscussionTree = computed(() => {
    if (!searchTerm.value) return discussionGroupsTree.value;
    const lowerCaseSearch = searchTerm.value.toLowerCase();

    const filterDiscussions = (discussions) => discussions.filter(d => d.title.toLowerCase().includes(lowerCaseSearch));

    const filterGroups = (groups) => {
        return groups.map(group => {
            const filteredChildren = filterGroups(group.children || []);
            const filteredDiscussionsInGroup = filterDiscussions(group.discussions || []);
            if (group.name.toLowerCase().includes(lowerCaseSearch) || filteredChildren.length > 0 || filteredDiscussionsInGroup.length > 0) {
                if (group.name.toLowerCase().includes(lowerCaseSearch)) {
                    return group; 
                }
                return { ...group, children: filteredChildren, discussions: filteredDiscussionsInGroup };
            }
            return null;
        }).filter(Boolean);
    };

    return {
        starred: filterDiscussions(discussionGroupsTree.value.starred || []),
        groups: filterGroups(discussionGroupsTree.value.groups || []),
        ungrouped: filterDiscussions(discussionGroupsTree.value.ungrouped || [])
    };
});

function handleNewGroup() {
    if (activeTab.value === 'chat') {
        uiStore.openModal('discussionGroup', { parentGroup: null });
    } else {
        // Note Group Modal
        uiStore.openModal('noteGroup', { parentGroup: null });
    }
}

function goToFeed() { uiStore.setMainView('feed'); }

async function handleRootDrop(event) {
    isRootDragOver.value = false;
    const data = event.dataTransfer.getData('application/lollms-item');
    if (!data) return;
    try {
        const { type, id } = JSON.parse(data);
        if (activeTab.value === 'chat') {
             if (type === 'group') {
                const group = store.discussionGroups.find(g => g.id === id);
                if (group && group.parent_id !== null) await store.updateGroup(id, group.name, null);
            } else if (type === 'discussion') {
                const discussion = store.discussions[id];
                if(discussion && discussion.group_id !== null) await store.moveDiscussionToGroup(id, null);
            }
        } else {
            // Handle Note Drag Drop to Root (ungroup)
            if (type === 'noteGroup') {
                 const group = notesStore.groups.find(g => g.id === id);
                 if (group && group.parent_id !== null) await notesStore.updateGroup(id, group.name, null);
            } else if (type === 'note') {
                 const note = notesStore.notes.find(n => n.id === id);
                 if (note && note.group_id !== null) await notesStore.updateNote(id, { group_id: null });
            }
        }
    } catch (e) { console.error("Root drop failed:", e); }
}

function handleNewItem() { 
    if (activeTab.value === 'chat') {
        store.createNewDiscussion(store.currentGroupId); 
    } else {
        // New Note
        notesStore.createNote({ title: 'New Note', content: '', group_id: notesStore.activeGroupId });
    }
}

function handleSelectUngrouped() {
    store.currentGroupId = null;
    isUngroupedVisible.value = !isUngroupedVisible.value;
}

function handleImportClick() { uiStore.openModal('import'); }
function handleExportClick() { uiStore.openModal('export', { allDiscussions: store.sortedDiscussions }); }
function handlePrune() { store.pruneDiscussions(); }
function handleShowTree() { if (activeDiscussion.value) uiStore.openModal('discussionTree', { discussionId: activeDiscussion.value.id }); else uiStore.addNotification('Please select a discussion first.', 'warning'); }
function handleClone() { if (activeDiscussion.value) store.cloneDiscussion(activeDiscussion.value.id); else uiStore.addNotification('Please select a discussion to clone.', 'warning'); }
</script>

<template>
    <div 
      class="h-full flex flex-col bg-white dark:bg-gray-900 w-full flex-shrink-0"
      @dragover.prevent="isRootDragOver = true"
      @dragleave="isRootDragOver = false"
      @drop.prevent="handleRootDrop"
      :class="{'bg-blue-50 dark:bg-blue-900/20': isRootDragOver}"
    >
        
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
                    <IconArrowLeft class="h-5 h-5" />
                </button>
            </div>

            <!-- TABS -->
            <div class="flex space-x-1 bg-slate-100 dark:bg-gray-800 p-1 rounded-lg">
                <button 
                    @click="activeTab = 'chat'" 
                    class="flex-1 py-1.5 text-sm font-medium rounded-md transition-colors flex items-center justify-center gap-2"
                    :class="activeTab === 'chat' ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                >
                    <IconMessage class="w-4 h-4" />
                    <span>Chats</span>
                </button>
                <button 
                    @click="activeTab = 'notes'" 
                    class="flex-1 py-1.5 text-sm font-medium rounded-md transition-colors flex items-center justify-center gap-2"
                    :class="activeTab === 'notes' ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                >
                    <IconPencil class="w-4 h-4" />
                    <span>Notes</span>
                </button>
            </div>

            <div class="flex items-center justify-between">
                 <div class="flex items-center space-x-1">
                    <button @click="isSearchVisible = !isSearchVisible" class="btn-icon-flat" title="Search" :class="{'bg-slate-100 dark:bg-gray-700': isSearchVisible}">
                        <IconMagnifyingGlass class="h-4 w-4" />
                    </button>
                    <button v-if="user && user.user_ui_level >= 2" @click="goToFeed" class="btn-icon-flat" title="Go to Feed">
                        <IconHome class="h-4 w-4" />
                    </button>
                    <router-link to="/news" class="btn-icon-flat" title="News">
                        <IconFileText class="h-4 w-4" />
                    </router-link>
                    <button @click="handleNewGroup" class="btn-icon-flat" title="New Group">
                        <IconFolder class="w-4 w-4" />
                    </button>
                    <button v-if="activeTab === 'chat' && user && user.user_ui_level >= 4" @click="showToolbox = !showToolbox" class="btn-icon-flat" :class="{ 'bg-slate-100 dark:bg-gray-700': showToolbox }" title="Toggle Toolbox">
                        <IconAdjustmentsHorizontal class="h-4 w-4" />
                    </button>
                </div>
                <button @click="handleNewItem()" class="btn-primary-flat !px-2.5" :title="activeTab === 'chat' ? 'New Discussion' : 'New Note'">
                    <IconPlus class="h-4 w-4" stroke-width="2.5" />
                </button>
            </div>
            
            <div v-if="isSearchVisible" class="relative mt-2">
                <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                    <IconMagnifyingGlass class="h-4 w-4 text-slate-400 dark:text-gray-500" />
                </div>
                <input type="text" v-model="searchTerm" :placeholder="activeTab === 'chat' ? 'Search discussions...' : 'Search notes...'" class="search-input-flat">
                <button v-if="searchTerm" @click="searchTerm = ''" class="absolute inset-y-0 right-0 flex items-center pr-3" title="Clear search">
                    <IconXMark class="h-4 w-4 text-slate-400 hover:text-slate-600 dark:hover:text-gray-300 transition-colors" />
                </button>
            </div>

            <div v-if="activeTab === 'chat' && user && user.user_ui_level >= 4 && showToolbox" class="overflow-hidden transition-all duration-300 ease-out">
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
            <!-- CHAT TAB CONTENT -->
            <template v-if="activeTab === 'chat'">
                <div v-if="isLoadingDiscussions" class="space-y-2 animate-pulse">
                    <div v-for="i in 8" :key="'skel-' + i" class="loading-skeleton-flat"></div>
                </div>
                
                <div v-else class="space-y-3">
                    <!-- Shared With Me -->
                    <div v-if="filteredSharedDiscussions.length > 0">
                        <button @click="isSharedVisible = !isSharedVisible" class="section-header-flat">
                            <div class="flex items-center space-x-2">
                                <span class="font-medium text-slate-700 dark:text-gray-300">Shared with me</span>
                                <div class="px-1.5 py-0.5 bg-slate-100 dark:bg-gray-700 text-slate-600 dark:text-gray-400 rounded text-xs font-medium">
                                    {{ filteredSharedDiscussions.length }}
                                </div>
                            </div>
                            <IconChevronRight class="w-4 h-4 transition-transform duration-200 text-slate-400" :class="{'rotate-90': isSharedVisible}" />
                        </button>
                        <div v-if="isSharedVisible" class="space-y-1 mt-2">
                            <DiscussionItem v-for="discussion in filteredSharedDiscussions" :key="discussion.share_id" :discussion="discussion" />
                        </div>
                    </div>

                    <!-- Starred Section -->
                    <div v-if="filteredDiscussionTree.starred && filteredDiscussionTree.starred.length > 0">
                        <button @click="isStarredVisible = !isStarredVisible" class="section-header-flat">
                            <div class="flex items-center space-x-2">
                                <span class="font-medium text-slate-700 dark:text-gray-300">Starred</span>
                                <div class="px-1.5 py-0.5 bg-slate-100 dark:bg-gray-700 text-slate-600 dark:text-gray-400 rounded text-xs font-medium">
                                    {{ filteredDiscussionTree.starred.length }}
                                </div>
                            </div>
                            <IconChevronRight class="w-4 h-4 transition-transform duration-200 text-slate-400" :class="{'rotate-90': isStarredVisible}" />
                        </button>
                        <div v-if="isStarredVisible" class="space-y-1 mt-2">
                            <DiscussionItem v-for="discussion in filteredDiscussionTree.starred" :key="discussion.id" :discussion="discussion" />
                        </div>
                    </div>

                    <!-- Groups Section -->
                    <DiscussionGroupItem 
                        v-for="group in filteredDiscussionTree.groups" 
                        :key="group.id" 
                        :group="group" 
                    />

                    <!-- Ungrouped Section -->
                    <div v-if="filteredDiscussionTree.ungrouped && filteredDiscussionTree.ungrouped.length > 0">
                        <button @click="handleSelectUngrouped" class="section-header-flat mt-4" :class="{'bg-blue-50 dark:bg-blue-900/20': store.currentGroupId === null && !store.currentDiscussionId}">
                            <div class="flex items-center space-x-2">
                                <span class="font-medium text-slate-700 dark:text-gray-300">Discussions</span>
                                <div class="px-1.5 py-0.5 bg-slate-100 dark:bg-gray-700 text-slate-600 dark:text-gray-400 rounded text-xs font-medium">
                                    {{ filteredDiscussionTree.ungrouped.length }}
                                </div>
                            </div>
                            <IconChevronRight class="w-4 h-4 transition-transform duration-200 text-slate-400" :class="{'rotate-90': isUngroupedVisible}" />
                        </button>
                        <div v-if="isUngroupedVisible" class="space-y-1 mt-2">
                            <DiscussionItem v-for="discussion in filteredDiscussionTree.ungrouped" :key="discussion.id" :discussion="discussion" />
                        </div>
                    </div>

                    <div v-if="!isLoadingDiscussions && sortedDiscussions.length === 0 && sharedWithMe.length === 0" class="empty-state-flat">
                        <p class="text-base font-medium text-slate-600 dark:text-gray-300 mb-2">
                            {{ searchTerm ? 'No matches found' : 'Start your first conversation' }}
                        </p>
                        <p class="text-sm text-slate-500 dark:text-gray-400">
                            {{ searchTerm ? 'Try different keywords' : 'Click the "+" button to begin' }}
                        </p>
                    </div>
                </div>
            </template>

            <!-- NOTES TAB CONTENT -->
            <template v-else>
                <NoteList :search-term="searchTerm" />
            </template>
        </div>
    </div>
</template>
