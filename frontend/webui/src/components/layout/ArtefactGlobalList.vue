<script setup>
import { computed, ref, onMounted } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import { storeToRefs } from 'pinia';
import ArtefactCard from '../ui/Cards/ArtefactCard.vue';

// Icons
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconFolder from '../../assets/icons/IconFolder.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';

const props = defineProps({
    searchTerm: { type: String, default: '' }
});

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const { allUserArtefacts, isLoadingArtefacts, discussions, starredArtefacts } = storeToRefs(discussionsStore);

const viewMode = ref('flat'); // 'flat', 'discussion' or 'starred'
const expandedDiscussions = ref(new Set());

onMounted(() => {
    discussionsStore.fetchAllUserArtefacts();
});

function handleStarToggle(title) {
    discussionsStore.toggleStarArtefact(title);
}

function handleShareArtefact(group) {
    const latest = group.versions[0];
    if (!latest) return;
    uiStore.openModal('shareResource', {
        id: latest.title,
        name: latest.title,
        type: 'artefact',
        discussionId: latest.discussion_id || discussionsStore.currentDiscussionId
    });
}

async function handleImportToCurrent(group) {
    const latest = group.versions[0];
    if (!latest || !discussionsStore.currentDiscussionId) {
        uiStore.addNotification("Please select or start a discussion first.", "warning");
        return;
    }
    if (latest.discussion_id === discussionsStore.currentDiscussionId) {
        uiStore.addNotification("Artefact is already in the current discussion.", "info");
        return;
    }
    await discussionsStore.importArtefactFromSource({
        targetDiscussionId: discussionsStore.currentDiscussionId,
        sourceDiscussionId: latest.discussion_id,
        artefactTitle: latest.title
    });
}

const filteredStarredArtefacts = computed(() => {
    const list = groupedArtefacts.value;
    if (!allUserArtefacts.value) return [];
    return list.filter(g => Array.isArray(starredArtefacts.value) && starredArtefacts.value.includes(g.title));
});

const filteredSharedArtefacts = computed(() => {
    const list = groupedArtefacts.value;
    if (!Array.isArray(list)) return [];
    return list.filter(g => g.versions[0]?.author && g.versions[0].author.startsWith('Shared by'));
});

const filteredArtefacts = computed(() => {
    const arts = allUserArtefacts ? allUserArtefacts.value : null;
    if (!Array.isArray(arts)) return [];

    if (!props.searchTerm || typeof props.searchTerm !== 'string') return arts;
    const term = props.searchTerm.toLowerCase();
    return arts.filter(a => 
        (a.title && a.title.toLowerCase().includes(term)) || 
        (a.author && a.author.toLowerCase().includes(term))
    );
});

const groupedByDiscussion = computed(() => {
    const groups = {};
    const arts = filteredArtefacts.value;
    if (!Array.isArray(arts)) return [];

    arts.forEach(art => {
        const dId = art.discussion_id;
        if (!groups[dId]) {
            groups[dId] = {
                id: dId,
                title: discussions.value[dId]?.title || `Discussion ${dId.substring(0, 8)}`,
                artefacts: []
            };
        }
        groups[dId].artefacts.push(art);
    });
    return Object.values(groups).sort((a, b) => a.title.localeCompare(b.title));
});

// Group the global list for ArtefactCard compatibility
const groupedArtefacts = computed(() => {
    const arts = filteredArtefacts ? filteredArtefacts.value : null;
    if (!Array.isArray(arts)) return [];

    const groups = arts.reduce((acc, artefact) => {
        if (artefact && artefact.title) {
            if (!acc[artefact.title]) {
                acc[artefact.title] = { 
                    title: artefact.title, 
                    versions: [] 
                };
            }
            acc[artefact.title].versions.push(artefact);
        }
        return acc;
    }, {});

    const result = Object.values(groups);
    result.forEach(group => {
        if (group.versions) {
            group.versions.sort((a, b) => (b.version || 0) - (a.version || 0));
        }
    });
    return result.sort((a, b) => a.title.localeCompare(b.title));
});

function toggleDiscussion(id) {
    if (expandedDiscussions.value.has(id)) expandedDiscussions.value.delete(id);
    else expandedDiscussions.value.add(id);
}

async function handleViewArtefact(artefact) {
    // 1. Switch to the discussion the artefact belongs to
    if (discussionsStore.currentDiscussionId !== artefact.discussion_id) {
        await discussionsStore.selectDiscussion(artefact.discussion_id);
    }
    
    // 2. Open the workspace for this specific title
    uiStore.activeSplitArtefactTitle = artefact.title;
    uiStore.dataZoneTab = 'workspace';
    uiStore.isDataZoneVisible = true;
}
</script>

<template>
    <div class="h-full flex flex-col">
        <div class="flex justify-between items-center mb-4 px-2 shrink-0">
            <div class="flex bg-gray-100 dark:bg-gray-800 p-1 rounded-lg">
                <button @click="viewMode = 'flat'" 
                        class="px-3 py-1 text-[10px] font-bold rounded-md transition-all"
                        :class="viewMode === 'flat' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-400'">
                    RAW
                </button>
                <button @click="viewMode = 'discussion'" 
                        class="px-3 py-1 text-[10px] font-bold rounded-md transition-all"
                        :class="viewMode === 'discussion' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-400'">
                    BY CHAT
                </button>
                <button @click="viewMode = 'starred'" 
                        class="px-3 py-1 text-[10px] font-bold rounded-md transition-all"
                        :class="viewMode === 'starred' ? 'bg-white dark:bg-gray-700 text-yellow-600 dark:text-yellow-400 shadow-sm' : 'text-gray-400'">
                    STARRED
                </button>
                <button @click="viewMode = 'shared'" 
                        class="px-3 py-1 text-[10px] font-bold rounded-md transition-all"
                        :class="viewMode === 'shared' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-400'">
                    SHARED
                </button>
            </div>
            <button @click="discussionsStore.fetchAllUserArtefacts()" class="p-1.5 text-gray-400 hover:text-blue-500 transition-colors">
                <IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingArtefacts}" />
            </button>
        </div>

        <div class="flex-1 overflow-y-auto custom-scrollbar pr-1">
            <div v-if="isLoadingArtefacts && allUserArtefacts.length === 0" class="text-center py-10">
                <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin mx-auto" />
            </div>

            <!-- FLAT VIEW -->
            <div v-else-if="viewMode === 'flat'" class="space-y-2">
                <div v-for="group in groupedArtefacts" :key="group.title">
                    <ArtefactCard 
                        :artefact-group="group" 
                        :is-starred="starredArtefacts && starredArtefacts.includes(group.title)"
                        @star="handleStarToggle(group.title)"
                        @share="handleShareArtefact(group)"
                        @import="handleImportToCurrent(group)"
                    />
                </div>
            </div>

            <!-- GROUPED VIEW -->
            <div v-else-if="viewMode === 'discussion'" class="space-y-4">
                <div v-for="group in groupedByDiscussion" :key="group.id" class="border-b dark:border-gray-800 pb-2 last:border-0">
                    <button @click="toggleDiscussion(group.id)" class="w-full flex items-center justify-between p-2 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg group transition-colors">
                        <div class="flex items-center gap-2 min-w-0">
                            <IconChevronRight class="w-4 h-4 transition-transform text-gray-400" :class="{'rotate-90': expandedDiscussions.has(group.id)}" />
                            <IconFileText class="w-4 h-4 text-blue-500 shrink-0" />
                            <span class="text-xs font-bold truncate text-gray-700 dark:text-gray-200">{{ group.title }}</span>
                        </div>
                        <span class="text-[10px] bg-gray-100 dark:bg-gray-700 px-2 rounded-full text-gray-500">{{ group.artefacts ? group.artefacts.length : 0 }}</span>
                    </button>

                    <div v-if="expandedDiscussions.has(group.id)" class="mt-2 ml-4 space-y-2 animate-in fade-in slide-in-from-top-1">
                        <div v-for="art in group.artefacts" :key="art.title + art.version">
                            <!-- Wrap single artefact in fake group for card compatibility -->
                            <ArtefactCard 
                                :artefact-group="{ title: art.title, versions: [art] }" 
                                :is-starred="starredArtefacts && starredArtefacts.includes(art.title)"
                                @star="handleStarToggle(art.title)"
                                @share="handleShareArtefact({ versions: [art] })"
                                @import="handleImportToCurrent({ versions: [art] })"
                            />
                        </div>
                    </div>
                </div>
            </div>

            <!-- STARRED VIEW -->
            <div v-else-if="viewMode === 'starred'" class="space-y-2">
                <div v-if="!filteredStarredArtefacts || filteredStarredArtefacts.length === 0" class="text-center py-10 text-gray-400 text-xs">No starred artefacts.</div>
                <div v-for="group in filteredStarredArtefacts" :key="group.title">
                    <ArtefactCard 
                        :artefact-group="group" 
                        :is-starred="true"
                        @star="handleStarToggle(group.title)"
                        @share="handleShareArtefact(group)"
                        @import="handleImportToCurrent(group)"
                    />
                </div>
            </div>

            <!-- SHARED VIEW -->
            <div v-else-if="viewMode === 'shared'" class="space-y-2">
                <div v-if="!filteredSharedArtefacts || filteredSharedArtefacts.length === 0" class="text-center py-10 text-gray-400 text-xs">No shared artefacts.</div>
                <div v-for="group in filteredSharedArtefacts" :key="group.title">
                    <ArtefactCard 
                        :artefact-group="group" 
                        :is-starred="starredArtefacts && starredArtefacts.includes(group.title)"
                        @star="handleStarToggle(group.title)"
                        @share="handleShareArtefact(group)"
                        @import="handleImportToCurrent(group)"
                    />
                </div>
            </div>

            <div v-if="!isLoadingArtefacts && (!filteredArtefacts || filteredArtefacts.length === 0)" class="empty-state-flat">
                <p class="text-sm text-gray-500">No artefacts found.</p>
            </div>
        </div>
    </div>
</template>
