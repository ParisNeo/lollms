<script setup>
import { computed, ref, watch, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconArrowPath from '../../assets/icons/IconArrowPath.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconMinimize from '../../assets/icons/IconMinimize.vue';
import DropdownMenu from '../ui/DropdownMenu/DropdownMenu.vue';
import { useAuthStore } from '../../stores/auth';

const uiStore = useUiStore();
const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();

const title = computed(() => uiStore.activeSplitArtefactTitle);
const isFullscreen = ref(false);

const exportFormats = computed(() => {
    const formats = [];
    if (authStore.export_to_txt_enabled) formats.push({ label: 'Text (.txt)', value: 'txt' });
    if (authStore.export_to_markdown_enabled) formats.push({ label: 'Markdown (.md)', value: 'md' });
    if (authStore.export_to_html_enabled) formats.push({ label: 'HTML (.html)', value: 'html' });
    if (authStore.export_to_pdf_enabled) formats.push({ label: 'PDF (.pdf)', value: 'pdf' });
    if (authStore.export_to_docx_enabled) formats.push({ label: 'Word (.docx)', value: 'docx' });
    return formats;
});

function handleExport(format) {
    discussionsStore.exportRawContent({ 
        content: content.value, 
        format: format 
    });
}

// Track if this file is currently being modified by AI - Added defensive checks
const isLiveUpdating = computed(() => {
    if (!title.value || !discussionsStore.activeUpdatingArtefacts) return false;
    return discussionsStore.activeUpdatingArtefacts.has(title.value);
});

const artefactGroup = computed(() => {
    if (!title.value) return null;
    const all = discussionsStore.activeDiscussionArtefacts || [];
    // Sort versions DESC (newest first)
    const versions = all.filter(a => a.title === title.value).sort((a,b) => b.version - a.version);
    return versions.length > 0 ? { title: title.value, versions } : null;
});

const dataZoneWidth = ref(600);
const isResizing = ref(false);

function startResize(event) {
    isResizing.value = true;
    const startX = event.clientX;
    const startWidth = dataZoneWidth.value;
    
    const onMouseMove = (e) => {
        if (!isResizing.value) return;
        const delta = startX - e.clientX;
        dataZoneWidth.value = Math.max(350, Math.min(window.innerWidth * 0.8, startWidth + delta));
    };
    
    const onMouseUp = () => {
        isResizing.value = false;
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        localStorage.setItem('lollms_artefactWidth', dataZoneWidth.value);
    };
    
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
}

onMounted(() => {
    const saved = localStorage.getItem('lollms_artefactWidth');
    if (saved) dataZoneWidth.value = parseInt(saved, 10);
});

const selectedVersion = ref(null);
const dbContent = ref('');
const isSaving = ref(false);
const isFetching = ref(false);

// Combined logic: Show the live stream if AI is writing, otherwise show DB content
const content = computed({
    get: () => {
        if (isLiveUpdating.value && discussionsStore.liveArtefactBuffers && discussionsStore.liveArtefactBuffers[title.value]) {
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
    isFetching.value = true;
    try {
        const data = await discussionsStore.fetchArtefactContent({
            discussionId: discussionsStore.currentDiscussionId,
            artefactTitle: title.value,
            version: v
        });
        
        if (data && data.content !== undefined) {
            // [FIX] Strip out legacy redundant headers (--- Document: ... ---) 
            // to keep the Workspace view clean and pure.
            let cleaned = data.content.trim();
            const headerPattern = /^--- (Document|Skill|Note|Artefact): .*? ---/i;
            const footerPattern = /--- End (Document|Skill|Note|Artefact)(?:: .*?)? ---$/i;
            
            cleaned = cleaned.replace(headerPattern, '').replace(footerPattern, '').trim();
            dbContent.value = cleaned;
        }
    } finally {
        isFetching.value = false;
    }
}

// Watch both title AND group availability to trigger initial load
watch([title, () => !!artefactGroup.value], ([newTitle, hasGroup]) => {
    if (newTitle && hasGroup) {
        const latest = artefactGroup.value.versions[0].version;
        if (selectedVersion.value !== latest) {
            selectedVersion.value = latest;
            loadVersion(latest);
        }
    }
}, { immediate: true });

// Watch for AI updates adding new versions to the current file
watch(() => artefactGroup.value?.versions.length, (newLen, oldLen) => {
    if (newLen > oldLen && artefactGroup.value) {
        const latest = artefactGroup.value.versions[0].version;
        selectedVersion.value = latest;
        loadVersion(latest);
    }
});

async function handleSave() {
    if (isLiveUpdating.value) return;
    isSaving.value = true;
    try {
        await discussionsStore.updateArtefact({
            discussionId: discussionsStore.currentDiscussionId,
            artefactTitle: title.value,
            newContent: dbContent.value, // Use the local editable ref
            updateInPlace: false // Creates new version
        });
        uiStore.addNotification("New version saved.", "success");
    } finally {
        isSaving.value = false;
    }
}

async function handleUndo() {
    if (!artefactGroup.value || artefactGroup.value.versions.length < 2) return;
    const prevVersion = artefactGroup.value.versions[1].version;
    
    await discussionsStore.revertArtefact({
        discussionId: discussionsStore.currentDiscussionId,
        artefactTitle: title.value,
        version: prevVersion
    });
    
    selectedVersion.value = prevVersion;
    await loadVersion(prevVersion);
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
    <div 
        class="h-full flex flex-row bg-white dark:bg-gray-900 border-l dark:border-gray-700 shadow-2xl z-20 transition-[width] duration-75"
        :class="{'fixed inset-0 !w-full z-[100]': isFullscreen}"
        :style="isFullscreen ? {} : { width: `${dataZoneWidth}px` }"
    >
        <!-- Resize Handle -->
        <div 
            v-if="!isFullscreen"
            @mousedown.prevent="startResize"
            class="w-1.5 h-full cursor-col-resize hover:bg-blue-500/30 transition-colors flex-shrink-0"
        ></div>

        <div class="flex-1 flex flex-col min-w-0">
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
            <div class="flex items-center gap-1">
                <button @click="isFullscreen = !isFullscreen" class="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg text-gray-500 transition-colors" :title="isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'">
                    <IconMinimize v-if="isFullscreen" class="w-4 h-4" />
                    <IconMaximize v-else class="w-4 h-4" />
                </button>
                <button @click="uiStore.activeSplitArtefactTitle = null" class="p-2 hover:bg-red-500 hover:text-white rounded-full transition-all">
                    <IconXMark class="w-5 h-5"/>
                </button>
            </div>
        </div>
        <div class="p-2 border-b border-gray-200 dark:border-gray-700 flex gap-2 items-center bg-white dark:bg-gray-850 shadow-sm relative z-10">
            <div v-if="artefactGroup" class="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg px-2 py-1 gap-2">
                <span class="text-[10px] font-black text-gray-400 uppercase tracking-tighter">Version</span>
                <select v-model="selectedVersion" @change="loadVersion(selectedVersion)" class="bg-transparent border-none text-xs font-bold text-blue-600 dark:text-blue-400 focus:ring-0 p-0 pr-6">
                    <option v-for="v in artefactGroup.versions" :key="v.version" :value="v.version">
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
            
            <!-- Export Dropdown -->
            <DropdownMenu v-if="exportFormats.length > 0" title="Export" icon="ticket" button-class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 transition-colors" collection="ui">
                <button v-for="format in exportFormats" :key="format.value" @click="handleExport(format.value)" class="w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 text-sm">
                    {{ format.label }}
                </button>
            </DropdownMenu>

            <button @click="download" class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 transition-colors" title="Download Source">
                <IconArrowDownTray class="w-4 h-4" />
            </button>

            <button @click="handleSave" class="btn btn-primary btn-sm h-8 flex items-center gap-2" :disabled="isSaving || isLiveUpdating">
                <IconRefresh v-if="isSaving" class="w-3.5 h-3.5 animate-spin" />
                <IconPencil v-else class="w-3.5 h-3.5" />
                <span>Save v{{ artefactGroup?.versions[0].version + 1 }}</span>
            </button>
        </div>
        <div class="flex-1 relative bg-white dark:bg-gray-950">
            <div v-if="isFetching" class="absolute inset-0 z-10 bg-white/50 dark:bg-gray-900/50 backdrop-blur-sm flex items-center justify-center">
                <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin" />
            </div>
            <CodeMirrorEditor v-model="content" class="absolute inset-0 h-full" initialMode="view" :renderable="true" />
        </div>
        </div>
    </div>
</template>