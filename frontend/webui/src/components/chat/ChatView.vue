<script setup>
import { computed, defineAsyncComponent } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import { storeToRefs } from 'pinia';
import MessageArea from './MessageArea.vue';
import ChatInput from './ChatInput.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const DataZone = defineAsyncComponent(() => import('./data_zone/DataZone.vue'));

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const { isLoadingMessages } = storeToRefs(discussionsStore);
const isDataZoneVisible = computed(() => uiStore.isDataZoneVisible);
</script>

<template>
    <div class="h-full flex flex-row overflow-hidden">
        <div class="flex-1 flex flex-col h-full overflow-hidden relative">
            <div v-if="isLoadingMessages" class="absolute inset-0 bg-white dark:bg-gray-800/80 backdrop-blur-sm z-20 flex flex-col items-center justify-center">
                <IconAnimateSpin class="w-16 h-16 text-blue-500 animate-spin" />
                <p class="mt-4 text-lg font-semibold text-gray-600 dark:text-gray-300">Loading Discussion...</p>
            </div>
            
            <template v-else>
                <MessageArea class="flex-1 overflow-y-auto" />
                <ChatInput />
            </template>
        </div>
        <DataZone v-if="isDataZoneVisible" />
    </div>
</template>