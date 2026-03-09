<script setup>
import { computed, ref, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const title = computed(() => uiStore.activeSplitArtefactTitle);

const artefactGroup = computed(() => {
    if (!title.value) return null;
    const all = discussionsStore.activeDiscussionArtefacts ||[];
    const versions = all.filter(a => a.title === title.value).sort((a,b) => b.version - a.version);
    if (versions.length === 0) return null;
    return { title: title.value, versions };
});

const selectedVersion = ref(null);
const currentContent = ref('');
const isSaving = ref(false);

watch(artefactGroup, async (group) => {
    if (group && group.versions.length > 0) {
        // Automatically select the latest version if none selected or the selected one isn't in the list
        if (!selectedVersion.value || !group.versions.find(v => v.version === selectedVersion.value)) {
            selectedVersion.value = group.versions[0].version;
        }
        await loadVersion(selectedVersion.value);
    }
}, { immediate: true });

async function loadVersion(version) {
    if (!title.value) return;
    const data = await discussionsStore.fetchArtefactContent({
        discussionId: discussionsStore.currentDiscussionId,
        artefactTitle: title.value,
        version: version
    });
    if (data) currentContent.value = data.content || '';
}

watch(selectedVersion, (newVer) => {
    if (newVer) loadVersion(newVer);
});

async function handleSave() {
    if (!title.value) return;
    isSaving.value = true;
    try {
        await discussionsStore.updateArtefact({
            discussionId: discussionsStore.currentDiscussionId,
            artefactTitle: title.value,
            newContent: currentContent.value,
            newImagesB64:[],
            keptImagesB64:[],
            version: selectedVersion.value,
            updateInPlace: false // Create new version
        });
        uiStore.addNotification('Artefact updated (new version created).', 'success');
        
        // Ensure UI updates to latest version automatically
        await discussionsStore.fetchArtefacts(discussionsStore.currentDiscussionId);
    } finally {
        isSaving.value = false;
    }
}

function handleDownload() {
    const blob = new Blob([currentContent.value], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = title.value || 'artefact.md';
    a.click();
    URL.revokeObjectURL(url);
}
</script>

<template>
    <div class="h-full flex flex-col bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-700 w-full sm:w-[400px] lg:w-[500px] flex-shrink-0 shadow-2xl relative z-20">
        <div class="p-3 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-800">
            <div class="flex items-center gap-2 overflow-hidden">
                <IconFileText class="w-5 h-5 text-blue-500 flex-shrink-0" />
                <h3 class="font-bold text-gray-800 dark:text-gray-200 truncate" :title="title">{{ title }}</h3>
            </div>
            <button @click="uiStore.closeArtefactSplit()" class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded text-gray-500"><IconXMark class="w-5 h-5"/></button>
        </div>
        
        <div v-if="artefactGroup" class="p-2 border-b border-gray-200 dark:border-gray-700 flex gap-2 items-center bg-white dark:bg-gray-850">
            <select v-model="selectedVersion" class="input-field text-xs py-1 px-2 border-none bg-gray-100 dark:bg-gray-800">
                <option v-for="v in artefactGroup.versions" :key="v.version" :value="v.version">v{{ v.version }}</option>
            </select>
            <button @click="handleDownload" class="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600" title="Download"><IconArrowDownTray class="w-4 h-4"/></button>
            <div class="flex-grow"></div>
            <button @click="handleSave" class="btn btn-primary btn-sm flex items-center gap-1" :disabled="isSaving">
                <IconRefresh v-if="isSaving" class="w-3.5 h-3.5 animate-spin" />
                <IconPencil v-else class="w-3.5 h-3.5" />
                Save New Version
            </button>
        </div>
        
        <div class="flex-grow overflow-hidden relative">
            <CodeMirrorEditor 
                v-model="currentContent" 
                class="h-full absolute inset-0 border-0 rounded-none" 
                :renderable="true" 
                initialMode="edit"
            />
        </div>
    </div>
</template>