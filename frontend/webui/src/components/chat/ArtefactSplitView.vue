<script setup>
import { computed, ref, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconArrowPath from '../../assets/icons/IconArrowPath.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const title = computed(() => uiStore.activeSplitArtefactTitle);

// Track if this file is currently being modified by AI
const isLiveUpdating = computed(() => discussionsStore.activeUpdatingArtefacts.has(title.value));

const artefactGroup = computed(() => {
    if (!title.value) return null;
    const all = discussionsStore.activeDiscussionArtefacts || [];
    // Sort versions DESC (newest first)
    const versions = all.filter(a => a.title === title.value).sort((a,b) => b.version - a.version);
    return versions.length > 0 ? { title: title.value, versions } : null;
});

const selectedVersion = ref(null);
const dbContent = ref('');
const isSaving = ref(false);

// Combined logic: Show the live stream if AI is writing, otherwise show DB content
const displayContent = computed({
    get: () => {
        if (isLiveUpdating.value && discussionsStore.liveArtefactBuffers[title.value]) {
            return discussionsStore.liveArtefactBuffers[title.value];
        }
        return dbContent.value;
    },
    set: (val) => {
        dbContent.value = val;
    }
});

async function loadVersion(v) {
    if (!title.value || v === null) return;
    const data = await discussionsStore.fetchArtefactContent({
        discussionId: discussionsStore.currentDiscussionId,
        artefactTitle: title.value,
        version: v
    });
    
    if (data && data.content) {
        // [FIX] Strip out legacy redundant headers (--- Document: ... ---) 
        // to keep the Workspace view clean and pure.
        let cleaned = data.content.trim();
        const headerPattern = /^(--- (Document|Skill|Note): .*? ---)/i;
        const footerPattern = /(--- End \2(?:: .*?)? ---)$/i;
        
        cleaned = cleaned.replace(headerPattern, '').replace(footerPattern, '').trim();
        dbContent.value = cleaned;
    }
}

// Watch for group changes (e.g. AI adds a new version)
watch(artefactGroup, (newGroup, oldGroup) => {
    if (!newGroup) return;
    
    // If AI just finished a new version or it's first load
    const latestVersion = newGroup.versions[0].version;
    if (!selectedVersion.value || (oldGroup && newGroup.versions.length > oldGroup.versions.length)) {
        selectedVersion.value = latestVersion;
        loadVersion(latestVersion);
    }
}, { immediate: true, deep: true });

async function handleSave() {
    isSaving.value = true;
    await discussionsStore.updateArtefact({
        discussionId: discussionsStore.currentDiscussionId,
        artefactTitle: title.value,
        newContent: content.value,
        updateInPlace: false // Creates new version
    });
    isSaving.value = false;
    uiStore.addNotification("New version saved.", "success");
}

async function handleUndo() {
    if (artefactGroup.value.versions.length < 2) return;
    const prevVersion = artefactGroup.value.versions[1].version;
    await apiClient.post(`/api/discussions/${discussionsStore.currentDiscussionId}/artefacts/revert`, {
        title: title.value,
        version: prevVersion
    });
    selectedVersion.value = prevVersion;
    await loadVersion(prevVersion);
    discussionsStore.fetchArtefacts(discussionsStore.currentDiscussionId);
}

function download() {
    const blob = new Blob([content.value], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = title.value;
    a.click();
}
</script>

<template>
    <div class="h-full flex flex-col bg-white dark:bg-gray-900 border-l dark:border-gray-700 w-full lg:w-[600px] shadow-2xl z-20">
        <div class="p-3 border-b flex justify-between items-center bg-gray-50 dark:bg-gray-800 shadow-sm">
            <div class="flex items-center gap-3 min-w-0">
                <!-- Dynamic Icon based on Type -->
                <div class="p-2 rounded-lg" :class="{
                    'bg-blue-100 text-blue-600': (artefactGroup?.versions[0]?.artefact_type || 'document') === 'document',
                    'bg-purple-100 text-purple-600': artefactGroup?.versions[0]?.artefact_type === 'code',
                    'bg-amber-100 text-amber-600': artefactGroup?.versions[0]?.artefact_type === 'note',
                    'bg-teal-100 text-teal-600': artefactGroup?.versions[0]?.artefact_type === 'skill'
                }">
                    <IconCode v-if="artefactGroup?.versions[0]?.artefact_type === 'code'" class="w-4 h-4" />
                    <IconPencil v-else-if="artefactGroup?.versions[0]?.artefact_type === 'note'" class="w-4 h-4" />
                    <IconSparkles v-else-if="artefactGroup?.versions[0]?.artefact_type === 'skill'" class="w-4 h-4" />
                    <IconFileText v-else class="w-4 h-4" />
                </div>
                
                <div class="flex flex-col min-w-0">
                    <span class="text-[9px] font-black uppercase text-gray-400 tracking-widest">
                        {{ artefactGroup?.versions[0]?.artefact_type || 'Artefact' }} Workspace
                    </span>
                    <span class="font-bold text-sm truncate dark:text-gray-100">{{ title }}</span>
                </div>
            </div>
            <button @click="uiStore.activeSplitArtefactTitle = null" class="p-2 hover:bg-red-500 hover:text-white rounded-full transition-all">
                <IconXMark class="w-5 h-5"/>
            </button>
        </div>
        <div class="p-2 border-b border-gray-200 dark:border-gray-700 flex gap-2 items-center bg-white dark:bg-gray-850 shadow-sm relative z-10">
            <div class="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg px-2 py-1 gap-2">
                <span class="text-[10px] font-black text-gray-400 uppercase tracking-tighter">Version</span>
                <select v-model="selectedVersion" @change="loadVersion(selectedVersion)" class="bg-transparent border-none text-xs font-bold text-blue-600 dark:text-blue-400 focus:ring-0 p-0 pr-6">
                    <option v-for="v in artefactGroup?.versions" :key="v.version" :value="v.version">
                        v{{ v.version }} {{ v.version === artefactGroup.versions[0].version ? '(Latest)' : '' }}
                    </option>
                </select>
            </div>

            <button @click="handleUndo" :disabled="artefactGroup?.versions.length < 2 || isSaving" 
                    class="btn btn-secondary btn-xs h-8" title="Restore previous version">
                <IconArrowPath class="w-3.5 h-3.5 mr-1" />
                Undo
            </button>
            
            <div class="flex-grow"></div>
            
            <button @click="download" class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 transition-colors" title="Download File">
                <IconArrowDownTray class="w-4 h-4" />
            </button>

            <button @click="handleSave" class="btn btn-primary btn-sm h-8 flex items-center gap-2" :disabled="isSaving || isLiveUpdating">
                <IconRefresh v-if="isSaving" class="w-3.5 h-3.5 animate-spin" />
                <IconPencil v-else class="w-3.5 h-3.5" />
                <span>Save v{{ artefactGroup?.versions[0].version + 1 }}</span>
            </button>
        </div>
        <div class="flex-1 relative">
            <CodeMirrorEditor v-model="content" class="absolute inset-0 h-full" initialMode="edit" :renderable="true" />
        </div>
    </div>
</template>