<script setup>
import { computed, ref } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import { storeToRefs } from 'pinia';

// Icons
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconSave from '../../assets/icons/IconSave.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const props = defineProps({
  artefactGroup: {
    type: Object,
    required: true,
  },
  isLoadedToPrompt: {
    type: Boolean,
    default: false,
  }
});

const emit = defineEmits(['load-to-prompt', 'unload-from-prompt']);

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const selectedVersion = ref(props.artefactGroup.versions[0]?.version || 1);
const isExporting = ref(false);

const isLoadedToDataZone = computed(() => props.artefactGroup.isAnyVersionLoaded);

const loadedVersion = computed(() => {
    if (!isLoadedToDataZone.value) return null;
    return props.artefactGroup.versions.find(v => v.is_loaded);
});

const cardClasses = computed(() => {
    if (isLoadedToDataZone.value) return 'loaded-data-zone';
    if (props.isLoadedToPrompt) return 'loaded-prompt';
    return '';
});

async function handleLoadToDataZone() {
    await discussionsStore.loadArtefactToContext({
        discussionId: discussionsStore.currentDiscussionId,
        artefactTitle: props.artefactGroup.title,
        version: selectedVersion.value,
    });
}

function handleLoadToPrompt() {
    emit('load-to-prompt', props.artefactGroup.title, selectedVersion.value);
}

async function handleUnload() {
    await discussionsStore.unloadArtefactFromContext({
        discussionId: discussionsStore.currentDiscussionId,
        artefactTitle: props.artefactGroup.title,
        version: loadedVersion.value.version,
    });
}

function handleUnloadFromPrompt() {
    emit('unload-from-prompt', props.artefactGroup.title);
}

async function handleEdit() {
    const artefact = await discussionsStore.fetchArtefactContent({
        discussionId: discussionsStore.currentDiscussionId,
        artefactTitle: props.artefactGroup.title,
        version: selectedVersion.value,
    });
    if (artefact) {
        uiStore.openModal('artefactEditor', { artefact, discussionId: discussionsStore.currentDiscussionId });
    }
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

<template>
  <div class="artefact-card group" :class="cardClasses">
    <div class="artefact-header">
      <div class="artefact-info">
        <div class="artefact-icon" :class="{ 'loaded-data-zone': isLoadedToDataZone, 'loaded-prompt': isLoadedToPrompt }">
          <IconFileText class="w-4 h-4" />
        </div>
        <div class="artefact-details">
          <h5 class="artefact-title" :title="artefactGroup.title">{{ artefactGroup.title }}</h5>
        </div>
      </div>
      <div class="artefact-actions">
        <button @click="handleEdit" class="artefact-action-btn" title="Edit Content"><IconPencil class="w-3 h-3" /></button>
        <button @click="handleDelete" class="artefact-action-btn artefact-action-btn-danger" title="Delete Artefact"><IconTrash class="w-3 h-3" /></button>
      </div>
    </div>
    <div class="artefact-body">
        <div class="w-full">
            <select v-model="selectedVersion" class="version-select">
                <option v-for="v in artefactGroup.versions" :key="v.version" :value="v.version">
                  Version {{ v.version }}
                </option>
            </select>
        </div>
      
        <div class="grid grid-cols-2 gap-1 w-full mt-1.5">
            <button 
                @click="handleLoadToDataZone"
                class="load-btn"
                :class="{ 'loaded-data-zone-btn': isLoadedToDataZone}"
                title="Load to Data Zone">
                <IconArrowDownTray class="w-3 h-3" /> Load DZ
            </button>
            <button 
                @click="handleUnload"
                class="load-btn"
                :class="{ 'loaded-data-zone-btn': isLoadedToDataZone }"
                title="Unload from Data Zone">
                <IconCheckCircle class="w-3 h-3" /> Unload DZ
            </button>
            <button 
                @click="handleLoadToPrompt"
                class="load-btn"
                :class="{ 'loaded-prompt-btn': isLoadedToPrompt }"
                title="Load to Prompt">
                <IconArrowDownTray class="w-3 h-3" /> Load PMPT
            </button>
            <button 
                @click="handleUnloadFromPrompt"
                class="load-btn"
                :class="{ 'loaded-prompt-btn': isLoadedToPrompt }"
                title="Unload from Prompt">
                <IconCheckCircle class="w-3 h-3" /> Unload PMPT
            </button>
        </div>
    </div>
  </div>
</template>

<style scoped>
/* Main card styling */
.artefact-card.loaded-data-zone {
    @apply border-green-500 bg-green-50 dark:bg-green-900/20;
}
.artefact-icon.loaded-data-zone {
    @apply bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-300;
}
.artefact-card.loaded-prompt {
    @apply border-blue-500 bg-blue-50 dark:bg-blue-900/20;
}
.artefact-icon.loaded-prompt {
    @apply bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-300;
}

.artefact-body {
    @apply p-1.5 pt-1 border-t border-gray-200 dark:border-gray-700;
}

/* Action buttons styling */
.load-btn {
    @apply w-full flex items-center justify-center gap-1.5 px-2 py-1.5 text-xs font-semibold rounded-md transition-colors
           bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600;
}

/* Class to visually disable but keep the button in the DOM */
.load-btn.is-disabled {
    @apply opacity-40 cursor-not-allowed;
}

.load-btn.loaded-data-zone-btn:not(.is-disabled) {
    @apply bg-green-500 text-white hover:bg-green-600;
}
.load-btn.loaded-prompt-btn:not(.is-disabled) {
    @apply bg-blue-500 text-white hover:bg-blue-600;
}
</style>