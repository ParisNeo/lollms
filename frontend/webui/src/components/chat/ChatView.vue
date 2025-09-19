<script setup>
import { computed, defineAsyncComponent } from 'vue';
import { useUiStore } from '../../stores/ui';
import MessageArea from './MessageArea.vue';
import ChatInput from './ChatInput.vue';

const DataZone = defineAsyncComponent(() => import('./data_zone/DataZone.vue'));

const uiStore = useUiStore();
const isDataZoneVisible = computed(() => uiStore.isDataZoneVisible);
</script>

<template>
    <div class="h-full flex flex-row overflow-hidden">
        <div class="flex-1 flex flex-col h-full overflow-hidden">
            <MessageArea class="flex-1 overflow-y-auto" />
            <ChatInput />
        </div>
        <DataZone v-if="isDataZoneVisible" />
    </div>
</template>