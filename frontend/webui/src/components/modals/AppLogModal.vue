<script setup>
import { computed, ref, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import GenericModal from './GenericModal.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();

const modalProps = computed(() => uiStore.modalData('appLog'));
const app = computed(() => modalProps.value?.app);
const logContent = ref('');
const isLoading = ref(false);

async function fetchLogs() {
    if (!app.value || isLoading.value) return;
    isLoading.value = true;
    try {
        logContent.value = await adminStore.fetchAppLog(app.value.id);
    } catch (error) {
        logContent.value = `Failed to load logs: ${error.message}`;
    } finally {
        isLoading.value = false;
    }
}

watch(
    () => uiStore.isModalOpen('appLog'),
    (isOpen) => {
        if (isOpen && app.value) {
            fetchLogs();
        } else {
            logContent.value = '';
        }
    },
    { immediate: true }
);
</script>

<template>
    <GenericModal modalName="appLog" :title="`Logs: ${app?.name || ''}`" maxWidthClass="max-w-4xl">
        <template #body>
            <div class="relative bg-gray-900 text-white font-mono text-xs p-4 rounded-md h-96 overflow-y-auto">
                <button @click="fetchLogs" class="absolute top-2 right-2 p-1.5 bg-gray-700 rounded-md hover:bg-gray-600" title="Refresh Logs">
                    <IconAnimateSpin v-if="isLoading" class="w-4 h-4" />
                    <IconRefresh v-else class="w-4 h-4" />
                </button>
                <pre class="whitespace-pre-wrap break-words">{{ logContent || 'No log output.' }}</pre>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('appLog')" type="button" class="btn btn-secondary">Close</button>
        </template>
    </GenericModal>
</template>