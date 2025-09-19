<script setup>
import { computed } from 'vue';
import { useDiscussionsStore } from '../../../stores/discussions';
import CodeMirrorEditor from '../../ui/CodeMirrorEditor.vue';

const discussionsStore = useDiscussionsStore();
const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const personalityDataZone = computed(() => activeDiscussion.value?.personality_data_zone || '');
const editorOptions = { readOnly: true };
</script>

<template>
    <div class="flex-1 flex flex-col min-h-0 p-2">
        <div class="flex-grow min-h-0 border dark:border-gray-700 rounded-md overflow-hidden">
            <CodeMirrorEditor
                v-model="personalityDataZone"
                class="h-full"
                :options="editorOptions"
            />
        </div>
    </div>
</template>