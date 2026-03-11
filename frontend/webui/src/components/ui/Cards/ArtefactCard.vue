<script setup>
import { computed, ref } from 'vue';
import { useDiscussionsStore } from '../../../stores/discussions';
import { useUiStore } from '../../../stores/ui';

// Icons
import IconFileText from '../../../assets/icons/IconFileText.vue';
import IconPencil from '../../../assets/icons/IconPencil.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';
import IconArrowDownTray from '../../../assets/icons/IconArrowDownTray.vue';
import IconXMark from '../../../assets/icons/IconXMark.vue';
import IconPlus from '../../../assets/icons/IconPlus.vue';

const props = defineProps({
  artefactGroup: {
    type: Object,
    required: true,
  },
});

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const selectedVersion = ref(props.artefactGroup.versions[0]?.version || 1);

const isLoadedToDataZone = computed(() => props.artefactGroup.isAnyVersionLoaded);
const isLoadedToPrompt = computed(() => discussionsStore.promptLoadedArtefacts.has(props.artefactGroup.title));

const loadedVersion = computed(() => {
    if (!isLoadedToDataZone.value) return null;
    return props.artefactGroup.versions.find(v => v.is_loaded);
});

const cardClasses = computed(() => ({
    'loaded-data-zone': isLoadedToDataZone.value,
    'loaded-prompt': isLoadedToPrompt.value && !isLoadedToDataZone.value
}));

async function handleLoadToDataZone() {
    await discussionsStore.loadArtefactToContext({
        discussionId: discussionsStore.currentDiscussionId,
        artefactTitle: props.artefactGroup.title,
        version: selectedVersion.value,
    });
}

function handleLoadToPrompt() {
    discussionsStore.loadArtefactToPrompt({
        discussionId: discussionsStore.currentDiscussionId,
        artefactTitle: props.artefactGroup.title,
        version: selectedVersion.value
    });
}

async function handleUnloadFromDataZone() {
    if (!loadedVersion.value) return;
    await discussionsStore.unloadArtefactFromContext({
        discussionId: discussionsStore.currentDiscussionId,
        artefactTitle: props.artefactGroup.title,
        version: loadedVersion.value.version,
    });
}

function handleUnloadFromPrompt() {
    discussionsStore.unloadArtefactFromPrompt(props.artefactGroup.title);
}

function handleView() {
    // Set the workspace focus
    uiStore.activeSplitArtefactTitle = props.artefactGroup.title;
    if (!uiStore.isDataZoneVisible) uiStore.isDataZoneVisible = true;
}

function handleEdit() {
    // Both View and Edit now use the Split View Workspace for consistent experience
    handleView();
}

async function handleDelete() {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete Artefact '${props.artefactGroup.title}'?`,
        message: 'This will permanently delete the artefact and all its versions.',
        confirmText: 'Delete',
    });
    if (confirmed) {
        await discussionsStore.deleteArtefact({
            discussionId: discussionsStore.currentDiscussionId,
            artefactTitle: props.artefactGroup.title,
        });
    }
}
</script>

<script setup>
import { computed, ref } from 'vue';
import { useDiscussionsStore } from '../../../stores/discussions';
import { useUiStore } from '../../../stores/ui';

// Icons
import IconFileText from '../../../assets/icons/IconFileText.vue';
import IconArrowDownTray from '../../../assets/icons/IconArrowDownTray.vue';
import IconPencil from '../../../assets/icons/IconPencil.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconRefresh from '../../../assets/icons/IconRefresh.vue';
import IconMenu from '../../../assets/icons/IconMenu.vue';
import DropdownMenu from '../DropdownMenu/DropdownMenu.vue';

const props = defineProps({
  artefactGroup: { type: Object, required: true },
});

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const selectedVersion = ref(props.artefactGroup.versions[0]?.version || 1);

const fileExtension = computed(() => {
    const title = props.artefactGroup.title;
    const parts = title.split('.');
    return parts.length > 1 ? parts.pop().toUpperCase() : 'DOC';
});

const isLoadedToDataZone = computed(() => props.artefactGroup.isAnyVersionLoaded);

function handleView() {
    uiStore.activeSplitArtefactTitle = props.artefactGroup.title;
    if (!uiStore.isDataZoneVisible) uiStore.isDataZoneVisible = true;
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
            version: selectedVersion.value
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
    <div class="file-icon-box" @click="handleView">
        <svg class="w-8 h-8 opacity-40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
            <path d="M14 2v6h6" />
        </svg>
    </div>

    <!-- Info Column -->
    <div class="flex-grow min-w-0 flex flex-col justify-center cursor-pointer" @click="handleView">
        <h4 class="text-sm font-bold text-gray-800 dark:text-gray-200 truncate" :title="artefactGroup.title">
            {{ artefactGroup.title }}
        </h4>
        <div class="flex items-center gap-2 mt-0.5">
            <span class="text-[10px] font-black text-gray-400 uppercase tracking-widest">{{ fileExtension }}</span>
            <span class="text-[10px] text-gray-400">•</span>
            <span class="text-[10px] font-bold text-gray-400">v{{ selectedVersion }}</span>
        </div>
    </div>

    <!-- Actions -->
    <div class="flex items-center gap-1 pr-1">
        <button @click.stop="handleDownload" class="p-2 text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors" title="Download">
            <IconArrowDownTray class="w-5 h-5" />
        </button>
        
        <!-- Advanced Actions Dropdown -->
        <DropdownMenu icon="menu" buttonClass="p-2 text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors" title="Actions">
            <button @click="toggleLoad" class="menu-item">
                <IconRefresh class="w-4 h-4 mr-3" :class="{'text-green-500': isLoadedToDataZone}"/> 
                <span>{{ isLoadedToDataZone ? 'Unload from Context' : 'Load to Context' }}</span>
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
.artefact-list-item {
    @apply flex items-center gap-4 p-2 bg-white dark:bg-gray-800/40 rounded-xl border border-gray-100 dark:border-gray-700/50 hover:border-gray-300 dark:hover:border-gray-600 transition-all shadow-sm;
}
.artefact-list-item.is-active {
    @apply ring-1 ring-blue-500/50 bg-blue-50/10 dark:bg-blue-900/5;
}
.file-icon-box {
    @apply w-12 h-12 flex-shrink-0 flex items-center justify-center bg-gray-50 dark:bg-gray-900 rounded-lg border dark:border-gray-700 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors;
}
.menu-item { @apply flex items-center w-full px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors; }
.menu-divider { @apply my-1 border-t border-gray-100 dark:border-gray-700; }
</style>