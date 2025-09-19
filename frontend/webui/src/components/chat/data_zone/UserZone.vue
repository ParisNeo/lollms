<script setup>
import { computed, ref } from 'vue';
import { useAuthStore } from '../../../stores/auth';
import CodeMirrorEditor from '../../ui/CodeMirrorEditor.vue';

// Icons
import IconUndo from '../../../assets/icons/IconUndo.vue';
import IconRedo from '../../../assets/icons/IconRedo.vue';

const authStore = useAuthStore();

const userDataZone = computed({
    get: () => authStore.user?.data_zone || '',
    set: (newVal) => {
        authStore.updateDataZone(newVal);
    }
});

// Placeholder for future undo/redo logic if needed
const canUndoUser = ref(false);
const canRedoUser = ref(false);
const handleUndoUser = () => {};
const handleRedoUser = () => {};

</script>

<template>
  <div class="flex-1 flex flex-col min-h-0">
    <div class="flex-shrink-0 px-3 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between gap-4">
        <span class="text-sm font-medium text-gray-600 dark:text-gray-300">Global User Context</span>
        <div class="flex items-center gap-1">
            <!-- Undo/Redo can remain if we implement a history for this field -->
            <button @click="handleUndoUser" class="action-btn-sm" title="Undo" :disabled="!canUndoUser"><IconUndo class="w-4 h-4" /></button>
            <button @click="handleRedoUser" class="action-btn-sm" title="Redo" :disabled="!canRedoUser"><IconRedo class="w-4 h-4" /></button>
        </div>
    </div>
    <div class="flex-grow min-h-0 p-2">
        <CodeMirrorEditor v-model="userDataZone" class="h-full border dark:border-gray-700 rounded-md" />
    </div>
  </div>
</template>