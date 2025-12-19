<script setup>
import { computed } from 'vue';
import { useDiscussionsStore } from '../../../stores/discussions';
import CodeMirrorEditor from '../../ui/CodeMirrorComponent/index.vue';

const discussionsStore = useDiscussionsStore();
const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const personalityDataZone = computed(() => activeDiscussion.value?.personality_data_zone || '');
</script>

<template>
    <div class="h-full flex flex-col border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
        <CodeMirrorEditor
            v-model="personalityDataZone"
            class="h-full"
            :read-only="true"
        />
    </div>
</template>
