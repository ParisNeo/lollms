<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import GenericModal from '../ui/GenericModal.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();

const props = computed(() => uiStore.modalData('appLog'));
const app = computed(() => props.value?.app);

const isLoading = ref(false);
const logContent = ref('');

async function fetchLogs() {
    if (!app.value) return;
    isLoading.value = true;
    try {
        logContent.value = await adminStore.fetchAppLog(app.value.id);
    } catch (error) {
        logContent.value = 'Failed to load logs.';
    } finally {
        isLoading.value = false;
    }
}

watch(app, (newApp) => {
    if (newApp) {
        fetchLogs();
    }
}, { immediate: true });
</script>

<template>
    <GenericModal
        modal-name="appLog"
        :title="app ? `Logs: ${app.name}` : 'App Logs'"
        max-width-class="max-w-4xl"
    >
        <template #body>
            <div class="relative min-h-[60vh] max-h-[70vh] flex flex-col">
                 <button @click="fetchLogs" class="absolute top-0 right-0 btn btn-secondary btn-sm p-2" :disabled="isLoading">
                    <IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoading}" />
                </button>
                <div v-if="isLoading" class="flex-grow flex justify-center items-center">
                    <IconAnimateSpin class="w-8 h-8 text-gray-500" />
                </div>
                <pre v-else class="flex-grow bg-gray-900 text-gray-200 text-xs font-mono p-4 rounded-md overflow-auto whitespace-pre-wrap break-words"><code>{{ logContent }}</code></pre>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-end">
                <button @click="uiStore.closeModal('appLog')" type="button" class="btn btn-primary">Close</button>
            </div>
        </template>
    </GenericModal>
</template>