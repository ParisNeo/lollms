<script setup>
import { computed } from 'vue';
import { useDiscussionsStore } from '../../../stores/discussions';
import CodeMirrorEditor from '../../ui/CodeMirrorComponent/index.vue';

const discussionsStore = useDiscussionsStore();
const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const personalityDataZone = computed(() => activeDiscussion.value?.personality_data_zone || '');
</script>

<template>
    <div class="h-full flex flex-col border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden bg-white dark:bg-gray-900">
        <!-- Live Status Header -->
        <div v-if="personalityDataZone.includes('(Live)')" class="px-3 py-1.5 bg-blue-500/10 border-b border-blue-500/20 flex items-center gap-2">
            <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
            <span class="text-[10px] font-black text-blue-600 dark:text-blue-400 uppercase tracking-widest">Live Execution Context</span>
        </div>
        <div v-else class="px-3 py-1.5 bg-gray-50 dark:bg-gray-800 border-b dark:border-gray-700 flex items-center gap-2">
            <span class="text-[10px] font-black text-gray-400 uppercase tracking-widest">AI Personality Context</span>
        </div>

        <CodeMirrorEditor
            v-model="personalityDataZone"
            class="flex-1"
            :read-only="true"
            :initialMode="'view'"
            :renderable="true"
        />
    </div>
</template>
