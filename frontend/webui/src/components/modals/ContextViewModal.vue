<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from '../ui/GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const contextStatus = computed(() => discussionsStore.activeDiscussionContextStatus);

const systemContext = computed(() => contextStatus.value?.zones?.system_context);
const messageHistory = computed(() => contextStatus.value?.zones?.message_history);

const systemBreakdown = computed(() => {
    if (!systemContext.value?.breakdown) return [];
    // Order matters for display
    const order = ['system_prompt', 'pruning_summary', 'memory', 'user_data_zone', 'personality_data_zone', 'discussion_data_zone'];
    return Object.entries(systemContext.value.breakdown)
        .filter(([key, value]) => value && value.trim() !== '')
        .sort((a, b) => {
            const indexA = order.indexOf(a[0]);
            const indexB = order.indexOf(b[0]);
            if (indexA === -1) return 1;
            if (indexB === -1) return -1;
            return indexA - indexB;
        });
});

function formatTitle(key) {
    return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}
</script>

<template>
  <GenericModal modalName="contextViewer" title="Context Breakdown" maxWidthClass="max-w-4xl">
    <template #body>
      <div v-if="!contextStatus" class="text-center text-gray-500">
        Loading context information...
      </div>
      <div v-else class="space-y-4 text-sm">
        <div class="flex justify-between items-baseline p-3 bg-gray-100 dark:bg-gray-700/50 rounded-lg">
            <h3 class="font-semibold text-lg text-gray-800 dark:text-gray-100">Total Context</h3>
            <p class="font-mono font-semibold text-lg">
                <span class="text-blue-600 dark:text-blue-400">{{ contextStatus.current_tokens.toLocaleString() }}</span>
                <span class="text-gray-400 dark:text-gray-500"> / </span>
                <span class="text-gray-500 dark:text-gray-400">{{ (contextStatus.max_tokens || '∞').toLocaleString() }}</span>
            </p>
        </div>

        <!-- System Context Section -->
        <details v-if="systemContext" class="context-section" open>
            <summary class="context-summary">
                <span>System Context</span>
                <span class="font-mono text-xs px-2 py-0.5 bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300 rounded-full">{{ systemContext.tokens.toLocaleString() }} tokens</span>
            </summary>
            <div class="context-content">
                 <details v-for="([key, value]) in systemBreakdown" :key="key" class="context-section !border-l-2 !pl-4" open>
                    <summary class="context-summary !py-1 !text-xs">
                        <span>{{ formatTitle(key) }}</span>
                    </summary>
                    <div class="context-content">
                        <CodeMirrorEditor :model-value="value" :options="{ readOnly: true }" class="text-xs" />
                    </div>
                </details>
            </div>
        </details>
        
        <!-- Message History Section -->
        <details v-if="messageHistory" class="context-section" open>
            <summary class="context-summary">
                <span>Message History ({{ messageHistory.message_count }} messages)</span>
                <span class="font-mono text-xs px-2 py-0.5 bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300 rounded-full">{{ messageHistory.tokens.toLocaleString() }} tokens</span>
            </summary>
            <div class="context-content">
                <CodeMirrorEditor :model-value="messageHistory.content" :options="{ readOnly: true }" class="text-xs" />
            </div>
        </details>
      </div>
    </template>
    <template #footer>
        <button @click="uiStore.closeModal('contextViewer')" class="btn btn-primary">Close</button>
    </template>
  </GenericModal>
</template>

<style scoped>
.context-section {
    @apply border border-gray-200 dark:border-gray-700 rounded-lg;
}
.context-summary {
    @apply flex justify-between items-center p-3 cursor-pointer list-none font-semibold text-gray-700 dark:text-gray-200 bg-gray-50 dark:bg-gray-700/30 rounded-t-lg;
}
details[open] > .context-summary {
    @apply border-b border-gray-200 dark:border-gray-700;
}
.context-content {
    @apply p-3;
}
</style>