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
const { allUserArtefacts, isLoadingArtefacts, discussions } = storeToRefs(discussionsStore);

const viewMode = ref('flat'); // 'flat' or 'discussion'
const expandedDiscussions = ref(new Set());

onMounted(() => {
    discussionsStore.fetchAllUserArtefacts();
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
                <div v-for="group in groupedArtefacts" :key="group.title" @click="handleViewArtefact(group.versions[0])">
                    <ArtefactCard :artefact-group="group" />
                </div>
            </div>

            <!-- GROUPED VIEW -->
            <div v-else class="space-y-4">
                <div v-for="group in groupedByDiscussion" :key="group.id" class="border-b dark:border-gray-800 pb-2 last:border-0">
                    <button @click="toggleDiscussion(group.id)" class="w-full flex items-center justify-between p-2 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg group transition-colors">
                        <div class="flex items-center gap-2 min-w-0">
                            <IconChevronRight class="w-4 h-4 transition-transform text-gray-400" :class="{'rotate-90': expandedDiscussions.has(group.id)}" />
                            <IconFileText class="w-4 h-4 text-blue-500 shrink-0" />
                            <span class="text-xs font-bold truncate text-gray-700 dark:text-gray-200">{{ group.title }}</span>
                        </div>
                        <span class="text-[10px] bg-gray-100 dark:bg-gray-700 px-2 rounded-full text-gray-500">{{ group.artefacts.length }}</span>
                    </button>
                    
                    <div v-if="expandedDiscussions.has(group.id)" class="mt-2 ml-4 space-y-2 animate-in fade-in slide-in-from-top-1">
                        <div v-for="art in group.artefacts" :key="art.title + art.version" @click="handleViewArtefact(art)">
                            <!-- Wrap single artefact in fake group for card compatibility -->
                            <ArtefactCard :artefact-group="{ title: art.title, versions: [art] }" />
                        </div>
                    </div>
                </div>
            </div>

            <div v-if="!isLoadingArtefacts && filteredArtefacts.length === 0" class="empty-state-flat">
                <p class="text-sm text-gray-500">No artefacts found.</p>
            </div>
        </div>
    </div>
</template>
