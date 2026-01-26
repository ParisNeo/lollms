<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import IconClose from '../../assets/icons/IconClose.vue';
import IconCode from '../../assets/icons/IconCode.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';

const uiStore = useUiStore();
// Access the modal state from the store.
const modalData = computed(() => uiStore.modals.featureInfo || null);
const isOpen = computed(() => !!modalData.value);

function closeModal() {
    uiStore.closeModal('featureInfo');
}

const title = computed(() => modalData.value?.title || 'Feature Information');
const items = computed(() => modalData.value?.items || []);
</script>

<template>
    <div v-if="isOpen" class="fixed
