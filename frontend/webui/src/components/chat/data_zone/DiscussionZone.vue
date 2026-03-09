<script setup>
import { computed, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useDiscussionsStore } from '../../../stores/discussions';
import { useUiStore } from '../../../stores/ui';
import CodeMirrorEditor from '../../ui/CodeMirrorComponent/index.vue';

// Icons
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';
import IconRefresh from '../../../assets/icons/IconRefresh.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconSave from '../../../assets/icons/IconSave.vue';

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const { activeDiscussion } = storeToRefs(discussionsStore);

// Local state for the text input
const localZoneContent = ref('');
const isSaving = ref(false);
const hasUnsavedChanges = ref(false);

// Initialize local content when discussion ID changes or on mount
watch(() => activeDiscussion.value?.id, () => {
    localZoneContent.value = activeDiscussion.value?.discussion_data_zone || '';
    hasUnsavedChanges.value = false;
}, { immediate: true });

// Track manual changes
watch(localZoneContent, (newVal) => {
    if (newVal !== activeDiscussion.value?.discussion_data_zone) {
        hasUnsavedChanges.value = true;
    } else {
        hasUnsavedChanges.value = false;
    }
});

async function handleValidate() {
    if (!activeDiscussion.value) return;
    
    isSaving.value = true;
    try {
        await discussionsStore.updateDataZone({ 
            discussionId: activeDiscussion.value.id, 
            content: localZoneContent.value 
        });
        hasUnsavedChanges.value = false;
        uiStore.addNotification('Discussion context updated.', 'success');
        // Refresh token counts
        await discussionsStore.fetchContextStatus(activeDiscussion.value.id);
    } finally {
        isSaving.value = false;
    }
}

function handleClear() {
    localZoneContent.value = '';
}

async function handleSync() {
    if (!activeDiscussion.value) return;
    await discussionsStore.fetchDataZones(activeDiscussion.value.id);
    localZoneContent.value = activeDiscussion.value.discussion_data_zone || '';
    hasUnsavedChanges.value = false;
}
</script>

<template>
  <div class="flex flex-col h-full overflow-hidden">
    <!-- Action Bar -->
    <div class="flex-shrink-0 flex items-center justify-between gap-2 p-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-t-lg shadow-sm">
        <div class="flex items-center gap-1.5">
            <button @click="handleClear" 
                    class="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-gray-400 hover:text-red-500 transition-colors" 
                    title="Clear Text">
                <IconTrash class="w-4 h-4" />
            </button>
            <button @click="handleSync" 
                    class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 transition-colors" 
                    title="Restore from Server">
                <IconRefresh class="w-4 h-4" />
            </button>
        </div>

        <div class="flex items-center gap-2">
            <span v-if="hasUnsavedChanges" class="text-[9px] font-bold text-amber-500 uppercase animate-pulse">Unsaved Changes</span>
            <button @click="handleValidate" 
                    class="btn btn-primary btn-xs flex items-center gap-2 px-3 shadow-md transition-all active:scale-95"
                    :disabled="isSaving || !hasUnsavedChanges">
                <IconAnimateSpin v-if="isSaving" class="w-3.5 h-3.5 animate-spin" />
                <IconSave v-else class="w-3.5 h-3.5" />
                <span>Validate</span>
            </button>
        </div>
    </div>

    <!-- Markdown Editor -->
    <div class="flex-1 min-h-0 border-x border-b border-gray-200 dark:border-gray-700 rounded-b-lg relative overflow-hidden bg-white dark:bg-gray-950">
        <CodeMirrorEditor 
            v-model="localZoneContent" 
            class="h-full absolute inset-0"
            :initialMode="'edit'"
            placeholder="Type context instructions or persistent data here..."
        />
    </div>

    <!-- Help Footer -->
    <div class="flex-shrink-0 p-2 text-[9px] text-gray-400 italic">
        This text is injected into the system prompt for all messages in this chat.
    </div>
  </div>
</template>

<style scoped>
/* Ensure the editor doesn't have extra borders inside our container */
:deep(.cm-editor) {
    @apply border-0;
}
</style>