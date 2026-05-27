<script setup>
import { ref, computed } from 'vue';
import { useDiscussionsStore } from '../../../stores/discussions';
import { useUiStore } from '../../../stores/ui';
import { usePyodideStore } from '../../../stores/pyodide';

// Icons
import IconFileText from '../../../assets/icons/IconFileText.vue';
import IconArrowDownTray from '../../../assets/icons/IconArrowDownTray.vue';
import IconPencil from '../../../assets/icons/IconPencil.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconRefresh from '../../../assets/icons/IconRefresh.vue';
import IconMenu from '../../../assets/icons/IconMenu.vue';
import IconPlayCircle from '../../../assets/icons/IconPlayCircle.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconStar from '../../../assets/icons/IconStar.vue';
import IconStarFilled from '../../../assets/icons/IconStarFilled.vue';
import IconShare from '../../../assets/icons/IconShare.vue';
import IconArrowUpTray from '../../../assets/icons/IconArrowUpTray.vue';
import DropdownMenu from '../DropdownMenu/DropdownMenu.vue';

const props = defineProps({
  artefactGroup: { type: Object, required: true },
  isStarred: { type: Boolean, default: false }
});

defineEmits(['star', 'share', 'import']);

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const pyodideStore = usePyodideStore();

const selectedVersion = ref(props.artefactGroup.versions[0]?.version || 1);
const isExecuting = ref(false);

const isSavedLibraryItem = computed(() => {
    const latest = props.artefactGroup.versions[0];
    return latest && latest.discussion_id === 'saved';
});

async function handleSaveToLibrary() {
    await discussionsStore.saveArtefactToLibrary({
        discussionId: discussionsStore.currentDiscussionId,
        artefactTitle: props.artefactGroup.title,
        version: selectedVersion.value
    });
}

async function handleStarClick() {
    if (!isSavedLibraryItem.value && !props.isStarred) {
        // Auto-promote to global library if starred from a local discussion
        await handleSaveToLibrary();
    }
    emit('star');
}

const fileExtension = computed(() => {
    const title = props.artefactGroup.title;
    const parts = title.split('.');
    return parts.length > 1 ? parts.pop().toUpperCase() : 'DOC';
});

const isLoadedToDataZone = computed(() => {
    const versionData = props.artefactGroup.versions.find(v => v.version === selectedVersion.value);
    return versionData ? versionData.is_loaded : false;
});

const showImportOption = computed(() => {
    const latest = props.artefactGroup.versions[0];
    return latest && latest.discussion_id && latest.discussion_id !== discussionsStore.currentDiscussionId;
});

const fileExtensionLower = computed(() => {
    const title = props.artefactGroup.title;
    const parts = title.split('.');
    return parts.length > 1 ? parts.pop().toLowerCase() : '';
});

const isExecutable = computed(() => {
    const ext = fileExtensionLower.value;
    return ['html', 'mermaid', 'svg', 'py', 'js', 'json', 'python', 'javascript'].includes(ext);
});

const executeTitle = computed(() => {
    const ext = fileExtensionLower.value;
    if (['html', 'mermaid', 'svg'].includes(ext)) return 'Show Render / Preview';
    return 'Execute Code';
});

async function executeArtefactContent(title, content, ext) {
    const cleanContent = content.trim();

    if (ext === 'html') {
        const blob = new Blob([cleanContent], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        window.open(url, '_blank');
        setTimeout(() => URL.revokeObjectURL(url), 60000);
        uiStore.addNotification("HTML opened in a new tab.", "success");
    } else if (ext === 'svg') {
        const htmlContent = `<div style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; padding: 1rem;">${cleanContent}</div>`;
        uiStore.openModal('interactiveOutput', { htmlContent, title: `SVG Preview: ${title}`, contentType: 'svg' });
    } else if (ext === 'mermaid') {
        uiStore.openModal('interactiveOutput', {
            title: `Mermaid Diagram: ${title}`,
            contentType: 'mermaid',
            sourceCode: cleanContent
        });
    } else if (ext === 'js' || ext === 'javascript') {
        const createDynamicFn = window.Function;
        try {
            let capturedOutput = '';
            const originalLog = console.log;
            console.log = (...args) => { capturedOutput += args.map(String).join(' ') + '\n'; };

            const result = (new createDynamicFn(cleanContent))();
            if (result !== undefined && result !== null) {
                capturedOutput += String(result);
            }
            console.log = originalLog;

            const outputText = capturedOutput.trim() || 'Execution finished with no output.';
            uiStore.openModal('interactiveOutput', { content: `### Execution Output\n\`\`\`\n${outputText}\n\`\`\``, title: `JS Output: ${title}` });
        } catch (e) {
            uiStore.openModal('interactiveOutput', { content: `### Execution Error\n\`\`\`\n${e.toString()}\n\`\`\``, title: `JS Error: ${title}` });
        }
    } else if (ext === 'py' || ext === 'python') {
        uiStore.addNotification("Loading Python environment...", "info");
        if (!pyodideStore.isReady) {
            await pyodideStore.initialize();
        }

        const canvasId = `code-canvas-${Date.now()}`;
        const result = await pyodideStore.runCode(cleanContent, {
            canvasSelector: `#${canvasId}`
        });

        const outputText = result.error || result.output || (result.image || result.usesCanvas ? '' : 'Execution finished with no output.');

        if (result.usesCanvas) {
            uiStore.openModal('interactiveOutput', { canvasId: canvasId, title: `Python Canvas: ${title}` });
        } else if (result.image) {
            const htmlContent = `<div style="text-align: center;"><img src="data:image/png;base64,${result.image}" class="max-w-full h-auto mx-auto" /></div>`;
            uiStore.openModal('interactiveOutput', { htmlContent, title: `Python Output: ${title}` });
        } else {
            uiStore.openModal('interactiveOutput', { content: `### Python Output\n\`\`\`\n${outputText}\n\`\`\``, title: `Python Output: ${title}` });
        }
    } else {
        uiStore.openModal('interactiveOutput', { content: cleanContent, title: `Viewer: ${title}` });
    }
}

async function handleExecute() {
    if (isExecuting.value) return;
    isExecuting.value = true;
    try {
        const data = await discussionsStore.fetchArtefactContent({
            discussionId: discussionsStore.currentDiscussionId,
            artefactTitle: props.artefactGroup.title,
            version: selectedVersion.value
        });

        let content = '';
        if (typeof data === 'string') {
            content = data;
        } else if (data && typeof data === 'object') {
            content = data.content ?? '';
        }

        const ext = fileExtensionLower.value;
        const title = props.artefactGroup.title;

        await executeArtefactContent(title, content, ext);
    } catch (e) {
        console.error("Execution failed:", e);
        uiStore.addNotification("Execution failed: " + e.message, "error");
    } finally {
        isExecuting.value = false;
    }
}

const currentType = computed(() => {
    // Get type from the first (latest) version
    return props.artefactGroup.versions[0]?.artefact_type || 'file';
});

function handleView() {
    uiStore.activeSplitArtefactTitle = props.artefactGroup.title;
    if (!uiStore.isDataZoneVisible) uiStore.isDataZoneVisible = true;
}

function handleRename() {
    uiStore.openModal('renameArtefact', {
        artefactTitle: props.artefactGroup.title,
        discussionId: discussionsStore.currentDiscussionId
    });
}

async function handleDelete() {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete Artefact?`,
        message: `This will delete "${props.artefactGroup.title}" and all its versions.`,
        confirmText: 'Delete'
    });
    if (confirmed.confirmed) {
        await discussionsStore.deleteArtefact({
            discussionId: discussionsStore.currentDiscussionId,
            artefactTitle: props.artefactGroup.title,
        });
    }
}

async function handleDownload() {
    const data = await discussionsStore.fetchArtefactContent({
        discussionId: discussionsStore.currentDiscussionId,
        artefactTitle: props.artefactGroup.title,
        version: selectedVersion.value
    });
    const blob = new Blob([data.content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = props.artefactGroup.title;
    a.click();
    URL.revokeObjectURL(url);
}

async function toggleLoad() {
    if (isLoadedToDataZone.value) {
        await discussionsStore.unloadArtefactFromContext({
            discussionId: discussionsStore.currentDiscussionId,
            artefactTitle: props.artefactGroup.title,
            version: selectedVersion.value,
            artefactType: currentType.value // Ensure correct category for text removal
        });
    } else {
        await discussionsStore.loadArtefactToContext({
            discussionId: discussionsStore.currentDiscussionId,
            artefactTitle: props.artefactGroup.title,
            version: selectedVersion.value
        });
    }
}
</script>

<template>
  <div class="artefact-list-item group" :class="{'is-active': isLoadedToDataZone}">
    <!-- File Icon Box -->
    <div class="file-icon-box" @click="handleView" :class="{
        'bg-blue-50 text-blue-500 border-blue-200': currentType === 'file' || currentType === 'document' || currentType === 'code',
        'bg-amber-50 text-amber-500 border-amber-200': currentType === 'note',
        'bg-green-50 text-green-500 border-green-200': currentType === 'skill'
    }">
        <IconFileText v-if="currentType === 'file' || currentType === 'document' || currentType === 'code'" class="w-6 h-6" />
        <IconPencil v-else-if="currentType === 'note'" class="w-6 h-6" />
        <IconSparkles v-else-if="currentType === 'skill'" class="w-6 h-6" />
    </div>

    <!-- Info Column -->
    <div class="grow min-w-0 flex flex-col justify-center cursor-pointer" @click="handleView">
        <div class="flex items-center gap-2">
            <h4 class="text-sm font-bold text-gray-800 dark:text-gray-200 truncate" :title="artefactGroup.title">
                {{ artefactGroup.title }}
            </h4>
            <!-- Star Toggle Button -->
            <button @click.stop="handleStarClick" class="p-1 rounded-full transition-colors shrink-0" :class="isStarred ? 'text-yellow-500' : 'text-gray-300 dark:text-gray-600 hover:text-yellow-500'">
                <IconStarFilled v-if="isStarred" class="w-3.5 h-3.5" />
                <IconStar v-else class="w-3.5 h-3.5" />
            </button>
        </div>
        <div class="flex items-center gap-2 mt-0.5">
            <span class="text-[10px] font-black text-gray-400 uppercase tracking-widest">{{ fileExtension }}</span>
            <span class="text-[10px] text-gray-400">•</span>
            <span class="text-[10px] font-bold text-gray-400">v{{ selectedVersion }}</span>
        </div>
    </div>

    <!-- Actions -->
    <div class="flex items-center gap-1 pr-1">
        <button v-if="isExecutable" @click.stop="handleExecute" class="p-2 text-gray-400 hover:text-green-600 transition-colors" :title="executeTitle">
            <IconAnimateSpin v-if="isExecuting" class="w-5 h-5 animate-spin" />
            <IconPlayCircle v-else class="w-5 h-5" />
        </button>

        <button @click.stop="handleDownload" class="p-2 text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors" title="Download">
            <IconArrowDownTray class="w-5 h-5" />
        </button>


        <!-- Advanced Actions Dropdown -->
        <DropdownMenu icon="menu" buttonClass="p-2 text-gray-400 hover:text-gray-900 dark:hover:white transition-colors" title="Actions">
            <button v-if="!isSavedLibraryItem" @click="toggleLoad" class="menu-item">
                <IconRefresh class="w-4 h-4 mr-3" :class="{'text-green-500': isLoadedToDataZone}"/> 
                <span>{{ isLoadedToDataZone ? 'Unload from Context' : 'Load to Context' }}</span>
            </button>
            <button v-if="!isSavedLibraryItem" @click="handleSaveToLibrary" class="menu-item text-blue-500">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                </svg>
                <span>Save to Library</span>
            </button>
            <button v-if="showImportOption" @click="$emit('import')" class="menu-item">
                <IconArrowUpTray class="w-4 h-4 mr-3" />
                <span>Import to Current Chat</span>
            </button>
            <button @click="$emit('share')" class="menu-item">
                <IconShare class="w-4 h-4 mr-3" />
                <span>Share with Friend</span>
            </button>
            <button @click="handleStarClick" class="menu-item">
                <IconStarFilled v-if="isStarred" class="w-4 h-4 mr-3 text-yellow-500" />
                <IconStar v-else class="w-4 h-4 mr-3" />
                <span>{{ isStarred ? 'Unstar' : 'Star' }}</span>
            </button>
            <button v-if="!isSavedLibraryItem" @click="handleRename" class="menu-item">
                <IconPencil class="w-4 h-4 mr-3" />
                <span>Rename</span>
            </button>
            <div class="menu-divider"></div>
            <button @click="handleDelete" class="menu-item text-red-500">
                <IconTrash class="w-4 h-4 mr-3" />
                <span>Delete</span>
            </button>
        </DropdownMenu>
    </div>
  </div>
</template>

<style scoped>
@reference "tailwindcss";

.artefact-list-item {
    @apply flex items-center gap-4 p-2 bg-white dark:bg-gray-800/40 rounded-xl border border-gray-100 dark:border-gray-700/50 hover:border-gray-300 dark:hover:border-gray-600 transition-all shadow-sm;
}
.artefact-list-item.is-active {
    @apply ring-1 ring-blue-500/50 bg-blue-50/10 dark:bg-blue-900/5;
}
.file-icon-box {
    @apply w-12 h-12 shrink-0 flex items-center justify-center bg-gray-50 dark:bg-gray-900 rounded-lg border dark:border-gray-700 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors;
}
.menu-item { @apply flex items-center w-full px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors; }
.menu-divider { @apply my-1 border-t border-gray-100 dark:border-gray-700; }
</style>